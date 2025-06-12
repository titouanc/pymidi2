import pytest

import pymidi2.ump as ump

TEST_PACKETS = [
    # MIDI 1.0 Channel Voice Messages
    pytest.param(
        [0x2294407F],
        ump.MIDI1NoteOn(group=2, channel=4, note=64, velocity=127),
        id="midi1-note-on",
    ),
    pytest.param(
        [0x2284407F],
        ump.MIDI1NoteOff(group=2, channel=4, note=64, velocity=127),
        id="midi1-note-off",
    ),
    pytest.param(
        [0x22B40740],
        ump.MIDI1ControlChange(group=2, channel=4, controller=7, value=64),
        id="midi1-control-change",
    ),
    pytest.param(
        [0x22C4007F],
        ump.MIDI1ProgramChange(group=2, channel=4, program=127),
        id="midi1-program-change",
    ),
    pytest.param(
        [0x22E45836],
        ump.MIDI1PitchBend(group=2, channel=4, value=7000),
        id="midi1-pitch-bend",
    ),
    pytest.param(
        [0x22E42849],
        ump.MIDI1PitchBend(group=2, channel=4, value=-7000),
        id="midi1-pitch-bend-negative",
    ),
    # MIDI 2.0 Channel Voice Messages
    pytest.param(
        [0x42944003, 0x09C41234],
        ump.MIDI2NoteOn(
            group=2,
            channel=4,
            note=64,
            velocity=2500,
            attribute_type=3,
            attribute_data=0x1234,
        ),
        id="midi2-note-on",
    ),
    pytest.param(
        [0x42844003, 0x09C41234],
        ump.MIDI2NoteOff(
            group=2,
            channel=4,
            note=64,
            velocity=2500,
            attribute_type=3,
            attribute_data=0x1234,
        ),
        id="midi2-note-off",
    ),
    pytest.param(
        [0x42B40700, 0x12345678],
        ump.MIDI2ControlChange(group=2, channel=4, controller=7, data=0x12345678),
        id="midi2-control-change",
    ),
    pytest.param(
        [0x42C40001, 0x2A001344],
        ump.MIDI2ProgramChange(
            group=2,
            channel=4,
            program=42,
            bank_valid=True,
            bank=2500,
        ),
        id="midi2-program-change",
    ),
    pytest.param(
        [0x42E40000, 0x80000000],
        ump.MIDI2PitchBend(group=2, channel=4, value=0x80000000),
        id="midi2-pitch-bend",
    ),
    # Utility Messages
    pytest.param(
        [0x00000000],
        ump.NoOp(),
        id="noop",
    ),
    pytest.param(
        [0x00112345],
        ump.JRClock(timestamp=0x12345),
        id="jrclock",
    ),
    pytest.param(
        [0x00212345],
        ump.JRTimestamp(timestamp=0x12345),
        id="jr-timestamp",
    ),
    # System Real Time Messages
    pytest.param(
        [0x10017F00],
        ump.MIDITimeCode(type=ump.MIDITimeCodeType.HOURS_HIGH_NIBBLE, value=15),
        id="rt-timecode",
    ),
    pytest.param(
        [0x10024003],
        ump.SongPositionPointer(position=448),
        id="rt-song-position-pointer",
    ),
    # Data Messages
    pytest.param(
        [0x32040102, 0x03040000],
        ump.Data64(group=2, status=ump.UMPStreamFormat.COMPLETE, data=[1, 2, 3, 4]),
        id="data64",
    ),
    pytest.param(
        [0x52082A01, 0x02030405, 0x06070800, 0x00000000],
        ump.Data128(
            group=2,
            status=ump.UMPStreamFormat.COMPLETE,
            stream_id=42,
            data=[1, 2, 3, 4, 5, 6, 7, 8],
        ),
        id="data128",
    ),
    # UMP Stream Messages
    pytest.param(
        [0xF0000101, 0x0000001C, 0x00000000, 0x00000000],
        ump.EndpointDiscovery(
            form=ump.UMPStreamFormat.COMPLETE,
            ump_version_major=1,
            ump_version_minor=1,
            filter=ump.EndpointDiscoveryFilter.ENDPOINT_NAME_NOTIFICATION
            | ump.EndpointDiscoveryFilter.PRODUCT_INSTANCE_ID_NOTIFICATION
            | ump.EndpointDiscoveryFilter.STREAM_CONFIGURATION_NOTIFICATION,
        ),
        id="endpoint-discovery",
    ),
    pytest.param(
        [0xF0010101, 0x91000303, 0x00000000, 0x00000000],
        ump.EndpointInfoNotification(
            form=ump.UMPStreamFormat.COMPLETE,
            ump_version_major=1,
            ump_version_minor=1,
            static=True,
            n_function_blocks=17,
            midi1=True,
            midi2=True,
            rxjr=True,
            txjr=True,
        ),
        id="endpoint-info-notification",
    ),
    pytest.param(
        [0xF0020000, 0x00000007, 0x01000200, 0x01020304],
        ump.DeviceIdentityNotification(
            form=ump.UMPStreamFormat.COMPLETE,
            device_manufacturer=(0, 0, 7),
            device_family=1,
            device_family_model=2,
            software_revision=(1, 2, 3, 4),
        ),
        id="device-identity-notification",
    ),
    pytest.param(
        [0xF003E282, 0xAC75726F, 0x7261636B, 0x00000000],
        ump.EndpointNameNotification(
            form=ump.UMPStreamFormat.COMPLETE,
            name="€urorack",
        ),
        id="endpoint-name-notification",
    ),
    pytest.param(
        [0xF0044177, 0x65736F6D, 0x65207072, 0x6F640000],
        ump.ProductInstanceIdNotification(
            form=ump.UMPStreamFormat.COMPLETE,
            product_instance_id="Awesome prod",
        ),
        id="product-instance-id-notification",
    ),
    pytest.param(
        [0xF0050180, 0x00000000, 0x00000000, 0x00000000],
        ump.StreamConfigurationRequest(
            form=ump.UMPStreamFormat.COMPLETE,
            protocol=1,
            extensions=True,
            reserved=0,
        ),
        id="stream-configuration-request",
    ),
    pytest.param(
        [0xF0060180, 0x00000000, 0x00000000, 0x00000000],
        ump.StreamConfigurationNotification(
            form=ump.UMPStreamFormat.COMPLETE,
            protocol=1,
            extensions=True,
            reserved=0,
        ),
        id="stream-configuration-notification",
    ),
    pytest.param(
        [0xF0100100, 0x00000000, 0x00000000, 0x00000000],
        ump.FunctionBlockDiscovery(
            form=ump.UMPStreamFormat.COMPLETE,
            function_block_filter=1,
            reserved=0,
        ),
        id="function-block-discovery",
    ),
    pytest.param(
        [0xF011813B, 0x01020004, 0x00000000, 0x00000000],
        ump.FunctionBlockInfoNotification(
            form=ump.UMPStreamFormat.COMPLETE,
            active=True,
            function_block_id=1,
            ui_hint_output=True,
            ui_hint_input=True,
            midi1=ump.MIDI1Mode.MIDI1_RESTRICT_BANDWITH,
            is_input=True,
            is_output=True,
            first_group=1,
            number_of_groups=2,
            midi_ci_version=0,
            max_sysex_8_streams=4,
        ),
        id="function-block-info-notification",
    ),
    pytest.param(
        [0xF0120148, 0x656C6C6F, 0x00000000, 0x00000000],
        ump.FunctionBlockNameNotification(
            form=ump.UMPStreamFormat.COMPLETE,
            function_block_id=1,
            name="Hello",
        ),
        id="function-block-name-notification",
    ),
    pytest.param(
        [0xF0200000, 0x00000000, 0x00000000, 0x00000000],
        ump.StartOfClip(form=ump.UMPStreamFormat.COMPLETE, reserved=0),
        id="start-of-clip",
    ),
    pytest.param(
        [0xF0210000, 0x00000000, 0x00000000, 0x00000000],
        ump.EndOfClip(form=ump.UMPStreamFormat.COMPLETE, reserved=0),
        id="end-of-clip",
    ),
]


@pytest.mark.parametrize("words,packet", TEST_PACKETS)
def test_ump_parse_and_encode(words, packet):
    """Test that parsing and encoding work correctly for all UMP message types."""
    decoded = ump.UMP.parse(words)
    assert decoded == packet
    assert packet.encode() == words
