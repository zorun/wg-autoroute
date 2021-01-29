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

## Installing

The project is pure-Python and has no dependency.  The minimum required version of Python is 3.5.


## Using

For now, you can start it with a Wireguard interface name as argument:

    sudo python3 src/wg-autoroute.py wg0

Of course, it needs to run as root to be able to add and remove kernel routes.

The software will only manage routes that go through the specified interface.

TODO: systemd service

