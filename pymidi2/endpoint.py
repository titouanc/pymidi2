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
    _name_complete: bool = False

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

        return (
            f"Block #{self._id} [{direction} : {role}] "
            f"'{self.name}' UMP groups {self.groups} {limitation}"
        )


@dataclass
class UMPEndpoint:
    transport: Transport
    function_blocks: list[FunctionBlock | None] = field(default_factory=list)
    name: str | None = None
    _name_complete: bool = False
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
                self._name_complete = False
            if self.name is None:
                return
            self.name += pkt.name
            if pkt.form.is_ending:
                self._name_complete = True

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
                    block._name_complete = False
                if block.name is None:
                    return
                block.name += pkt.name
                if pkt.form.is_ending:
                    block._name_complete = True

    @property
    def has_all_names(self) -> bool:
        return self._name_complete and all(
            f is not None and f._name_complete for f in self.function_blocks
        )

    def discover(self, wait_for_all_names: bool = True) -> None:
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

        if wait_for_all_names:
            while not self.has_all_names:
                self.dispatch(self.transport.recv())

    def send(self, pkt: ump.UMP) -> None:
        self.transport.send(pkt)

    def sendmany(self, pkts: list[ump.UMP]) -> None:
        self.transport.sendmany(pkts)

    def recv(self) -> ump.UMP:
        return self.transport.recv()
