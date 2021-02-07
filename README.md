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
Activity is detected based on the age of the latest handshake.


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

To pass additional options, create a file `/etc/default/wg-autoroute` and
define `$WG_AUTOROUTE_ARGS`, for instance:

    # /etc/default/wg-autoroute
    WG_AUTOROUTE_ARGS="--timeout 300"

The service will only manage routes that go through the specified
interface. If you need to manage several wireguard interfaces, either
start several systemd services, or use $WG_AUTOROUTE_ARGS to manually add
several interfaces to the command-line arguments.


## Manual usage

You can also manually start the service with one or more Wireguard interface names as argument:

    sudo python3 src/wg-autoroute.py wg0 [wg1 [...]]

Of course, it needs to run as root to be able to add and remove kernel routes.

Other options:

    --logfile LOGFILE, -l LOGFILE
                        Log to the given file in addition to stderr
    --interval INTERVAL, -I INTERVAL
                        Amount of seconds to wait between each route check. Default: 5
    --timeout TIMEOUT, -T TIMEOUT
                        Amount of seconds after which a peer will be considered inactive
			(since its last handshake). Don't set this lower than about 3 minutes.
			Default: 200


## Credits

The idea was first developed in bash at [Illyse](https://www.illyse.net/), member of [FFDN](https://www.ffdn.org/en).
This is a Python re-implementation.
