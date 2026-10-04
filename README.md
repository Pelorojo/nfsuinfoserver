# nfsuinfoserver
TCP infoserver for [nfsuserver](https://github.com/HarpyWar/nfsuserver) to share online rankings and records

## Installation:
Copy infoserver.py and infoserver.sh into the nfsuserver folder (where `stat.dat` is located).\
Then cd to that folder and run:\
`./infoserver.sh install`

## Deinstallation:
`./infoserver.sh remove`

## Restart:
`./infoserver.sh restart`

## Usage:
The server will listen on TCP port 10880 and respond to following requests:

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
To run the info server without it, add `--no-holepunch` to the `ExecStart` line of the service.

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

# nfsuinfocentral
You don't need to install the infocentral script as my server `nfs.onl` currently acts as public list provider. You can receive the the server ip list for your own website by sending the following request:

Host/IP: nfs.onl\
TCP Port: 10881

<= in\
`LIST`\
=> out\
`<ip:port1> <ip:port2> <ip:port3>` ...

## Note
In case my server is no more or you want to use another server as public list provider, the installation is equivalent to infoserver.
