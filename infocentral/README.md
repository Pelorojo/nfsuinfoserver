# nfsuinfocentral
You don't need to install the infocentral script as my server `nfs.onl` currently acts as public list provider. You can receive the server ip list for your own website by sending the following request:

Host/IP: nfs.onl\
TCP Port: 10881

<= in\
`LIST`\
=> out\
`<ip:port1> <ip:port2> <ip:port3>` ...

## Note
In case my server is no more or you want to use another server as public list provider, copy infocentral.py and infocentral.sh to your server, cd to that folder and run `./infocentral.sh install` (`remove` and `restart` work like for the infoserver).\
Open TCP port 10881 in your firewall, e.g. `sudo ufw allow 10881/tcp`, and change `CENTRAL_REGISTRY_HOST` in infoserver.py to your server.
