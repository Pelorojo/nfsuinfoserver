#!/usr/bin/env python3
# nfsuinfoserver board TCP:10802 by Redhair
"""A board where the kickStarts of one race meet (TCP), e.g. to agree on the kind of collisions.

The board doesn't understand what is posted and holds no key: every kickStart signs its own
entry and checks the others itself. So the board can't forge or replay entries, only lose them,
and a missing entry only leads to the safe choice for that race.

  client -> board  BOARD POST <race-id> <message>
  board  -> client OK | FAIL full
  client -> board  BOARD GET <race-id>
  board  -> client <count>, then one message per line

  race-id: 32 hex. message: <ver>.<nick-hex>.<state>.<flags-hex>.<mac-hex>, i.e. ver 1-9,
  nick 1-12 bytes as hex, state on | cars-off | all-off, flags 8 hex, mac 32 hex; hex in lower case.
  One request per connection. Entries are kept in memory only, for 10 minutes.

The same port takes HELLO and RACE of the plugin check (private addon); without it they get
"FAIL unsupported". Anything else, a malformed BOARD line or too many requests bans the sender
for 24 hours and removes its entries at once. Bans only affect BOARD and unknown requests.
IPs are only kept as a salted hash (salt in board.salt), also in board.blacklist
("<hash>;<unixtime>;<reason>" per line, time 0 = permanent).

  python3 board.py ban <ip> [reason]    permanent ban (the running server picks it up)
  python3 board.py unban <ip>
"""

import asyncio
import hashlib
import hmac
import ipaddress
import os
import re
import secrets
import sys
import time
from collections import deque

PORT = 10802
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SALT_FILE = os.path.join(BASE_DIR, "board.salt")
BLACKLIST_FILE = os.path.join(BASE_DIR, "board.blacklist")
TIMEOUT = 5                  # seconds for the request line
MAX_LINE = 256
MAX_PER_IP = 4               # connections open at the same time from one IP
MAX_TOTAL = 64
KEEP_SECONDS = 600           # a race's entries are dropped this long after its first post
MAX_MESSAGES = 12            # per race (6 players, room for retries)
MAX_POSTS_PER_IP = 6         # per race and IP (several players behind one IP, e.g. LAN)
MAX_RACES_PER_IP = 8         # races one IP posts to within KEEP_SECONDS
MAX_GETS_PER_MINUTE = 60     # kickStart reads about once a second for a few seconds
MAX_RACES = 5000
MAX_BANS = 10000
BAN_SECONDS = 24 * 3600      # dynamic IPs: a ban mustn't hit someone else later for good

RACE_ID = re.compile(r"[0-9a-f]{32}")
MESSAGE = re.compile(r"[1-9]\.((?:[0-9a-f]{2}){1,12})\.(?:on|cars-off|all-off)\.[0-9a-f]{8}\.[0-9a-f]{32}")
PLUGIN_COMMANDS = ("HELLO", "RACE")   # never banned, also where the plugin check isn't running


class Banned(Exception):
    pass


def log(text):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "[board]", text, flush=True)


def message_ok(message):
    match = MESSAGE.fullmatch(message)
    return match is not None and all(c >= 0x20 and c != 0x7F for c in bytes.fromhex(match.group(1)))


