# nfsuinfoserver
TCP infoserver for [nfsuserver](https://github.com/HarpyWar/nfsuserver) to share online rankings and records

## Installation:
Copy infoserver.py, holepunch.py, board.py and infoserver.sh into the nfsuserver folder (where `stat.dat` is located).\
Then cd to that folder and run:\
`./infoserver.sh install`

Options go after `install`, e.g. `./infoserver.sh install --no-holepunch`:
- `--no-holepunch`: no hole punching service (UDP 10910)
- `--no-board`: no board for kickStart (TCP 10802)

To change them, run `install` again with the new options.

## Deinstallation:
`./infoserver.sh remove`

## Restart:
`./infoserver.sh restart`

## Usage:
The server will listen on TCP port 10880 (open it in your firewall, e.g. `sudo ufw allow 10880/tcp`) and respond to following requests:

<= in\
`ping`\
=> out\
`pong`

<= in\
`rank:<type>`\
_`<type>` can be: `circuit`, `sprint`, `drift`, `drag`, `all`_\
=> out\
`<name>|<rating>|<wins>|<losses>|<disconnects>|<reputatiton>|<opp-rep>|<opp-rating>`

<= in\
`perf:<trackid>`\
_`<trackid>` can be: `1001`, `1002`, `1003`, `1004`, `1005`, `1006`, `1007`, `1008`
    `1102`, `1103`, `1104`, `1105`, `1106`, `1107`, `1108`, `1109`,
    `1201`, `1202`, `1206`, `1210`, `1207`, `1214`,
    `1301`, `1302`, `1303`, `1304`, `1305`, `1306`, `1307`, `1308`_\
=> out\
`<name1>|<result1>|<carid1>|<reverse1>~<name2>|<result2>|<cardid2>|<reverse2>` ...

# Hole punching (UDP 10910)
The info server also runs the rendezvous and relay service for the hole punching of the [NFSUServerChanger](https://github.com/Pelorojo/NFSUServerChanger) game plugin
(`holepunch.py`, started automatically). It lets players race each other even when the host
can't open UDP port 3658 (mobile/CGNAT, no port forwarding): the plugin learns the players'
real public ports here, and if a direct connection still fails, the race is relayed through
this server. Players without the plugin are not affected.

The plugin finds the service at the IP of your lobby server, so run the info server on the same
machine and open UDP port 10910 in your firewall, e.g. `sudo ufw allow 10910/udp`.\
To run the info server without it, install it with `./infoserver.sh install --no-holepunch`.

Protocol (plain text unless noted, port 10910):

<= in, from the game's UDP socket (no answer)\
`NHP1 HELLO <persona>`

<= in\
`NHP1 QUERY <ip> <persona>`\
=> out\
`NHP1 FOUND <ip> <port> <persona>` / `NHP1 OTHER <ip> <persona>` (plugin present, but its UDP
comes from another IP: relay only) / `NHP1 NONE <ip> <persona>`

<= in, from the game's UDP socket (binary)\
`NHPR` + 4-byte pair token + game packet\
=> forwarded unchanged to the other player of the pair

# Board for kickStart (TCP 10802)
The info server also runs a small board (`board.py`, started automatically) where the kickStarts of
one race meet, e.g. to agree on fair collisions: every kickStart posts its own signed entry and
checks the others itself. The board holds no key and doesn't understand the entries; they are kept
in memory only, for 10 minutes. Players without kickStart are not affected.

Open TCP port 10802 in your firewall, e.g. `sudo ufw allow 10802/tcp`.\
To run the info server without it, install it with `./infoserver.sh install --no-board`.

Malformed requests or too many of them ban the sender for 24 hours and remove its entries.
IPs are only stored as a salted hash (`board.salt`, `board.blacklist`). By hand:\
`./infoserver.sh ban <ip> [reason]` (permanent) / `./infoserver.sh unban <ip>`

# nfsuinfocentral
You don't need to install it, my server `nfs.onl` currently acts as public list provider.\
How to get the server list for your own website, or how to run your own list provider: [infocentral/README.md](infocentral/README.md)
