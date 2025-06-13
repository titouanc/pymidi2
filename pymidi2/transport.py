import socket
import struct
from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from logging import getLogger
from pathlib import Path
from typing import Self

from . import udp
from .ump import UMP, MessageType

logger = getLogger(__name__)


class Transport:
    @classmethod
    @abstractmethod
    def list(cls) -> Sequence[Self]: ...

    @abstractmethod
    def connect(self): ...

    @abstractmethod
    def disconnect(self): ...

    @abstractmethod
    def send(self, packet: UMP): ...

    @abstractmethod
    def recv(self) -> UMP: ...

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args, **kwargs):
        self.disconnect()


@dataclass
class ALSATransport(Transport):
    location: Path

    @classmethod
    def list(cls) -> Sequence[Self]:
        return [cls(location=p) for p in Path("/dev/snd").glob("ump*")]

    def connect(self):
        self.recvfd = self.location.open("rb")

    def disconnect(self):
        self.recvfd.close()

    def send(self, packet: UMP):
        words = packet.encode()
        encoded = struct.pack("@" + len(words) * "I", *words)
        with self.location.open("wb") as fd:
            fd.write(encoded)
            logger.debug(f"Tx {packet!r}")

    def recv(self) -> UMP:
        words = struct.unpack("@I", self.recvfd.read(4))
        mt = MessageType(words[0] >> 28)
        remaining = mt.num_words - 1
        if remaining:
            words += struct.unpack(
                "@" + "I" * remaining,
                self.recvfd.read(4 * remaining),
            )
        packet = UMP.parse(words)
        logger.debug(f"Rx {packet!r}")
        return packet


@dataclass
class UDPTransport(Transport):
    peer_ip: str
    peer_port: int
    bind_ip: str = "0.0.0.0"
    bind_port: int = 0
    tx_seq: int = 0
    rx_queue: list[UMP] = field(default_factory=list)
    connected: bool = False

    @classmethod
    def list(cls) -> Sequence[Self]:
        # TODO: mdns discovery
        raise NotImplementedError()

    def sendcmd(self, *commands: udp.CommandPacket):
        pkt = udp.MIDIUDPPacket(list(commands))
        self.sock.sendto(bytes(pkt), (self.peer_ip, self.peer_port))
        logger.debug(f"Tx {pkt!r}")

    def recvcmd(self) -> Sequence[udp.CommandPacket]:
        while True:
            buf, addr_info = self.sock.recvfrom(1500)
            if addr_info != (self.peer_ip, self.peer_port):
                continue
            pkt = udp.MIDIUDPPacket.parse(buf)
            logger.debug(f"Rx {pkt!r}")
            return pkt.commands

    def connect(self):
        self.connected = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 0))
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # 1. Send invitation packet
        self.sendcmd(
            udp.CommandPacket(
                command=udp.CommandCode.INVITATION,
                specific_data=udp.ClientCapability.NONE,
                payload=b"",
            ),
        )

        # 2. Wait for invitation reply
        while not self.connected:
            for cmd in self.recvcmd():
                if cmd.command is udp.CommandCode.INVITATION_REPLY_ACCEPTED:
                    self.connected = True

    def disconnect(self):
        self.connected = False
        self.sock.close()

    def send(self, packet: UMP):
        words = packet.encode()
        encoded = struct.pack(">" + len(words) * "I", *words)
        self.sendcmd(
            udp.CommandPacket(
                command=udp.CommandCode.UMP_DATA,
                specific_data=self.tx_seq,
                payload=encoded,
            ),
        )
        self.tx_seq += 1

    def dispatch(self, cmd: udp.CommandPacket):
        match cmd.command:
            case udp.CommandCode.PING:
                reply = replace(cmd, command=udp.CommandCode.PING_REPLY)
                self.sendcmd(reply)

            case udp.CommandCode.UMP_DATA:
                words = [
                    int.from_bytes(cmd.payload[4 * i : 4 * (i + 1)], byteorder="big")
                    for i in range(len(cmd.payload) // 4)
                ]
                self.rx_queue.append(UMP.parse(words))

    def recv(self) -> UMP:
        while not self.rx_queue:
            for cmd in self.recvcmd():
                self.dispatch(cmd)
        return self.rx_queue.pop(0)
