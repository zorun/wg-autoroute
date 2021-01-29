#!/usr/bin/env python3

from collections import namedtuple
import subprocess
import sys
import time


INTERVAL=5
TIMEOUT=200

Peer = namedtuple("Peer", [
    "public_key",           # String
    "preshared_key",        # String
    "endpoint",             # String
    "allowed_ips",          # List
    "latest_handshake",     # Int
    "transfer_rx",          # Int
    "transfer_tx",          # Int
    "persistent_keepalive"  # Int
])

def parse_wg_peer(fields):
    peer = Peer(fields[0],
                fields[1],
                fields[2],
                fields[3].split(","),
                int(fields[4]),
                int(fields[5]),
                int(fields[6]),
                int(fields[7]))
    return peer


def get_wg_peers(interface):
    """Returns the current list of peers of the wireguard interface, as a list of Peer objects.
    """
    # Get wireguard state for interface
    wgstate = subprocess.run(["wg", "show", interface, "dump"],
                             encoding="ascii",
                             capture_output=True)
    # Discard first line, peers start at second line
    raw_peers = wgstate.stdout.split("\n")[1:]
    peers = [parse_wg_peer(raw_peer.split()) for raw_peer in raw_peers if raw_peer != ""]
    return peers


def get_kernel_routes(interface, ipv6):
    """Returns kernel routes for the given interface, as a list of prefixes."""
    if ipv6:
        raw_routes = subprocess.run(["ip", "-6", "route", "show", "dev", interface],
                                    encoding="ascii",
                                    capture_output=True)
    else:
        raw_routes = subprocess.run(["ip", "route", "show", "dev", interface],
                                    encoding="ascii",
                                    capture_output=True)
    routes = [route.split()[0] for route in raw_routes.stdout.split("\n") if route != ""]
    # Handle "default" route
    default_route = "::/0" if ipv6 else "0.0.0.0/0"
    routes = map(lambda route: default_route if route == "default" else route,
                 routes)
    # Handle host routes
    host_prefix_len = "128" if ipv6 else "32"
    routes = map(lambda route: route + "/" + host_prefix_len if not "/" in route else route,
                 routes)
    return list(routes)


def update_peer_routes(interface, wg_peers, ipv4_routes, ipv6_routes):
    """Checks the activity of all wireguard peers (last handshake),
       and updates routes in the kernel based on AllowedIPs for each peer."""
    now = time.time()
    for peer in wg_peers:
        # Active peer
        if now - peer.latest_handshake < TIMEOUT:
            for prefix in peer.allowed_ips:
                if not (prefix in ipv4_routes or prefix in ipv6_routes):
                    print("Adding new prefix {}".format(prefix))
                    subprocess.run(["ip", "route", "replace", prefix, "dev", interface])
        # Inactive peer
        else:
            for prefix in peer.allowed_ips:
                if prefix in ipv4_routes or prefix in ipv6_routes:
                    print("Removing stale prefix {}".format(prefix))
                    subprocess.run(["ip", "route", "delete", prefix, "dev", interface])


def remove_orphan_routes(interface, wg_peers, ipv4_routes, ipv6_routes):
    """Removes kernel routes that are not related to any wireguard peers.
       Allows to clean up routes when peers are removed or their IP is changed."""
    # Compute union of allowed_ips for all peers
    all_allowed_ips = set()
    for peer in wg_peers:
        all_allowed_ips.update(peer.allowed_ips)
    # Remove unknown routes
    for prefix in ipv4_routes + ipv6_routes:
        if prefix not in all_allowed_ips:
            print("Removing unknown prefix {}".format(prefix))
            subprocess.run(["ip", "route", "delete", prefix, "dev", interface])
            

def main_loop(interfaces):
    while True:
        for interface in interfaces:
            wg_peers = get_wg_peers(interface)
            ipv4_routes = get_kernel_routes(interface, ipv6=False)
            ipv6_routes = get_kernel_routes(interface, ipv6=True)
            update_peer_routes(interface, wg_peers, ipv4_routes, ipv6_routes)
            remove_orphan_routes(interface, wg_peers, ipv4_routes, ipv6_routes)
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main_loop([sys.argv[1]])
