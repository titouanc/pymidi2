import logging
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from itertools import chain
from time import sleep

from pymidi2.endpoint import UMPEndpoint
from pymidi2.transport import ALSATransport, UDPTransport


def list_endpoints(args):
    if args.alsa_only:
        transports = ALSATransport.list()
    else:
        sleep(args.wait)
        if args.udp_only:
            transports = UDPTransport.list()
        else:
            transports = chain(ALSATransport.list(), UDPTransport.list())

    for t in transports:
        try:
            ep = UMPEndpoint.open(t.url)
            ep.discover()

            print(f"{ep.name} ({t.url})")
            for fb in ep.function_blocks:
                print("-", fb)

        except PermissionError:
            print(t.url, "Authentication required")


ACTIONS = {
    "list": list_endpoints,
}

parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument("action", choices=ACTIONS.keys())
parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="Enable verbose logging",
)
parser.add_argument("-D", "--debug", action="store_true", help="Enable debug logging")
parser.add_argument(
    "-u",
    "--udp-only",
    action="store_true",
    help="Only list UDP endpoints",
)
parser.add_argument(
    "-a",
    "--alsa-only",
    action="store_true",
    help="Only list ALSA endpoints",
)
parser.add_argument(
    "-w",
    "--wait",
    type=float,
    default=0.25,
    help="Number of seconds to wait for network discovery",
)


def main():
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)

    ACTIONS[args.action](args)


if __name__ == "__main__":
    main()
