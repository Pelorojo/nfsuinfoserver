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
