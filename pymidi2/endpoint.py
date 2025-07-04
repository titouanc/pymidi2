import logging
from dataclasses import dataclass, field
from typing import Self, cast

from . import ump
from .transport import Transport

logger = logging.getLogger(__name__)


@dataclass
class FunctionBlock:
    _id: int
    active: bool
    groups: set[int]
    is_output: bool
    is_input: bool
    ui_hint_sender: bool
    ui_hint_receiver: bool
    midi1: bool
    restrict_31_25kbps: bool
    name: str | None = None

    @classmethod
    def from_info(cls, pkt: ump.FunctionBlockInfoNotification) -> Self:
        return cls(
            _id=pkt.function_block_id,
            active=pkt.active,
            groups=set(range(pkt.first_group, pkt.first_group + pkt.number_of_groups)),
            is_output=pkt.is_output,
            is_input=pkt.is_input,
            ui_hint_sender=pkt.ui_hint_sender,
            ui_hint_receiver=pkt.ui_hint_receiver,
            midi1=pkt.midi1.is_midi1,
            restrict_31_25kbps=pkt.midi1.is_restricted_31_25kbps,
        )

    def __str__(self) -> str:
        direction = f"{'i' if self.is_input else '-'}{'o' if self.is_output else '-'}"
        role = "--------"
        if self.ui_hint_sender and self.ui_hint_receiver:
            role = "Recv/Send"
        elif self.ui_hint_sender:
            role = "     Send"
        elif self.ui_hint_receiver:
            role = "Recv     "

        limitation = "[MIDI1 + MIDI2]"
        if self.midi1 and self.restrict_31_25kbps:
            limitation = "[MIDI1 31.25kb/s]"
        elif self.midi1:
            limitation = "[MIDI1 only]"

        name = self.name if self.name else "<Function Block>"

        return (
            f"Block #{self._id} [{direction} : {role}] "
            f"'{name}' UMP groups {self.groups} {limitation}"
        )


@dataclass
class UMPEndpoint:
    transport: Transport
    function_blocks: list[FunctionBlock | None] = field(default_factory=list)
    name: str | None = None
    _transport_connected: bool = False

    @classmethod
    def open(cls, url: str) -> Self:
        transport = Transport.open(url)
        transport.connect()
        return cls(transport, _transport_connected=True)

    def __del__(self):
        if self._transport_connected:
            self.transport.disconnect()

    def dispatch(self, pkt: ump.UMP) -> None:
        if isinstance(pkt, ump.EndpointInfoNotification):
            if self.function_blocks:
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
            if pkt.function_block_id >= len(self.function_blocks):
                logger.warning(
                    f"Receiving info for Block #{pkt.function_block_id} "
                    f"but I only know about {len(self.function_blocks)} of them",
                )
                return
            self.function_blocks[pkt.function_block_id] = FunctionBlock.from_info(pkt)

        elif isinstance(pkt, ump.FunctionBlockNameNotification):
            if pkt.function_block_id >= len(self.function_blocks):
                logger.warning(
                    f"Receiving name for Block #{pkt.function_block_id} "
                    f"but I only know about {len(self.function_blocks)} of them",
                )
                return
            if block := self.function_blocks[pkt.function_block_id]:
                if pkt.form.is_starting:
                    block.name = ""
                if block.name is None:
                    return
                block.name += pkt.name

    def discover(self) -> None:
        self.function_blocks = []
        self.name = None

        self.transport.send(
            ump.EndpointDiscovery(
                form=ump.StreamFormat.COMPLETE,
                ump_version=(1, 1),
                filter=ump.EndpointDiscovery.Filter.ALL,
            ),
        )

        while not self.function_blocks:
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

        # Send 1 more request for Endpoint Info Notification.
        # When we get its reply, all requests above should have been processed
        self.transport.send(
            ump.EndpointDiscovery(
                form=ump.StreamFormat.COMPLETE,
                ump_version=(1, 1),
                filter=ump.EndpointDiscovery.Filter.ENDPOINT_INFO_NOTIFICATION,
            ),
        )
        while True:
            msg = self.transport.recv()
            if isinstance(msg, ump.EndpointInfoNotification):
                break
            else:
                self.dispatch(msg)

    def send(self, pkt: ump.UMP) -> None:
        self.transport.send(pkt)

    def sendmany(self, pkts: list[ump.UMP]) -> None:
        self.transport.sendmany(pkts)

    def recv(self) -> ump.UMP:
        return self.transport.recv()
