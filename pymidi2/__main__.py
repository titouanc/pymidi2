import argparse
import logging
import time
from binascii import hexlify, unhexlify
from itertools import chain
from urllib.parse import urlparse

from pymidi2 import smf, ump
from pymidi2.endpoint import UMPEndpoint
from pymidi2.transport import (
    ALSATransport,
    SharedSecretRequiredError,
    Transport,
    UDPTransport,
    UserPasswordRequiredError,
)


def get_ump_group(endpoint_url: str, default: int = 0) -> int:
    ump_group = default
    url = urlparse(endpoint_url)
    if url.fragment:
        ump_group = int(url.fragment)
    if not (0 <= ump_group < 16):
        raise ValueError(f"Invalid UMP group number {ump_group}")
    return ump_group


def print_ep_topology(endpoint_url: str) -> None:
    try:
        ep = UMPEndpoint.open(endpoint_url)
        ep.discover()

        print(f"{ep.name} ({endpoint_url})")
        for fb in ep.function_blocks:
            print("-", fb)

    except SharedSecretRequiredError:
        print(f"{endpoint_url} - Requires shared secret authentication")
    except UserPasswordRequiredError:
        print(f"{endpoint_url} - Requires user/password authentication")


def find_endpoints(args) -> None:
    transports: chain[Transport] | list[ALSATransport] | list[UDPTransport]
    if args.alsa_only:
        transports = ALSATransport.find()
    else:
        time.sleep(args.wait)
        if args.udp_only:
            transports = UDPTransport.find()
        else:
            transports = chain(ALSATransport.find(), UDPTransport.find())

    for i, t in enumerate(transports):
        if i:
            print()
        print_ep_topology(t.url)


def topo_endpoint(args) -> None:
    if not args.endpoint_url:
        print("Missing endpoint url (-e / --endpoint-url)")
    else:
        print_ep_topology(args.endpoint_url)


def play_file(args) -> None:
    endpoint = None
    ump_group = 0

    if args.endpoint_url:
        ump_group = get_ump_group(args.endpoint_url, ump_group)
        endpoint = UMPEndpoint.open(args.endpoint_url)

    bpm = 120.0
    start = time.monotonic()

    for beat, events in smf.File.from_io(args.file):
        pkts = []

        for ev in events:
            if (
                isinstance(ev, smf.MetaEvent)
                and ev.meta_type is smf.MetaEvent.MetaType.TEMPO_SETTING
            ):
                # Tempo given in µs per quarter note
                bpm = 60_000_000 / int.from_bytes(ev.data, byteorder="big")

            if not isinstance(ev, smf.MIDIEvent):
                continue

            if endpoint is not None:
                prefix = bytes([0x20 + ump_group])
                event_bytes = (prefix + ev.data).ljust(4, b"\x00")
                pkts.append(ump.UMP.parse([int.from_bytes(event_bytes)]))

            if not args.quiet:
                print(hexlify(ev.data).decode().upper())

        while (time.monotonic() - start) / 60 < beat / bpm:
            pass

        if endpoint is not None:
            endpoint.sendmany(pkts)


def send_midi1(args):
    ump_group = get_ump_group(args.endpoint_url)

    pkts = []
    for ev in args.event:
        prefix = bytes([0x20 + ump_group])
        event_bytes = (prefix + unhexlify(ev)).ljust(4, b"\x00")
        pkts.append(ump.UMP.parse([int.from_bytes(event_bytes)]))

    endpoint = UMPEndpoint.open(args.endpoint_url)
    endpoint.sendmany(pkts)


def main():
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.info:
        logging.basicConfig(level=logging.INFO)

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_usage()


parser = argparse.ArgumentParser(
    "pymidi2",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)

parser.add_argument("-I", "--info", action="store_true", help="Enable info logging")
parser.add_argument("-D", "--debug", action="store_true", help="Enable debug logging")
subparsers = parser.add_subparsers()

parser_find = subparsers.add_parser("find", help="Find available UMP endpoints")
parser_find.set_defaults(func=find_endpoints)
parser_find.add_argument(
    "-u",
    "--udp-only",
    action="store_true",
    help="Only find UDP endpoints",
)
parser_find.add_argument(
    "-a",
    "--alsa-only",
    action="store_true",
    help="Only find ALSA endpoints",
)
parser_find.add_argument(
    "-w",
    "--wait",
    type=float,
    default=0.25,
    help="Number of seconds to wait for enpoints discovery on the network",
)

parser_topo = subparsers.add_parser("topo", help="Print UMP endpoint topology")
parser_topo.set_defaults(func=topo_endpoint)
parser_topo.add_argument("endpoint_url", help="URL of the UMP endpoint to connect to")


parser_play = subparsers.add_parser("play", help="Play a MIDI file")
parser_play.set_defaults(func=play_file)
parser_play.add_argument("file", type=argparse.FileType("rb"), help="File to play")
parser_play.add_argument(
    "-e",
    "--endpoint_url",
    help="URL of the UMP endpoint to play the file to",
)
parser_play.add_argument(
    "-q",
    "--quiet",
    action="store_true",
    help="Do not print MIDI events to stdout as they are played",
)

parser_send1 = subparsers.add_parser("send1", help="Send MIDI1 events")
parser_send1.set_defaults(func=send_midi1)
parser_send1.add_argument("endpoint_url", help="URL of the UMP endpoint to connect to")
parser_send1.add_argument("event", nargs="+")

if __name__ == "__main__":
    main()
