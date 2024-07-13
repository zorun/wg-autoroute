#!/usr/bin/env python3

import argparse
from collections import namedtuple
import logging
import subprocess
import time


Peer = namedtuple("Peer", [
    "public_key",           # String
    "preshared_key",        # String
    "endpoint",             # String
    "allowed_ips",          # List
    "latest_handshake",     # Int
    "transfer_rx",          # Int
    "transfer_tx",          # Int
    "persistent_keepalive"  # Int, 0 means disabled
])

def parse_wg_peer(fields):
    try:
        persistent_keepalive = int(fields[7])
    except ValueError: # Probably "off", let's be robust to other cases
        persistent_keepalive = 0
    peer = Peer(fields[0],
                fields[1],
                fields[2],
                fields[3].split(","),
                int(fields[4]),
                int(fields[5]),
                int(fields[6]),
                persistent_keepalive)
    return peer


def get_wg_peers(interface):
    """Returns the current list of peers of the wireguard interface, as a list of Peer objects.

    In case of failure, returns None.
    """
    # Get wireguard state for interface
    wgstate = subprocess.run(["wg", "show", interface, "dump"],
                             encoding="ascii",
                             capture_output=True)
    if wgstate.returncode != 0:
        logging.error("%s: call to wireguard failed: %s", interface,
                      wgstate.stderr.strip())
        return
    # Discard first line, peers start at second line
    raw_peers = wgstate.stdout.split("\n")[1:]
    peers = [parse_wg_peer(raw_peer.split()) for raw_peer in raw_peers if raw_peer != ""]
    return peers


def get_kernel_routes(interface, ipv6):
    """Returns kernel routes for the given interface, as a list of prefixes.

    In case of failure, returns None."""
    ip = ["ip", "-6"] if ipv6 else ["ip"]
    raw_routes = subprocess.run(ip + ["route", "show", "dev", interface],
                                encoding="ascii",
                                capture_output=True)
    if raw_routes.returncode != 0:
        logging.error("%s: Couldn't get kernel routes: %s", interface,
                      raw_routes.stderr.strip())
        return
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


def update_peer_routes(interface, timeout, wg_peers, ipv4_routes, ipv6_routes):
    """Checks the activity of all wireguard peers (last handshake),
       and updates routes in the kernel based on AllowedIPs for each peer."""
    now = time.time()
    for peer in wg_peers:
        # Active peer
        if now - peer.latest_handshake < timeout:
            for prefix in peer.allowed_ips:
                if not (prefix in ipv4_routes or prefix in ipv6_routes):
                    logging.info("%s: [%s] Adding new prefix %s", interface,
                                 peer.public_key, prefix)
                    ret = subprocess.run(["ip", "route", "replace", prefix, "dev", interface],
                                         encoding="ascii",
                                         capture_output=True)
                    if ret.returncode != 0:
                        logging.error("%s: Couldn't add prefix %s: %s", interface,
                                      prefix, ret.stderr.strip())
        # Inactive peer
        else:
            for prefix in peer.allowed_ips:
                if prefix in ipv4_routes or prefix in ipv6_routes:
                    logging.info("%s: [%s] Removing stale prefix %s", interface,
                                 peer.public_key, prefix)
                    ret = subprocess.run(["ip", "route", "delete", prefix, "dev", interface],
                                         encoding="ascii",
                                         capture_output=True)
                    if ret.returncode != 0:
                        logging.error("%s: Couldn't remove prefix %s: %s", interface,
                                      prefix, ret.stderr.strip())


def remove_orphan_routes(interface, wg_peers, ipv4_routes, ipv6_routes):
    """Removes kernel routes that are not related to any wireguard peers.
       Allows to clean up routes when peers are removed or their IP is changed."""
    # Compute union of allowed_ips for all peers
    all_allowed_ips = set()
    for peer in wg_peers:
        all_allowed_ips.update(peer.allowed_ips)
    # Retrieve local addresses
    raw_addresses = subprocess.run(["ip", "-brief", "address", "show", interface],
                                   encoding="ascii",
                                   capture_output=True)
    if raw_addresses.returncode != 0:
        logging.error("%s: Couldn't get interface addresses: %s", interface,
                      raw_addresses.stderr.strip())
        return
    addresses = [address.split()[2] for address in raw_addresses.stdout.split("\n") if address != ""]
    all_allowed_ips.update(addresses)
    # Don't remove link local
    all_allowed_ips.add("fe80::/64")
    # Remove unknown routes
    for prefix in ipv4_routes + ipv6_routes:
        if prefix not in all_allowed_ips:
            logging.info("%s: Removing unknown prefix %s", interface,
                         prefix)
            ret = subprocess.run(["ip", "route", "delete", prefix, "dev", interface],
                                 encoding="ascii",
                                 capture_output=True)
            if ret.returncode != 0:
                logging.error("%s: Couldn't remove prefix %s: %s",
                              interface, prefix, ret.stderr.strip())
            

def main_loop(args):
    logging.info("Starting main loop on interfaces: %s", ", ".join(args.interface))
    while True:
        for interface in args.interface:
            wg_peers = get_wg_peers(interface)
            if wg_peers == None:
                continue
            ipv4_routes = get_kernel_routes(interface, ipv6=False)
            ipv6_routes = get_kernel_routes(interface, ipv6=True)
            if ipv4_routes == None or ipv6_routes == None:
                continue
            update_peer_routes(interface, args.timeout, wg_peers, ipv4_routes, ipv6_routes)
            remove_orphan_routes(interface, wg_peers, ipv4_routes, ipv6_routes)
        time.sleep(args.interval)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("interface", help="Wireguard interface(s) to manage",
                        nargs="+")
    parser.add_argument("--logfile", "-l", help="Log to the given file in addition to stderr")
    parser.add_argument("--interval", "-I", type=int, default=5,
                        help="Amount of seconds to wait between each route check. Default: %(default)s")
    parser.add_argument("--timeout", "-T", type=int, default=200,
                        help="Amount of seconds after which a peer will be considered inactive (since its last handshake). Don't set this lower than about 3 minutes. Default: %(default)s")
    args = parser.parse_args()
    # Setup logging
    handlers = [logging.StreamHandler()]
    if args.logfile:
        handlers.append(logging.FileHandler(args.logfile))
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                        level=logging.INFO,
                        handlers=handlers)
    try:
        main_loop(args)
    except KeyboardInterrupt:
        logging.info("Exiting main loop")
