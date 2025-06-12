import struct
from dataclasses import dataclass
from enum import Enum, IntEnum, IntFlag, auto
from typing import Self


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
                f"but got {p} Bytes instead",
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
            "!BBH",
            self.command,
            len(self.payload) // 4,
            self.specific_data,
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
