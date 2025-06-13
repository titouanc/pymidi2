from dataclasses import dataclass
from typing import cast

from . import ump
from .transport import ALSATransport, Transport


@dataclass
class FunctionBlock:
    info: ump.FunctionBlockInfoNotification
    name: str | None = None


@dataclass
class UMPEndpoint:
    transport: Transport
    function_blocks: list[FunctionBlock | None] | None = None
    name: str | None = None

    def expect(self, pkt_type: type[ump.UMP]) -> ump.UMP:
        while True:
            pkt = self.transport.recv()
            if isinstance(pkt, pkt_type):
                return pkt

    def dispatch(self, pkt: ump.UMP) -> None:
        if isinstance(pkt, ump.EndpointInfoNotification):
            if self.function_blocks is not None:
                return
            self.function_blocks = cast(
                "list[FunctionBlock | None]",
                pkt.n_function_blocks * [None],
            )

        elif isinstance(pkt, ump.EndpointNameNotification):
            if pkt.form.is_starting:
                self.name = ""
            if self.name is None:
                return
            self.name += pkt.name

        elif isinstance(pkt, ump.FunctionBlockInfoNotification):
            if self.function_blocks is None:
                return
            self.function_blocks[pkt.function_block_id] = FunctionBlock(pkt)

        elif isinstance(pkt, ump.FunctionBlockNameNotification):
            if self.function_blocks is None:
                return
            if block := self.function_blocks[pkt.function_block_id]:
                if pkt.form.is_starting:
                    block.name = ""
                if block.name is None:
                    return
                block.name += pkt.name

    def discover(self) -> None:
        self.function_blocks = None
        self.name = None

        self.transport.send(
            ump.EndpointDiscovery(
                form=ump.StreamFormat.COMPLETE,
                ump_version=(1, 1),
                filter=ump.EndpointDiscovery.Filter.ALL,
            ),
        )

        while self.function_blocks is None:
            self.dispatch(self.transport.recv())

        for i in range(len(self.function_blocks)):
            self.transport.send(
                ump.FunctionBlockDiscovery(
                    form=ump.StreamFormat.COMPLETE,
                    filter=ump.FunctionBlockDiscovery.Filter.ALL,
                    block_num=i,
                ),
            )

        while not all(self.function_blocks):
            self.dispatch(self.transport.recv())

        if self.function_blocks[0].name:
            while not all(f.name for f in self.function_blocks):
                self.dispatch(self.transport.recv())


if __name__ == "__main__":
    import logging
    from pprint import pprint

    logging.basicConfig(level=logging.DEBUG)

    with ALSATransport.list()[0] as t:
        ep = UMPEndpoint(t)
        ep.discover()
        pprint(ep)
