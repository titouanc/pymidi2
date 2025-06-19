import pytest

from pymidi2.udp import CommandCode, CommandPacket, MIDIUDPPacket


def test_decode_valid_packet():
    pkt, rest = CommandPacket.parse(b"\xff\x01\x12\x34****")
    assert rest == b""
    assert pkt.command == CommandCode.UMP_DATA
    assert pkt.specific_data == 0x1234
    assert pkt.payload == b"****"


def test_decode_with_rest():
    pkt_bytes = b"\xff\x01\x12\x34****"
    pkt, rest = CommandPacket.parse(2 * pkt_bytes)
    assert rest == pkt_bytes


def test_encode_valid_packet():
    pkt = CommandPacket(
        command=CommandCode.UMP_DATA,
        specific_data=2047,
        payload=b"Coucou  ",
    )
    assert bytes(pkt) == b"\xff\x02\x07\xffCoucou  "


def test_encode_unaligned_payload():
    with pytest.raises(ValueError):
        CommandPacket(command=CommandCode.UMP_DATA, payload="unaligned")


def test_decode_udp_packet():
    udp_pkt = MIDIUDPPacket.parse(b"MIDI\xff\x01\x12\x34****")
    [pkt] = udp_pkt.commands
    assert pkt.command == CommandCode.UMP_DATA
    assert pkt.specific_data == 0x1234
    assert pkt.payload == b"****"
