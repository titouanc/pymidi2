from dataclasses import dataclass, field
from enum import IntEnum, IntFlag


class MessageType(IntEnum):
    """UMP Message Type definitions"""

    UTILITY = 0x0
    SYSTEM_REAL_TIME = 0x1
    MIDI_1_CHANNEL_VOICE = 0x2
    DATA_64 = 0x3
    MIDI_2_CHANNEL_VOICE = 0x4
    DATA_128 = 0x5
    FLEX_DATA = 0xD
    UMP_STREAM = 0xF

    @property
    def num_words(self) -> int:
        return UMP_NUM_WORDS[self]


UMP_NUM_WORDS = {
    MessageType.UTILITY: 1,
    MessageType.SYSTEM_REAL_TIME: 1,
    MessageType.MIDI_1_CHANNEL_VOICE: 1,
    MessageType.DATA_64: 2,
    MessageType.MIDI_2_CHANNEL_VOICE: 2,
    MessageType.DATA_128: 4,
    MessageType.FLEX_DATA: 4,
    MessageType.UMP_STREAM: 4,
}


class UMPStreamFormat(IntEnum):
    COMPLETE = 0
    START = 1
    CONTINUE = 2
    END = 3


class UMPStreamStatus(IntEnum):
    """UMP Stream Message Status values"""

    ENDPOINT_DISCOVERY = 0x00
    ENDPOINT_INFO_NOTIFICATION = 0x01
    DEVICE_IDENTITY_NOTIFICATION = 0x02
    ENDPOINT_NAME_NOTIFICATION = 0x03
    PRODUCT_INSTANCE_ID_NOTIFICATION = 0x04
    STREAM_CONFIGURATION_REQUEST = 0x05
    STREAM_CONFIGURATION_NOTIFICATION = 0x06
    FUNCTION_BLOCK_DISCOVERY = 0x10
    FUNCTION_BLOCK_INFO_NOTIFICATION = 0x11
    FUNCTION_BLOCK_NAME_NOTIFICATION = 0x12
    START_OF_CLIP = 0x20
    END_OF_CLIP = 0x21


class UtilityStatus(IntEnum):
    """Utility Message Status values"""

    NOOP = 0x0
    JR_CLOCK = 0x1
    JR_TIMESTAMP = 0x2
    DELTA_CLOCKSTAMP_TPQ = 0x3
    DELTA_CLOCKSTAMP = 0x4


class SystemRealTimeStatus(IntEnum):
    """System Real Time Message Status values"""

    MIDI_TIME_CODE = 0x1
    SONG_POSITION_POINTER = 0x2
    SONG_SELECT = 0x3
    TUNE_REQUEST = 0x6
    TIMING_CLOCK = 0x8
    START = 0xA
    CONTINUE = 0xB
    STOP = 0xC
    ACTIVE_SENSING = 0xE
    RESET = 0xF


class MIDI1Status(IntEnum):
    """MIDI 1.0 Channel Voice Message Status values"""

    NOTE_OFF = 0x8
    NOTE_ON = 0x9
    POLY_PRESSURE = 0xA
    CONTROL_CHANGE = 0xB
    PROGRAM_CHANGE = 0xC
    CHANNEL_PRESSURE = 0xD
    PITCH_BEND = 0xE


class MIDI2Status(IntEnum):
    """MIDI 2.0 Channel Voice Message Status values"""

    REGISTERED_PER_NOTE_CONTROLLER = 0x0
    ASSIGNABLE_PER_NOTE_CONTROLLER = 0x1
    REGISTERED_CONTROLLER = 0x2
    ASSIGNABLE_CONTROLLER = 0x3
    RELATIVE_REGISTERED_CONTROLLER = 0x4
    RELATIVE_ASSIGNABLE_CONTROLLER = 0x5
    PER_NOTE_PITCH_BEND = 0x6
    NOTE_OFF = 0x8
    NOTE_ON = 0x9
    POLY_PRESSURE = 0xA
    CONTROL_CHANGE = 0xB
    PROGRAM_CHANGE = 0xC
    CHANNEL_PRESSURE = 0xD
    PITCH_BEND = 0xE
    PER_NOTE_MANAGEMENT = 0xF