def load_salt(path):
    """The node's own random salt, made on the first start; hashes don't match between nodes."""
    try:
        with open(path, encoding="ascii") as f:
            salt = bytes.fromhex(f.read().strip())
        if len(salt) == 32:
            return salt
    except FileNotFoundError:
        pass
    salt = secrets.token_bytes(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(salt.hex() + "\n")
    return salt


def ip_hash(salt, ip):
    return hmac.new(salt, ip.encode("ascii"), hashlib.sha256).hexdigest()[:32]


class Blacklist:
    def __init__(self, path):
        self.path = path
        self.bans = {}       # hash -> (unixtime, reason); unixtime 0 = permanent
        self.stamp = None
        self.reload()

    def reload(self):
        """Read again only when the file changed (ban/unban from the command line)."""
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            self.bans, self.stamp = {}, None
            return
        stamp = (st.st_mtime_ns, st.st_size)
        if stamp == self.stamp:
            return
        bans = {}
        with open(self.path, encoding="ascii", errors="replace") as f:
            for line in f:
                parts = line.strip().split(";", 2)
                if len(parts) == 3 and RACE_ID.fullmatch(parts[0]) and parts[1].isdigit():
                    bans[parts[0]] = (int(parts[1]), parts[2])
        self.bans, self.stamp = bans, stamp

    def active(self, when, now):
        return when == 0 or now - when < BAN_SECONDS

    def banned(self, h):
        entry = self.bans.get(h)
        return entry is not None and self.active(entry[0], int(time.time()))

    def save(self):
        now = int(time.time())
        self.bans = {h: v for h, v in self.bans.items() if self.active(v[0], now)}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="ascii") as f:
            f.writelines(f"{h};{when};{reason}\n" for h, (when, reason) in sorted(self.bans.items()))
        os.replace(tmp, self.path)
        st = os.stat(self.path)
        self.stamp = (st.st_mtime_ns, st.st_size)

    def add(self, h, when, reason):
        """False if the list is full (the ban then only lasts for this connection)."""
        if h not in self.bans and len(self.bans) >= MAX_BANS:
            self.save()     # drops expired bans
            if len(self.bans) >= MAX_BANS:
                return False
        self.bans[h] = (when, reason)
        self.save()
        return True


class Board:
    def __init__(self, handlers, enabled, salt_path, blacklist_path):
        self.handlers = handlers     # command -> async fn(tokens, reader, writer, ip)
        self.enabled = enabled
        self.salt = load_salt(salt_path)
        self.blacklist = Blacklist(blacklist_path)
        self.races = {}      # race-id -> (first post unixtime, {message: ip hash})
        self.ip_races = {}   # ip hash -> set of race-ids it posted to
        self.gets = {}       # ip hash -> deque of GET times
        self.per_ip = {}     # ip hash -> open connections
        self.total = 0
        self.pruned = 0

    def prune(self, now):
        if now - self.pruned < 5:
            return
        self.pruned = now
        self.races = {r: v for r, v in self.races.items() if now - v[0] < KEEP_SECONDS}
        self.ip_races = {h: s & self.races.keys() for h, s in self.ip_races.items()}
        self.ip_races = {h: s for h, s in self.ip_races.items() if s}
        self.gets = {h: q for h, q in self.gets.items() if q and now - q[-1] < 60}

    def purge(self, h):
        """Removes everything this IP posted; returns how many messages."""
        purged = 0
        for rid in self.ip_races.pop(h, ()):
            race = self.races.get(rid)
            if race is None:
                continue
            mine = [m for m, owner in race[1].items() if owner == h]
            for m in mine:
                del race[1][m]
            purged += len(mine)
            if not race[1]:
                del self.races[rid]
        self.gets.pop(h, None)
        return purged

    def ban(self, h, reason):
        purged = self.purge(h)
        try:
            self.blacklist.add(h, int(time.time()), reason)
        except OSError as e:
            log(f"error writing {self.blacklist.path}: {e}")
        log(f"BAN ip={h} reason={reason} purged={purged}")

    def post(self, h, rid, message, now):
        mine = self.ip_races.setdefault(h, set())
        if rid not in mine and len(mine) >= MAX_RACES_PER_IP:
            raise Banned("too-many-races")
        race = self.races.get(rid)
        if race is not None and now - race[0] >= KEEP_SECONDS:
            del self.races[rid]      # expired, not pruned yet: starts again
            race = None
        if race is None:
            if len(self.races) >= MAX_RACES:
                return "FAIL full"
            race = self.races[rid] = (now, {})
        messages = race[1]
        if message in messages:
            return "OK"          # a retry
        if len(messages) >= MAX_MESSAGES:
            return "FAIL full"
        if sum(1 for owner in messages.values() if owner == h) >= MAX_POSTS_PER_IP:
            raise Banned("too-many-posts")
        messages[message] = h
        mine.add(rid)
        return "OK"

    def get(self, h, rid, now):
        times = self.gets.setdefault(h, deque())
        while times and now - times[0] >= 60:
            times.popleft()
        if len(times) >= MAX_GETS_PER_MINUTE:
            raise Banned("too-many-gets")
        times.append(now)
        race = self.races.get(rid)
        messages = list(race[1]) if race is not None and now - race[0] < KEEP_SECONDS else []
        return "\n".join([str(len(messages))] + messages)

    def board(self, tokens, h):
        """Answer to a BOARD request; Banned if it's malformed."""
        now = time.time()
        self.prune(now)
        if len(tokens) == 4 and tokens[1] == "POST" and RACE_ID.fullmatch(tokens[2]) and message_ok(tokens[3]):
            return self.post(h, tokens[2], tokens[3], now)
        if len(tokens) == 3 and tokens[1] == "GET" and RACE_ID.fullmatch(tokens[2]):
            return self.get(h, tokens[2], now)
        raise Banned("bad-board")

    async def serve(self, reader, writer, ip, h):
        try:
            line = await asyncio.wait_for(reader.readuntil(b"\n"), TIMEOUT)
            tokens = line.decode("ascii").split()
        except (asyncio.LimitOverrunError, UnicodeDecodeError):
            raise Banned("bad-line")     # longer than MAX_LINE or not ASCII
        command = tokens[0] if tokens else ""
        if command in self.handlers:
            await self.handlers[command](tokens, reader, writer, ip)
            return
        if command in PLUGIN_COMMANDS or (command == "BOARD" and not self.enabled):
            answer = "FAIL unsupported"
        elif command == "BOARD" and not self.blacklist.banned(h):
            answer = self.board(tokens, h)
        elif command == "BOARD":
            return       # banned: no answer at all
        else:
            raise Banned("unknown-command")
        writer.write(answer.encode("ascii") + b"\n")
        await writer.drain()

    async def handle(self, reader, writer):
        ip = writer.get_extra_info("peername")[0]
        h = ip_hash(self.salt, ip)
        self.blacklist.reload()
        if self.total >= MAX_TOTAL or self.per_ip.get(h, 0) >= MAX_PER_IP:
            writer.close()
            return
        self.total += 1
        self.per_ip[h] = self.per_ip.get(h, 0) + 1
        try:
            await self.serve(reader, writer, ip, h)
        except Banned as e:
            if not self.blacklist.banned(h):
                self.ban(h, str(e))
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError):
            pass     # slow, empty or dropped connection: no ban
        except Exception as e:
            log(f"error: {e!r}")
        finally:
            writer.close()
            self.total -= 1
            self.per_ip[h] -= 1
            if self.per_ip[h] <= 0:
                del self.per_ip[h]


