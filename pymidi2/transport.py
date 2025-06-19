from __future__ import annotations

import socket
import struct
from abc import abstractmethod
from dataclasses import dataclass, field, replace
from hashlib import sha256
from logging import getLogger
from pathlib import Path
from typing import ClassVar, Self
from urllib.parse import urlparse

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

from . import udp
from .ump import UMP, MessageType

logger = getLogger(__name__)


class Transport:
    @classmethod
    @abstractmethod
    def find(cls) -> list[Self]: ...

    def connect(self) -> None:
        if getattr(self, "_transport_connected", False):
            logger.warning("Already connected")
        else:
            self._connect()
            self._transport_connected = True

    def disconnect(self) -> None:
        if getattr(self, "_transport_connected", False):
            self._disconnect()
            self._transport_connected = False
        else:
            logger.warning("Already disconnected")

    @abstractmethod
    def _connect(self): ...

    @abstractmethod
    def _disconnect(self): ...

    @abstractmethod
    def send(self, packet: UMP): ...

    @abstractmethod
    def recv(self) -> UMP: ...

    @property
    @abstractmethod
    def url(self) -> str: ...

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args, **kwargs):
        self.disconnect()

    @staticmethod
    def open(url: str) -> Transport:
        parsed = urlparse(url)
        match parsed.scheme:
            case "file":
                return ALSATransport(location=Path(parsed.path))
            case "udp":
                if parsed.hostname is None or parsed.port is None:
                    raise ValueError("Missing host or port in udp url")
                return UDPTransport(
                    peer_ip=parsed.hostname,
                    peer_port=parsed.port,
                    auth=(
                        (parsed.username, parsed.password)
                        if parsed.username
                        else parsed.password
                    )
                    if parsed.password
                    else None,
                )
        raise ValueError(f"Invalid UMP endpoint {url=!r}")


@dataclass
class ALSATransport(Transport):
    location: Path

    @property
    def url(self) -> str:
        return f"file://{self.location}"

    @classmethod
    def find(cls) -> list[Self]:
        return [cls(location=p) for p in Path("/dev/snd").glob("ump*")]

    def _connect(self):
        self.recvfd = self.location.open("rb")

    def _disconnect(self):
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
class MIDI2Listener(ServiceListener):
    discovered: dict[str, tuple[str, int]] = field(default_factory=dict)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.discovered.pop(name, None)

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is not None and info.port is not None:
            addr = ".".join(map(str, info.addresses[0]))
            self.discovered[name] = (addr, info.port)
            logger.debug(f"Discovered MIDI2 service {name} at {addr}:{info.port}")

    update_service = add_service


class SharedSecretRequiredError(PermissionError):
    def __init__(self):
        super().__init__("Endpoint requires a shared secret authentication")


class UserPasswordRequiredError(PermissionError):
    def __init__(self):
        super().__init__("Endpoint requires a user/password authentication")


@dataclass
class UDPTransport(Transport):
    peer_ip: str
    peer_port: int
    bind_ip: str = "0.0.0.0"
    bind_port: int = 0
    tx_seq: int = 0
    rx_queue: list[UMP] = field(default_factory=list)
    session_established: bool = False
    auth: None | str | tuple[str, str] = None
    _mdns_listener: ClassVar[MIDI2Listener] = MIDI2Listener()

    @property
    def url(self) -> str:
        auth = ""
        if isinstance(self.auth, str):
            auth = f":{self.auth}@"
        elif isinstance(self.auth, tuple):
            auth = ":".join(self.auth) + "@"
        return f"udp://{auth}{self.peer}"

    @property
    def peer(self) -> str:
        return f"{self.peer_ip}:{self.peer_port}"

    @classmethod
    def find(cls) -> list[Self]:
        return [
            cls(peer_ip, peer_port)
            for peer_ip, peer_port in cls._mdns_listener.discovered.values()
        ]

    def sendcmd(self, *commands: udp.CommandPacket):
        pkt = udp.MIDIUDPPacket(list(commands))
        self.sock.sendto(bytes(pkt), (self.peer_ip, self.peer_port))
        logger.debug(f"Tx {pkt!r}")

    def recvcmd(self) -> list[udp.CommandPacket]:
        while True:
            buf, addr_info = self.sock.recvfrom(1500)
            if addr_info != (self.peer_ip, self.peer_port):
                continue
            pkt = udp.MIDIUDPPacket.parse(buf)
            logger.debug(f"Rx {pkt!r}")
            return pkt.commands

    def check_invitation(self, cmd: udp.CommandPacket) -> None:
        match cmd.command:
            case udp.CommandCode.INVITATION_REPLY_ACCEPTED:
                logger.info(f"Invitation to {self.peer} accepted")
                self.session_established = True

            case udp.CommandCode.INVITATION_REPLY_AUTH_REQUIRED:
                if not isinstance(self.auth, str):
                    raise SharedSecretRequiredError()

                auth = sha256(cmd.payload + self.auth.encode())
                logger.info(f"Shared secret auth to {self.peer}")
                self.sendcmd(
                    udp.CommandPacket(
                        command=udp.CommandCode.INVITATION_WITH_AUTH,
                        payload=auth.digest(),
                    ),
                )

            case udp.CommandCode.INVITATION_REPLY_USER_AUTH_REQUIRED:
                if not isinstance(self.auth, tuple):
                    raise UserPasswordRequiredError()

                logger.info(f"User auth to {self.peer} as {self.auth[0]}")
                user, pwd = map(str.encode, self.auth)
                auth = sha256(cmd.payload + user + pwd)
                if len(user) % 4:
                    pad = len(user) + 4 - len(user) % 4
                    user = user.ljust(pad, b"\x00")

                self.sendcmd(
                    udp.CommandPacket(
                        command=udp.CommandCode.INVITATION_WITH_USER_AUTH,
                        payload=auth.digest() + user,
                    ),
                )

    def _connect(self):
        self.session_established = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 0))
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # 1. Send invitation packet
        self.sendcmd(
            udp.CommandPacket(
                command=udp.CommandCode.INVITATION,
                specific_data=udp.ClientCapability.NONE,
            ),
        )

        # 2. Wait for invitation reply
        while not self.session_established:
            for cmd in self.recvcmd():
                self.check_invitation(cmd)

    def _disconnect(self):
        self.sendcmd(
            udp.CommandPacket(
                command=udp.CommandCode.BYE,
                specific_data=(
                    udp.ByeReason.USER_TERMINATED
                    if self.session_established
                    else udp.ByeReason.INVITATION_CANCELED
                )
                << 8,
            ),
        )
        self.session_established = False
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


ServiceBrowser(Zeroconf(), "_midi2._udp.local.", UDPTransport._mdns_listener)