class FlexDataStatusBank(IntEnum):
    SETUP_AND_PERFORMANCE_EVENTS = 0x00
    METADATA_TEXT = 0x01
    PERFORMANCE_TEXT_EVENTS = 0x02


class PerformanceEventStatus(IntEnum):
    SET_TEMPO = 0x00
    SET_TIME_SIGNATURE = 0x01
    SET_METRONOME = 0x02
    SET_KEY_SIGNATURE = 0x05
    SET_CHORD_NAME = 0x06
    TEXT_EVENT = 0x10


class MetadataTextStatus(IntEnum):
    UNKNOWN = 0x00
    PROJECT_NAME = 0x01
    SONG_NAME = 0x02
    MIDI_CLIP_NAME = 0x03
    COPYRIGHT_NOTICE = 0x04
    COMPOSER_NAME = 0x05
    LYRICIST_NAME = 0x06
    ARRANGER_NAME = 0x07
    PUBLISHER_NAME = 0x08
    PRIMARY_PERFOMER_NAME = 0x09
    ACCOMPANYING_PERFORMER_NAME = 0x0A
    RECORDING_DATE = 0x0B
    RECORDING_LOCATION = 0x0C


class PerformanceTextStatus(IntEnum):
    UNKNOWN = 0x00
    LYRICS = 0x01
    LYRICS_LANGUAGE = 0x02
    RUBY = 0x03
    RUBY_LANGUAGE = 0x04


class MIDITimeCodeType(IntEnum):
    FRAME_LOW_NIBBLE = 0
    FRAME_HIGH_NIBBLE = 1
    SECONDS_LOW_NIBBLE = 2
    SECONDS_HIGH_NIBBLE = 3
    MINUTES_LOW_NIBBLE = 4
    MINUTES_HIGH_NIBBLE = 5
    HOURS_LOW_NIBBLE = 6
    HOURS_HIGH_NIBBLE = 7


@dataclass
class UMP:
    mt: MessageType = field(init=False)

    @classmethod
    def parse(cls, words):
        mt = MessageType(words[0] >> 28)
        return UMP_BY_MT[mt].parse(words)

    def encode_into(self, words: list[int]) -> None:
        words[0] |= self.mt << 28

    def encode(self) -> list[int]:
        words = UMP_NUM_WORDS[self.mt] * [0]
        self.encode_into(words)
        return words


