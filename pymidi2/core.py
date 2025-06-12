"""
A Python implementation of "User Datagram Protocol for Universal MIDI Packets"
    Network MIDI 2.0 (UDP) - Transport Specification

See the specification https://drive.google.com/file/d/1dtsOgMLbtif9Fp-OaZhwnRs9an4dn3uv/edit
"""

import logging
import socket
import struct
from enum import Enum, IntEnum, IntFlag, auto
from dataclasses import dataclass
from math import ceil

from typing_extensions import Self

logger = logging.getLogger("pymidi2.core")


class ClientCapability(IntFlag):
    """
    Spec 6.4: Table 11: Capabilities for Invitation
    """

    NONE = 0
    INVITATION_WITH_AUTH = 1 << 0
    INVITATION_WITH_USER_AUTH = 1 << 1


class SessionState(Enum):
    """
    Spec 6.1: Session States
    """

    IDLE = auto()
    PENDING_INVITATION = auto()
    AUTHENTICATION_REQUIRED = auto()
    ESTABLISHED_SESSION = auto()
    PENDING_SESSION_RESET = auto()
    PENDING_BYTE = auto()


class CommandCode(IntEnum):
    """
    Spec 5.5 Command Codes ad Packet Types
    """

    INVITATION = 0x01
    INVITATION_WITH_AUTH = 0x02
    INVITATION_WITH_USER_AUTH = 0x03
    INVITATION_REPLY_ACCEPTED = 0x10
    INVITATION_REPLY_PENDING = 0x11
    INVITATION_REPLY_AUTH_REQUIRED = 0x12
    INVITATION_REPLY_USER_AUTH_REQUIRED = 0x13
    PING = 0x20
    PING_REPLY = 0x21
    RETRANSMIT_REQUEST = 0x80
    RETRANSMIT_ERROR = 0x81
    SESSION_RESET = 0x82
    SESSION_RESET_REPLY = 0x83
    NAK = 0x8F
    BYE = 0xF0
    BYE_REPLY = 0xF1
    UMP_DATA = 0xFF


@dataclass(frozen=True)
class CommandPacket:
    """
    Spec 5.4: Command Packet Header and Payload
    """

    command: CommandCode
    specific_data: int = 0
    payload: bytes = b""

    def __post_init__(self):
        if (p := len(self.payload)) % 4:
            raise ValueError(
                "Expected the payload length to be a multiple of 4 Bytes, "
                f"but got {p} Bytes instead"
            )

    @classmethod
    def parse(cls, buf: bytes) -> tuple[Self, bytes]:
        head, payload = buf[:4], buf[4:]
        command, payload_length_words, specific_data = struct.unpack("!BBH", head)
        payload_length = 4 * payload_length_words

        if len(payload) < payload_length:
            raise ValueError(
                f"Expecting at least {payload_length} bytes of payload, "
                f"but got only {len(payload)}"
            )

        res = cls(
            command=CommandCode(command),
            specific_data=specific_data,
            payload=payload[:payload_length],
        )
        return res, payload[payload_length:]

    def __bytes__(self) -> bytes:
        res = struct.pack(
            "!BBH", self.command, len(self.payload) // 4, self.specific_data
        )
        return res + self.payload


@dataclass(frozen=True)
class MIDIUDPPacket:
    commands: list[CommandPacket]

    def __bytes__(self) -> bytes:
        return b"MIDI" + b"".join(map(bytes, self.commands))

    @classmethod
    def parse(cls, buf: bytes) -> Self:
        head, buf = buf[:4], buf[4:]
        if head != b"MIDI":
            raise ValueError(f"Expecting b'MIDI' header, got {head!r}")

        commands = []
        while buf:
            cmd, buf = CommandPacket.parse(buf)
            commands.append(cmd)
        return cls(commands=commands)


@dataclass
class MIDISession:
    state: SessionState = SessionState.IDLE
    ump_seq: int = 0
    remote: tuple[str, str] | None = None

    def next_seq(self) -> int:
        res = self.ump_seq
        self.ump_seq = (self.ump_seq + 1) & 0xFFFF
        return res


@dataclass
class UMPNetEndpoint:
    name: str
    product_instance_id: str = ""
    bind_ip: str = "0.0.0.0"
    bind_port: int = 0

    def __post_init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.bind_ip, self.bind_port))
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        logger.info(f"Bound to {self.bind_ip}:{self.bind_port}")

    def send(
        self, addr_info: tuple[str, int], pkts: MIDIUDPPacket | list[CommandPacket]
    ):
        if not isinstance(pkts, MIDIUDPPacket):
            pkts = MIDIUDPPacket(commands=pkts)
        buf = bytes(pkts)
        logger.debug(f"Tx {addr_info} {buf!r}")
        self.sock.sendto(buf, addr_info)

    def recv(self) -> tuple[tuple[str, int], MIDIUDPPacket]:
        buf, addr_info = self.sock.recvfrom(1500)
        logger.debug(f"Rx {addr_info} {buf!r}")
        return addr_info, MIDIUDPPacket.parse(buf)

    def get_identity(
        self,
        as_command: CommandCode,
        capabilities: ClientCapability = ClientCapability.NONE,
    ) -> CommandPacket:
        name = self.name.encode("utf-8")
        piid = self.product_instance_id.encode("ascii")
        name_len = int(ceil(len(name) / 4))
        piid_len = int(ceil(len(piid) / 4))
        name_padded = name.ljust(4 * name_len, b"\x00")
        piid_padded = piid.ljust(4 * piid_len, b"\x00")

        return CommandPacket(
            command=as_command,
            specific_data=(name_len << 8) | int(capabilities),
            payload=name_padded + piid_padded,
        )
