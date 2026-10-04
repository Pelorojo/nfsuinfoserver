#!/usr/bin/env python3
# nfsuinfoserver hole punching UDP:10910 by Redhair
"""Rendezvous and relay for the hole punching of the NFSUServerChanger game plugin (UDP).

NFSU races are a star: every client talks to the host over UDP 3658, and the lobby only tells
the players each other's public IP, never a port - so the game always sends to IP:3658. That
fails when a NAT doesn't keep port 3658 (mobile/CGNAT, no port forwarding). The plugin finds
this service at the lobby server's IP, port 10910:

  NHP1 HELLO <persona>          from the game's UDP socket; remembers the sender's public
                                ip:port for (ip, persona). No answer - nothing may reach the
                                game's socket that the game doesn't expect.
  NHP1 QUERY <ip> <persona>     from the plugin's own socket; answered with
  NHP1 FOUND <ip> <port> <persona>  -> the plugin sends to that port instead of 3658,
  NHP1 OTHER <ip> <persona>     -> the persona said HELLO from another IP (e.g. WARP uses
                                   different IPs for TCP and UDP): relay only, or
  NHP1 NONE <ip> <persona>      -> no plugin, nothing changes.

Entries are keyed by the HELLO's source IP, so a player can only register a port for its own
IP; the plugin only takes over a port for exactly the IP the lobby reported.

Relay (fallback when hole punching fails, e.g. symmetric NAT on both sides):

  NHPR <4-byte pair token> <game packet>   from the game's UDP socket of either player of a
                                host<->client pair; forwarded unchanged to the pair's other
                                endpoint. Both plugins derive the same token from the game and
                                the two personas; the first two senders of a token are the pair.

Limits per IP keep it from being abused as a free relay.
"""

import asyncio
import time

PORT = 10910
EXPIRE_SECONDS = 60          # the plugin repeats HELLO every 15 s
MAX_PERSONA = 32
MAX_HELLOS_PER_IP = 16       # personas registered from one IP
RELAY_MAGIC = b"NHPR"
RELAY_EXPIRE_SECONDS = 30    # a race sends many packets per second
MAX_PAIRS_PER_IP = 8         # relay pairs one IP may take part in
MAX_RELAY_RATE = 200         # relayed packets per second per sender (a race sends ~40)
MAX_PACKET = 2048


def log(text):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "[holepunch]", text, flush=True)


class HolePunch(asyncio.DatagramProtocol):
    def __init__(self):
        self.entries = {}   # (ip, persona) -> (port, last_seen)
        self.pairs = {}     # token -> {endpoint: last_seen}, at most 2 endpoints
        self.rates = {}     # endpoint -> (second, packets in that second)
        self.transport = None
        self.last_cleanup = 0

    def connection_made(self, transport):
        self.transport = transport

    def cleanup(self, now):
        self.entries = {k: v for k, v in self.entries.items() if now - v[1] <= EXPIRE_SECONDS}
        for token in list(self.pairs):
            pair = {e: seen for e, seen in self.pairs[token].items() if now - seen <= RELAY_EXPIRE_SECONDS}
            if pair:
                self.pairs[token] = pair
            else:
                del self.pairs[token]
        self.rates = {e: r for e, r in self.rates.items() if int(now) - r[0] <= 1}

    def within_rate(self, endpoint, now):
        second = int(now)
        start, count = self.rates.get(endpoint, (second, 0))
        if start != second:
            start, count = second, 0
        self.rates[endpoint] = (start, count + 1)
        return count < MAX_RELAY_RATE

    def relay(self, data, addr, now):
        if not self.within_rate(addr, now):
            return
        token = data[4:8]
        pair = self.pairs.get(token)
        if pair is None:
            joined = sum(1 for p in self.pairs.values() if any(e[0] == addr[0] for e in p))
            if joined >= MAX_PAIRS_PER_IP:
                return
            pair = self.pairs[token] = {}
        # Endpoints that went quiet make room (a player's NAT mapping may change).
        for endpoint in [e for e, seen in pair.items() if now - seen > RELAY_EXPIRE_SECONDS]:
            del pair[endpoint]
        if addr not in pair:
            if len(pair) >= 2:
                return
            log(f"RELAY {token.hex()} joined by {addr[0]}:{addr[1]}")
        pair[addr] = now
        for endpoint in pair:
            if endpoint != addr:
                self.transport.sendto(data, endpoint)

    def datagram_received(self, data, addr):
        now = time.time()
        if now - self.last_cleanup >= 10:
            self.last_cleanup = now
            self.cleanup(now)
        if len(data) > MAX_PACKET:
            return

        if data[:4] == RELAY_MAGIC and len(data) > 8:
            self.relay(data, addr, now)
            return

        ip, port = addr[0], addr[1]
        try:
            text = data.decode("latin-1")
        except Exception:
            return
        parts = text.split(" ", 2)
        if len(parts) < 3 or parts[0] != "NHP1":
            return

        if parts[1] == "HELLO":
            persona = parts[2][:MAX_PERSONA]
            key = (ip, persona)
            previous = self.entries.get(key)
            if previous is None and sum(1 for i, _ in self.entries if i == ip) >= MAX_HELLOS_PER_IP:
                return
            self.entries[key] = (port, now)
            if previous is None or previous[0] != port:
                log(f"HELLO {persona} at {ip}:{port}")
        elif parts[1] == "QUERY":
            query = parts[2].split(" ", 1)
            if len(query) < 2:
                return
            want_ip, persona = query[0], query[1][:MAX_PERSONA]
            entry = self.entries.get((want_ip, persona))
            if entry and now - entry[1] <= EXPIRE_SECONDS:
                answer = f"NHP1 FOUND {want_ip} {entry[0]} {persona}"
            elif any(p == persona and now - v[1] <= EXPIRE_SECONDS for (_, p), v in self.entries.items()):
                answer = f"NHP1 OTHER {want_ip} {persona}"
            else:
                answer = f"NHP1 NONE {want_ip} {persona}"
            self.transport.sendto(answer.encode("latin-1"), addr)


async def start(host="0.0.0.0", port=PORT):
    """Starts the service in the running event loop; returns the transport."""
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(HolePunch, local_addr=(host, port))
    log(f"listening on UDP {host}:{port}")
    return transport


if __name__ == "__main__":
    # Standalone: python3 holepunch.py [port]
    import sys

    async def main():
        await start(port=int(sys.argv[1]) if len(sys.argv) > 1 else PORT)
        await asyncio.Event().wait()

    asyncio.run(main())