async def start(host="0.0.0.0", port=PORT, handlers=None, enabled=True,
                salt_path=SALT_FILE, blacklist_path=BLACKLIST_FILE):
    """Starts the service on port 10802 in the running event loop; returns the server.

    handlers: {"HELLO": fn, "RACE": fn} of the plugin check, if it runs; enabled=False answers
    BOARD with "FAIL unsupported" (--no-board) but keeps the port for the plugin check.
    """
    board = Board(handlers or {}, enabled, salt_path, blacklist_path)
    server = await asyncio.start_server(board.handle, host, port, limit=MAX_LINE)
    log(f"listening on TCP {host}:{port} (board {'on' if enabled else 'off'}"
        f"{', plugin check ' + '/'.join(sorted(board.handlers)) if board.handlers else ''})")
    return server


def command_line(args):
    if len(args) in (2, 3) and args[0] == "ban" or len(args) == 2 and args[0] == "unban":
        try:
            ip = str(ipaddress.IPv4Address(args[1]))
        except ValueError:
            sys.exit(f"not an IPv4 address: {args[1]}")
        h = ip_hash(load_salt(SALT_FILE), ip)
        blacklist = Blacklist(BLACKLIST_FILE)
        if args[0] == "ban":
            reason = re.sub(r"[^A-Za-z0-9_.-]", "_", args[2] if len(args) == 3 else "manual")[:32]
            if not blacklist.add(h, 0, reason):
                sys.exit(f"{BLACKLIST_FILE} is full")
            print(f"banned {ip} for good ({h})")
        elif blacklist.bans.pop(h, None) is not None:
            blacklist.save()
            print(f"unbanned {ip} ({h})")
        else:
            print(f"{ip} is not banned")
    elif not args:
        async def main():
            await start()
            await asyncio.Event().wait()
        asyncio.run(main())      # standalone: python3 board.py
    else:
        sys.exit("usage: board.py [ban <ip> [reason] | unban <ip>]")


if __name__ == "__main__":
    command_line(sys.argv[1:])