# Utility Messages
@dataclass
class Utility(UMP):
    status: UtilityStatus = field(init=False)

    def __post_init__(self):
        self.mt = MessageType.UTILITY

    @classmethod
    def parse(cls, words, **kwargs):
        status = UtilityStatus((words[0] >> 20) & 0xF)
        return UTILITY_BY_STATUS[status].parse(words, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.status << 20


@dataclass
class NoOp(Utility):
    def __post_init__(self):
        super().__post_init__()
        self.status = UtilityStatus.NOOP

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(**kwargs)


@dataclass
class JRClock(Utility):
    timestamp: int

    def __post_init__(self):
        super().__post_init__()
        self.status = UtilityStatus.JR_CLOCK

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(timestamp=words[0] & 0xFFFFF, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.timestamp & 0xFFFFF


@dataclass
class JRTimestamp(Utility):
    timestamp: int

    def __post_init__(self):
        super().__post_init__()
        self.status = UtilityStatus.JR_TIMESTAMP

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(timestamp=words[0] & 0xFFFFF, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.timestamp & 0xFFFFF


# System Real Time Messages
@dataclass
class SystemRealTime(UMP):
    status: SystemRealTimeStatus = field(init=False)

    def __post_init__(self):
        self.mt = MessageType.SYSTEM_REAL_TIME

    @classmethod
    def parse(cls, words, **kwargs):
        status = SystemRealTimeStatus((words[0] >> 16) & 0xFF)
        return SYSTEM_RT_BY_STATUS.get(status, cls).parse(words, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.status << 16


@dataclass
class MIDITimeCode(SystemRealTime):
    type: MIDITimeCodeType
    value: int

    def __post_init__(self):
        super().__post_init__()
        self.status = SystemRealTimeStatus.MIDI_TIME_CODE

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            type=MIDITimeCodeType((words[0] >> 12) & 0x07),
            value=(words[0] >> 8) & 0x0F,
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.type << 12) | (self.value << 8)


@dataclass
class SongPositionPointer(SystemRealTime):
    position: int

    def __post_init__(self):
        super().__post_init__()
        self.status = SystemRealTimeStatus.SONG_POSITION_POINTER

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            position=((words[0] & 0x7F) << 7) | ((words[0] >> 8) & 0x7F),
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= ((self.position & 0x7F) << 8) | ((self.position >> 7) & 0x7F)


# MIDI 1.0 Channel Voice Messages
@dataclass
class MIDI1ChannelVoice(UMP):
    group: int
    status: MIDI1Status = field(init=False)
    channel: int

    def __post_init__(self):
        self.mt = MessageType.MIDI_1_CHANNEL_VOICE

    @classmethod
    def parse(cls, words, **kwargs):
        group = (words[0] >> 24) & 0xF
        status = MIDI1Status((words[0] >> 20) & 0xF)
        channel = (words[0] >> 16) & 0xF
        return MIDI1_BY_STATUS[status].parse(
            words,
            group=group,
            channel=channel,
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.group << 24) | (self.status << 20) | (self.channel << 16)


@dataclass
class MIDI1NoteOff(MIDI1ChannelVoice):
    note: int
    velocity: int

    def __post_init__(self):
        super().__post_init__()
        self.status = MIDI1Status.NOTE_OFF

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(note=(words[0] >> 8) & 0x7F, velocity=words[0] & 0x7F, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.note << 8) | self.velocity


@dataclass
class MIDI1NoteOn(MIDI1ChannelVoice):
    note: int
    velocity: int

    def __post_init__(self):
        super().__post_init__()
        self.status = MIDI1Status.NOTE_ON

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(note=(words[0] >> 8) & 0x7F, velocity=words[0] & 0x7F, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.note << 8) | self.velocity


@dataclass
class MIDI1ControlChange(MIDI1ChannelVoice):
    controller: int
    value: int

    def __post_init__(self):
        super().__post_init__()
        self.status = MIDI1Status.CONTROL_CHANGE

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(controller=(words[0] >> 8) & 0x7F, value=words[0] & 0x7F, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.controller << 8) | self.value


@dataclass
class MIDI1ProgramChange(MIDI1ChannelVoice):
    program: int

    def __post_init__(self):
        super().__post_init__()
        self.status = MIDI1Status.PROGRAM_CHANGE

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(program=words[0] & 0x7F, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.program


@dataclass
class MIDI1PitchBend(MIDI1ChannelVoice):
    value: int

    def __post_init__(self):
        super().__post_init__()
        self.status = MIDI1Status.PITCH_BEND

    @classmethod
    def parse(cls, words, **kwargs):
        lsb = (words[0] >> 8) & 0x7F
        msb = words[0] & 0x7F
        value = (msb << 7) | lsb
        if value & (1 << 13):
            value -= 1 << 14
        return cls(value=value, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= ((self.value & 0x7F) << 8) | ((self.value >> 7) & 0x7F)


# MIDI 2.0 Channel Voice Messages
@dataclass
class MIDI2ChannelVoice(UMP):
    group: int
    status: MIDI2Status = field(init=False)
    channel: int

    def __post_init__(self):
        self.mt = MessageType.MIDI_2_CHANNEL_VOICE

    @classmethod
    def parse(cls, words, **kwargs):
        group = (words[0] >> 24) & 0xF
        status = MIDI2Status((words[0] >> 20) & 0xF)
        channel = (words[0] >> 16) & 0xF
        return MIDI2_BY_STATUS[status].parse(
            words,
            group=group,
            channel=channel,
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.group << 24) | (self.status << 20) | (self.channel << 16)


@dataclass
class MIDI2NoteOff(MIDI2ChannelVoice):
    note: int
    attribute_type: int
    velocity: int
    attribute_data: int

    def __post_init__(self):
        super().__post_init__()
        self.status = MIDI2Status.NOTE_OFF

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            note=(words[0] >> 8) & 0x7F,
            attribute_type=words[0] & 0xFF,
            velocity=words[1] >> 16,
            attribute_data=words[1] & 0xFFFF,
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.note << 8) | self.attribute_type
        words[1] |= (self.velocity << 16) | self.attribute_data


@dataclass
class MIDI2NoteOn(MIDI2ChannelVoice):
    note: int
    attribute_type: int
    velocity: int
    attribute_data: int

    def __post_init__(self):
        super().__post_init__()
        self.status = MIDI2Status.NOTE_ON

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            note=(words[0] >> 8) & 0x7F,
            attribute_type=words[0] & 0xFF,
            velocity=words[1] >> 16,
            attribute_data=words[1] & 0xFFFF,
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.note << 8) | self.attribute_type
        words[1] |= (self.velocity << 16) | self.attribute_data


@dataclass
class MIDI2ControlChange(MIDI2ChannelVoice):
    controller: int
    data: int

    def __post_init__(self):
        super().__post_init__()
        self.status = MIDI2Status.CONTROL_CHANGE

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            controller=(words[0] >> 8) & 0x7F,
            data=words[1],
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.controller << 8
        words[1] |= self.data


@dataclass
class MIDI2ProgramChange(MIDI2ChannelVoice):
    program: int
    bank_valid: bool
    bank: int

    def __post_init__(self):
        super().__post_init__()
        self.status = MIDI2Status.PROGRAM_CHANGE

    @classmethod
    def parse(cls, words, **kwargs):
        bank_msb = (words[1] >> 8) & 0x7F
        bank_lsb = words[1] & 0x7F
        return cls(
            bank_valid=bool(words[0] & (1 << 0)),
            program=(words[1] >> 24) & 0x7F,
            bank=(bank_msb << 7) | bank_lsb,
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        bank_lsb = self.bank & 0x7F
        bank_msb = self.bank >> 7
        print(hex(self.bank), hex(bank_msb), hex(bank_lsb))
        words[0] |= self.bank_valid
        words[1] |= (self.program << 24) | (bank_msb << 8) | bank_lsb


@dataclass
class MIDI2PitchBend(MIDI2ChannelVoice):
    value: int

    def __post_init__(self):
        super().__post_init__()
        self.status = MIDI2Status.PITCH_BEND

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(value=words[1], **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[1] |= self.value


# Data Messages (64-bit and 128-bit)
@dataclass
class Data64(UMP):
    group: int
    status: UMPStreamFormat
    data: list[int]  # up to 6 bytes

    def __post_init__(self):
        self.mt = MessageType.DATA_64

    @classmethod
    def parse(cls, words, **kwargs):
        length = (words[0] >> 16) & 0xF
        data = [
            *(words[0] & 0x7F7F).to_bytes(length=2, byteorder="big"),
            *(words[1] & 0x7F7F7F7F).to_bytes(length=4, byteorder="big"),
        ]
        return cls(
            group=(words[0] >> 24) & 0xF,
            status=UMPStreamFormat((words[0] >> 20) & 0xF),
            data=data[:length],
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        if len(self.data) > 6:
            raise ValueError("Data64 message can only carry up to 6 bytes of data")
        super().encode_into(words)
        data = list(self.data)
        if len(data) < 6:
            data += (6 - len(data)) * [0]
        words[0] |= (
            (self.group << 24)
            | (self.status << 20)
            | (len(self.data) << 16)
            | ((data[0] & 0x7F) << 8)
            | (data[1] & 0x7F)
        )
        words[1] = int.from_bytes(data[2:], byteorder="big")


@dataclass
class Data128(UMP):
    group: int
    status: UMPStreamFormat
    stream_id: int
    data: list[int]  # up to 13 bytes

    def __post_init__(self):
        self.mt = MessageType.DATA_128

    @classmethod
    def parse(cls, words, **kwargs):
        length = (words[0] >> 16) & 0xF
        data = [
            words[0] & 0xFF,
            *words[1].to_bytes(length=4, byteorder="big"),
            *words[2].to_bytes(length=4, byteorder="big"),
            *words[3].to_bytes(length=4, byteorder="big"),
        ]
        return cls(
            group=(words[0] >> 24) & 0xF,
            status=UMPStreamFormat((words[0] >> 20) & 0xF),
            stream_id=(words[0] >> 8) & 0xFF,
            data=data[:length],
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        if len(self.data) > 13:
            raise ValueError("Data64 message can only carry up to 13 bytes of data")
        super().encode_into(words)
        data = list(self.data)
        if len(data) < 13:
            data += (13 - len(data)) * [0]
        words[0] |= (
            (self.group << 24)
            | (self.status << 20)
            | (len(self.data) << 16)
            | (self.stream_id << 8)
            | (data[0] & 0xFF)
        )
        words[1] = int.from_bytes(data[1:5], byteorder="big")
        words[2] = int.from_bytes(data[5:9], byteorder="big")
        words[3] = int.from_bytes(data[9:13], byteorder="big")


# Flex Data Messages
@dataclass
class FlexData(UMP):
    group: int
    form: UMPStreamFormat
    address: int
    channel: int
    status_bank: FlexDataStatusBank = field(init=False)

    def __post_init__(self):
        self.mt = MessageType.FLEX_DATA

    @classmethod
    def parse(cls, words, **kwargs):
        status_bank = FlexDataStatusBank((words[0] >> 8) & 0xFF)
        return FLEX_DATA_BY_STATUS_BANK[status_bank].parse(
            words,
            group=(words[0] >> 24) & 0xF,
            form=UMPStreamFormat((words[0] >> 22) & 0x3),
            address=(words[0] >> 16) & 0x3F,
            channel=(words[0] >> 12) & 0xF,
            status=words[0] & 0xFF,
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (
            (self.group << 24)
            | (self.form << 22)
            | (self.address << 16)
            | (self.channel << 12)
            | (self.status_bank << 8)
        )


@dataclass
class SetupAndPerformanceEvent(FlexData):
    status: PerformanceEventStatus

    def __post_init__(self):
        self.status_bank = FlexDataStatusBank.SETUP_AND_PERFORMANCE_EVENTS

    @classmethod
    def parse(cls, words, status, **kwargs):
        return cls(status=PerformanceEventStatus(status))

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.status


@dataclass
class MetadataText(FlexData):
    status: MetadataTextStatus

    def __post_init__(self):
        self.status_bank = FlexDataStatusBank.METADATA_TEXT

    @classmethod
    def parse(cls, words, status, **kwargs):
        return cls(status=MetadataTextStatus(status))

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.status


@dataclass
class PerformanceTextEvent(FlexData):
    status: PerformanceTextStatus

    def __post_init__(self):
        self.status_bank = FlexDataStatusBank.PERFORMANCE_TEXT_EVENTS

    @classmethod
    def parse(cls, words, status, **kwargs):
        return cls(status=PerformanceTextStatus(status))

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.status


# UMP Stream Messages (keeping your existing implementation)
@dataclass
class UMPStream(UMP):
    form: UMPStreamFormat
    status: UMPStreamStatus = field(init=False)

    def __post_init__(self):
        self.mt = MessageType.UMP_STREAM

    @classmethod
    def parse(cls, words, **kwargs):
        form = UMPStreamFormat((words[0] >> 26) & 0x03)
        status = UMPStreamStatus((words[0] >> 16) & 0x3FF)
        return UMP_STREAM_BY_STATUS[status].parse(words, form=form, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.form << 26) | (self.status << 16)


class EndpointDiscoveryFilter(IntFlag):
    ENDPOINT_INFO_NOTIFICATION = 1 << 0
    DEVICE_IDENTITY_NOTIFICATION = 1 << 1
    ENDPOINT_NAME_NOTIFICATION = 1 << 2
    PRODUCT_INSTANCE_ID_NOTIFICATION = 1 << 3
    STREAM_CONFIGURATION_NOTIFICATION = 1 << 4


@dataclass
class EndpointDiscovery(UMPStream):
    ump_version_major: int
    ump_version_minor: int
    filter: EndpointDiscoveryFilter

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStreamStatus.ENDPOINT_DISCOVERY

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            ump_version_major=(words[0] >> 8) & 0xFF,
            ump_version_minor=words[0] & 0xFF,
            filter=EndpointDiscoveryFilter(words[1] & 0x1F),
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.ump_version_major << 8) | self.ump_version_minor
        words[1] |= self.filter


@dataclass
class EndpointInfoNotification(UMPStream):
    ump_version_major: int
    ump_version_minor: int
    static: bool
    n_function_blocks: int
    midi2: bool
    midi1: bool
    rxjr: bool
    txjr: bool

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStreamStatus.ENDPOINT_INFO_NOTIFICATION

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            ump_version_major=(words[0] >> 8) & 0xFF,
            ump_version_minor=words[0] & 0xFF,
            static=bool(words[1] & (1 << 31)),
            n_function_blocks=(words[1] >> 24) & 0x7F,
            midi2=bool(words[1] & (1 << 9)),
            midi1=bool(words[1] & (1 << 8)),
            rxjr=bool(words[1] & (1 << 1)),
            txjr=bool(words[1] & (1 << 0)),
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.ump_version_major << 8) | self.ump_version_minor
        words[1] |= (
            (self.static << 31)
            | (self.n_function_blocks << 24)
            | (self.midi2 << 9)
            | (self.midi1 << 8)
            | (self.rxjr << 1)
            | (self.txjr)
        )


@dataclass
class DeviceIdentityNotification(UMPStream):
    device_manufacturer: tuple[int, int, int]
    device_family: int
    device_family_model: int
    software_revision: tuple[int, int, int, int]

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStreamStatus.DEVICE_IDENTITY_NOTIFICATION
        if len(self.device_manufacturer) != 3:
            raise ValueError("Device manufacturer should be a triple")
        if len(self.software_revision) != 4:
            raise ValueError("Software revision should be a quadruplet")

    @classmethod
    def parse(cls, words, **kwargs):
        family_lsb = (words[2] >> 24) & 0x7F
        family_msb = (words[2] >> 16) & 0x7F
        model_lsb = (words[2] >> 8) & 0x7F
        model_msb = words[2] & 0x7F
        return cls(
            device_manufacturer=(
                (words[1] >> 16) & 0x7F,
                (words[1] >> 8) & 0x7F,
                words[1] & 0x7F,
            ),
            device_family=(family_msb << 7) | family_lsb,
            device_family_model=(model_msb << 7) | model_lsb,
            software_revision=(
                (words[3] >> 24) & 0x7F,
                (words[3] >> 16) & 0x7F,
                (words[3] >> 8) & 0x7F,
                words[3] & 0x7F,
            ),
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        family_lsb = self.device_family & 0x7F
        family_msb = (self.device_family >> 7) & 0x7F
        model_lsb = self.device_family_model & 0x7F
        model_msb = (self.device_family_model >> 7) & 0x7F
        words[1] |= int.from_bytes(self.device_manufacturer, byteorder="big")
        words[2] = int.from_bytes(
            (family_lsb, family_msb, model_lsb, model_msb), byteorder="big"
        )
        words[3] = int.from_bytes(self.software_revision, byteorder="big")


@dataclass
class EndpointNameNotification(UMPStream):
    name: str

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStreamStatus.ENDPOINT_NAME_NOTIFICATION

    @classmethod
    def parse(cls, words, **kwargs):
        chars = [
            *(words[0] & 0xFFFF).to_bytes(length=2, byteorder="big"),
            *words[1].to_bytes(length=4, byteorder="big"),
            *words[2].to_bytes(length=4, byteorder="big"),
            *words[3].to_bytes(length=4, byteorder="big"),
        ]
        return cls(
            name=bytes(chars).decode("utf-8").rstrip("\x00"),
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        chars = self.name.encode("utf-8").ljust(14, b"\x00")
        if len(chars) > 14:
            raise ValueError("Endpoint name notification can carry up to 14 bytes")

        super().encode_into(words)
        words[0] |= int.from_bytes(chars[:2], byteorder="big")
        words[1] = int.from_bytes(chars[2:6], byteorder="big")
        words[2] = int.from_bytes(chars[6:10], byteorder="big")
        words[3] = int.from_bytes(chars[10:], byteorder="big")


@dataclass
class ProductInstanceIdNotification(UMPStream):
    product_instance_id: str  # up to 14 bytes

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStreamStatus.PRODUCT_INSTANCE_ID_NOTIFICATION

    @classmethod
    def parse(cls, words, **kwargs):
        chars = [
            *(words[0] & 0xFFFF).to_bytes(length=2, byteorder="big"),
            *words[1].to_bytes(length=4, byteorder="big"),
            *words[2].to_bytes(length=4, byteorder="big"),
            *words[3].to_bytes(length=4, byteorder="big"),
        ]
        return cls(
            product_instance_id=bytes(chars).decode("ascii").rstrip("\x00"),
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        chars = self.product_instance_id.encode("ascii").ljust(14, b"\x00")
        if len(chars) > 14:
            raise ValueError("Product instance id can carry up to 14 bytes")

        super().encode_into(words)
        words[0] |= int.from_bytes(chars[:2], byteorder="big")
        words[1] = int.from_bytes(chars[2:6], byteorder="big")
        words[2] = int.from_bytes(chars[6:10], byteorder="big")
        words[3] = int.from_bytes(chars[10:], byteorder="big")


@dataclass
class StreamConfigurationRequest(UMPStream):
    protocol: int
    extensions: bool
    reserved: int

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStreamStatus.STREAM_CONFIGURATION_REQUEST

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            protocol=(words[0] >> 8) & 0xFF,
            extensions=bool(words[0] & (1 << 7)),
            reserved=words[0] & 0x7F,
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (
            (self.protocol << 8) | (self.extensions << 7) | (self.reserved & 0x7F)
        )


@dataclass
class StreamConfigurationNotification(UMPStream):
    protocol: int
    extensions: bool
    reserved: int

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStreamStatus.STREAM_CONFIGURATION_NOTIFICATION

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            protocol=(words[0] >> 8) & 0xFF,
            extensions=bool(words[0] & (1 << 7)),
            reserved=words[0] & 0x7F,
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (
            (self.protocol << 8) | (self.extensions << 7) | (self.reserved & 0x7F)
        )


@dataclass
class FunctionBlockDiscovery(UMPStream):
    function_block_filter: int
    reserved: int

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStreamStatus.FUNCTION_BLOCK_DISCOVERY

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            function_block_filter=(words[0] >> 8) & 0xFF,
            reserved=words[0] & 0xFF,
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.function_block_filter << 8) | self.reserved


class MIDI1Mode(IntEnum):
    NOT_MIDI1 = 0x00
    MIDI1 = 0x01
    MIDI1_RESTRICT_BANDWITH = 0x02


@dataclass
class FunctionBlockInfoNotification(UMPStream):
    active: bool
    function_block_id: int
    ui_hint_output: bool
    ui_hint_input: bool
    midi1: MIDI1Mode
    is_output: bool
    is_input: bool
    first_group: int
    number_of_groups: int
    midi_ci_version: int
    max_sysex_8_streams: int

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStreamStatus.FUNCTION_BLOCK_INFO_NOTIFICATION

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            active=bool((words[0] >> 15) & 1),
            function_block_id=(words[0] >> 8) & 0x7F,
            ui_hint_output=bool((words[0] >> 5) & 1),
            ui_hint_input=bool((words[0] >> 4) & 1),
            midi1=MIDI1Mode((words[0] >> 2) & 0x03),
            is_output=bool((words[0] >> 1) & 1),
            is_input=bool(words[0] & 1),
            first_group=words[1] >> 24,
            number_of_groups=(words[1] >> 16) & 0xFF,
            midi_ci_version=(words[1] >> 8) & 0xFF,
            max_sysex_8_streams=words[1] & 0xFF,
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (
            (self.active << 15)
            | (self.function_block_id << 8)
            | (self.ui_hint_output << 5)
            | (self.ui_hint_input << 4)
            | (self.midi1 << 2)
            | (self.is_output << 1)
            | self.is_input
        )
        words[1] = int.from_bytes(
            [
                self.first_group,
                self.number_of_groups,
                self.midi_ci_version,
                self.max_sysex_8_streams,
            ],
            byteorder="big",
        )


@dataclass
class FunctionBlockNameNotification(UMPStream):
    function_block_id: int
    name: str

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStreamStatus.FUNCTION_BLOCK_NAME_NOTIFICATION

    @classmethod
    def parse(cls, words, **kwargs):
        function_block_id = (words[0] >> 8) & 0xFF

        # Extract name from remaining bytes
        name_bytes = []

        # Get remaining byte from first word
        name_bytes.append(words[0] & 0xFF)

        # Get bytes from remaining words
        for i in range(1, 4):
            for j in range(4):
                byte_val = (words[i] >> (24 - j * 8)) & 0xFF
                name_bytes.append(byte_val)

        # Remove null bytes and decode
        name_bytes = [b for b in name_bytes if b != 0]
        name = bytes(name_bytes).decode("utf-8", errors="ignore")

        return cls(function_block_id=function_block_id, name=name, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.function_block_id << 8

        name_bytes = self.name.encode("utf-8")[
            :13
        ]  # Max 13 bytes (1 byte used for FB ID)

        # Pack first byte into first word
        if len(name_bytes) > 0:
            words[0] |= name_bytes[0]

        # Pack remaining bytes
        idx = 1
        for i in range(1, 4):
            for j in range(4):
                if idx < len(name_bytes):
                    words[i] |= name_bytes[idx] << (24 - j * 8)
                    idx += 1


@dataclass
class StartOfClip(UMPStream):
    reserved: int

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStreamStatus.START_OF_CLIP

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(reserved=words[0] & 0xFFFF, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.reserved & 0xFFFF


@dataclass
class EndOfClip(UMPStream):
    reserved: int

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStreamStatus.END_OF_CLIP

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(reserved=words[0] & 0xFFFF, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.reserved & 0xFFFF


# Lookup tables
UMP_BY_MT = {
    MessageType.UTILITY: Utility,
    MessageType.SYSTEM_REAL_TIME: SystemRealTime,
    MessageType.MIDI_1_CHANNEL_VOICE: MIDI1ChannelVoice,
    MessageType.DATA_64: Data64,
    MessageType.MIDI_2_CHANNEL_VOICE: MIDI2ChannelVoice,
    MessageType.DATA_128: Data128,
    MessageType.FLEX_DATA: FlexData,
    MessageType.UMP_STREAM: UMPStream,
}

UTILITY_BY_STATUS = {
    UtilityStatus.NOOP: NoOp,
    UtilityStatus.JR_CLOCK: JRClock,
    UtilityStatus.JR_TIMESTAMP: JRTimestamp,
}

SYSTEM_RT_BY_STATUS = {
    SystemRealTimeStatus.MIDI_TIME_CODE: MIDITimeCode,
    SystemRealTimeStatus.SONG_POSITION_POINTER: SongPositionPointer,
}

MIDI1_BY_STATUS = {
    MIDI1Status.NOTE_OFF: MIDI1NoteOff,
    MIDI1Status.NOTE_ON: MIDI1NoteOn,
    MIDI1Status.CONTROL_CHANGE: MIDI1ControlChange,
    MIDI1Status.PROGRAM_CHANGE: MIDI1ProgramChange,
    MIDI1Status.PITCH_BEND: MIDI1PitchBend,
}

MIDI2_BY_STATUS = {
    MIDI2Status.NOTE_OFF: MIDI2NoteOff,
    MIDI2Status.NOTE_ON: MIDI2NoteOn,
    MIDI2Status.CONTROL_CHANGE: MIDI2ControlChange,
    MIDI2Status.PROGRAM_CHANGE: MIDI2ProgramChange,
    MIDI2Status.PITCH_BEND: MIDI2PitchBend,
}

FLEX_DATA_BY_STATUS_BANK = {
    FlexDataStatusBank.SETUP_AND_PERFORMANCE_EVENTS: SetupAndPerformanceEvent,
    FlexDataStatusBank.METADATA_TEXT: MetadataText,
    FlexDataStatusBank.PERFORMANCE_TEXT_EVENTS: PerformanceTextEvent,
}

UMP_STREAM_BY_STATUS = {
    UMPStreamStatus.ENDPOINT_DISCOVERY: EndpointDiscovery,
    UMPStreamStatus.ENDPOINT_INFO_NOTIFICATION: EndpointInfoNotification,
    UMPStreamStatus.DEVICE_IDENTITY_NOTIFICATION: DeviceIdentityNotification,
    UMPStreamStatus.ENDPOINT_NAME_NOTIFICATION: EndpointNameNotification,
    UMPStreamStatus.PRODUCT_INSTANCE_ID_NOTIFICATION: ProductInstanceIdNotification,
    UMPStreamStatus.STREAM_CONFIGURATION_REQUEST: StreamConfigurationRequest,
    UMPStreamStatus.STREAM_CONFIGURATION_NOTIFICATION: StreamConfigurationNotification,
    UMPStreamStatus.FUNCTION_BLOCK_DISCOVERY: FunctionBlockDiscovery,
    UMPStreamStatus.FUNCTION_BLOCK_INFO_NOTIFICATION: FunctionBlockInfoNotification,
    UMPStreamStatus.FUNCTION_BLOCK_NAME_NOTIFICATION: FunctionBlockNameNotification,
    UMPStreamStatus.START_OF_CLIP: StartOfClip,
    UMPStreamStatus.END_OF_CLIP: EndOfClip,
}
