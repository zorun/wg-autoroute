# Wireguard autoroute

This software automatically maintains kernel routes towards active Wireguard peers.

The main use-case is to run several redundant Wireguard servers where clients are
assigned public IP addresses inside the VPN.  When clients roam from one server to
another, their public-VPN IP address needs to be routed to the right Wireguard server.

This software only makes sure that the local routing table is synchronised with the
`AllowedIPs` configuration for each active Wireguard peer.  It is then your responsibility to
ensure that these local routes are distributed across your network (using OSPF, BGP...).

The main interesting property is that **synchronisation is dynamic:** we ensure that
kernel routes only exist when peers are **active**, and we remove routes to inactive peers.
Activity is detected based on the date of the latest handshake.


## Installation

The project is pure-Python and has no dependency.  It means you can just
copy the main script (`src/wg-autoroute.py`) and it will work.  The
minimum required version of Python is 3.5.


## Systemd service

To manage the service with systemd:

- copy `src/wg-autoroute.py` to `/usr/local/sbin/wg-autoroute.py`, make sure it is executable

- copy `systemd/wg-autoroute@.service` to `/etc/systemd/system/wg-autoroute@.service`

- enable and start the service on interface `wg0`:

    systemctl daemon-reload
    systemctl enable wg-autoroute@wg0
    systemctl start wg-autoroute@wg0

The service will only manage routes that go through the specified interface.


## Manual usage

You can also manually start the service with one or more Wireguard interface names as argument:

    sudo python3 src/wg-autoroute.py wg0

Of course, it needs to run as root to be able to add and remove kernel routes.


## Credits

The idea was first developed in bash at [Illyse](https://www.illyse.net/), member of [FFDN](https://www.ffdn.org/en).
This is a Python re-implementation.