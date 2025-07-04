import argparse
import curses
import logging
import time
from binascii import hexlify, unhexlify
from dataclasses import dataclass, field
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

        print(f"{ep.name if ep.name else '<Endpoint>'} ({endpoint_url})")
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


def recv_midi1(args):
    endpoint = UMPEndpoint.open(args.endpoint_url)
    group = get_ump_group(args.endpoint_url, -1)

    try:
        while True:
            ev = endpoint.recv()
            if ev.group == group and isinstance(ev, ump.MIDI1ChannelVoice):
                print(hexlify(ev.midi1).decode().upper())
    except KeyboardInterrupt:
        return


def send_midi2(args):
    pkts = [ump.UMP.parse([int(w, 16) for w in ev.split(",")]) for ev in args.event]

    endpoint = UMPEndpoint.open(args.endpoint_url)
    endpoint.sendmany(pkts)


def recv_midi2(args):
    endpoint = UMPEndpoint.open(args.endpoint_url)
    try:
        group = get_ump_group(args.endpoint_url, -1)
    except ValueError:
        group = None

    try:
        while True:
            ev = endpoint.recv()
            if group is None or group == ev.group:
                print(" ".join(f"{w:08X}" for w in ev.encode()))
    except KeyboardInterrupt:
        return


@dataclass
class GroupMonitor:
    act: bool = False
    chan_act: list[bool] = field(default_factory=lambda: 16 * [False])


def monitor_endpoint(args):
    monitors = [GroupMonitor() for i in range(16)]
    endpoint = UMPEndpoint.open(args.endpoint_url)
    act_char = {True: "■", False: " "}

    def run(stdscr):
        header = " ".join(f"{i:2d}" for i in range(1, 17))
        stdscr.addstr(0, 0, f" --- Channel |{header}")

        def redraw():
            for i, mon in enumerate(monitors):
                group = f"Group {1+i:2d} | {act_char[mon.act]}"
                chans = "  ".join(map(act_char.get, mon.chan_act))
                stdscr.addstr(1+i, 0, f"{group} | {chans}")
            stdscr.refresh()

        redraw()
        while True:
            ev = endpoint.recv()
            if hasattr(ev, "group"):
                monitors[ev.group].act = True
                if hasattr(ev, "channel"):
                    monitors[ev.group].chan_act[ev.channel] = True
                redraw()

    curses.wrapper(run)


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

parser_recv1 = subparsers.add_parser("recv1", help="Receive MIDI1 events")
parser_recv1.set_defaults(func=recv_midi1)
parser_recv1.add_argument("endpoint_url", help="URL of the UMP endpoint to connect to (must include the UMP group number)")

parser_send2 = subparsers.add_parser("send2", help="Send MIDI2 events")
parser_send2.set_defaults(func=send_midi2)
parser_send2.add_argument("endpoint_url", help="URL of the UMP endpoint to connect to")
parser_send2.add_argument("event", nargs="+")

parser_recv2 = subparsers.add_parser("recv2", help="Receive MIDI2 events")
parser_recv2.set_defaults(func=recv_midi2)
parser_recv2.add_argument("endpoint_url", help="URL of the UMP endpoint to connect to")

parser_mon = subparsers.add_parser("mon", help="Monitor UMP groups and channels")
parser_mon.set_defaults(func=monitor_endpoint)
parser_mon.add_argument("endpoint_url", help="URL of the UMP endpoint to connect to")

if __name__ == "__main__":
    main()
