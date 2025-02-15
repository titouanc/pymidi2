import logging
import platform

from .core import CommandCode, MIDISession, CommandPacket, UMPNetEndpoint, SessionState

logger = logging.getLogger()


class MIDIHost(UMPNetEndpoint):
    def __init__(
        self,
        name: str,
        product_instance_id: str = "",
        bind_ip: str = "0.0.0.0",
        bind_port: int = 5673,
    ):
        super().__init__(
            name=name,
            product_instance_id=product_instance_id,
            bind_ip=bind_ip,
            bind_port=bind_port,
        )
        self.sessions: dict[tuple[str, int], MIDISession] = {}

    def dispatch_packet(self, addr_info: tuple[str, int], pkt: CommandPacket):
        sess = self.sessions.setdefault(addr_info, MIDISession())
        logger.debug(f"Dispatching {pkt} for {sess}")

        match pkt.command:
            case CommandCode.PING:
                reply = CommandPacket(
                    command=CommandCode.PING_REPLY,
                    payload=pkt.payload,
                )
                self.send(addr_info, [reply])

            case CommandCode.INVITATION:
                assert sess.state in {
                    SessionState.IDLE,
                    SessionState.ESTABLISHED_SESSION,
                }
                remote_name_len = 4 * (pkt.specific_data >> 8)
                remote_name = (
                    pkt.payload[:remote_name_len].rstrip(b"\x00").decode("utf-8")
                )
                remote_piid = (
                    pkt.payload[remote_name_len:].rstrip(b"\x00").decode("ascii")
                )
                sess.remote = (remote_name, remote_piid)

                reply = self.get_identity(
                    as_command=CommandCode.INVITATION_REPLY_ACCEPTED
                )
                self.send(addr_info, [reply])
                sess.state = SessionState.ESTABLISHED_SESSION

            case CommandCode.UMP_DATA:
                assert sess.state is SessionState.ESTABLISHED_SESSION
                logger.info(f"UMP DATA: {pkt.payload!r}")

            case CommandCode.BYE:
                logger.info(f"Bye from {sess} ({pkt.payload.decode('utf-8')})")
                self.sessions.pop(addr_info)
                reply = CommandPacket(command=CommandCode.BYE_REPLY)

    def main(self):
        addr_info, udp_pkt = self.recv()
        for cmd_pkt in udp_pkt.commands:
            try:
                self.dispatch_packet(addr_info, cmd_pkt)
            except Exception:
                logger.exception(f"Cannot dispatch {cmd_pkt} from {addr_info}")

    def mainloop(self):
        while True:
            self.main()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    host = MIDIHost(name="The host", product_instance_id=platform.node())
    host.mainloop()
