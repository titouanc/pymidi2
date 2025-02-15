import logging
import platform
from uuid import uuid4

from .core import (
    CommandCode,
    MIDISession,
    CommandPacket,
    UMPNetEndpoint,
    SessionState,
    ClientCapability,
)

logger = logging.getLogger("netmidi2.client")


class MIDIClient(UMPNetEndpoint):
    def __init__(
        self,
        host_ip: str,
        host_port: int,
        name: str,
        product_instance_id: str = "",
        bind_ip: str = "0.0.0.0",
        bind_port: int = 0,
    ):
        super().__init__(
            name=name,
            product_instance_id=product_instance_id,
            bind_ip=bind_ip,
            bind_port=bind_port,
        )
        self.session = MIDISession()
        self.host = (host_ip, host_port)

    def expect(self, cmd: CommandCode) -> CommandPacket:
        while True:
            addr_info, udp_packet = self.recv()
            if addr_info != self.host:
                continue

            for pkt in udp_packet.commands:
                if pkt.command == cmd:
                    return pkt

    def ping(self):
        ping_pkt = CommandPacket(command=CommandCode.PING, payload=uuid4().bytes[:4])
        self.send(self.host, [ping_pkt])
        while True:
            reply = self.expect(CommandCode.PING_REPLY)
            if reply.payload == ping_pkt.payload:
                return

    def invite(self, capabilities: ClientCapability = ClientCapability.NONE):
        invite_pkt = self.get_identity(
            as_command=CommandCode.INVITATION,
            capabilities=capabilities,
        )
        self.send(self.host, [invite_pkt])
        self.session.state = SessionState.PENDING_INVITATION
        res = self.expect(CommandCode.INVITATION_REPLY_ACCEPTED)

        remote_name_len = 4 * (res.specific_data >> 8)
        remote_name = res.payload[:remote_name_len].rstrip(b"\x00").decode("utf-8")
        remote_piid = res.payload[remote_name_len:].rstrip(b"\x00").decode("ascii")
        self.session.remote = (remote_name, remote_piid)
        self.session.state = SessionState.ESTABLISHED_SESSION
        logger.info(f"Invited {self.session}")

    def send_midi(self, ump: bytes):
        pkt = CommandPacket(
            command=CommandCode.UMP_DATA,
            specific_data=self.session.next_seq(),
            payload=ump,
        )
        self.send(self.host, [pkt])


if __name__ == "__main__":
    from time import sleep

    logging.basicConfig(level=logging.DEBUG)

    client = MIDIClient(
        host_ip="localhost",
        host_port=5763,
        name="The client",
        product_instance_id=platform.node(),
    )
    client.ping()
    client.invite()

    for i in range(10):
        client.send_midi(b"\x20\x90\x11\x29")
        sleep(0.5)
        client.send_midi(b"\x20\x80\x11\x29")
        sleep(0.5)
