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


class StreamFormat(IntEnum):
    COMPLETE = 0
    START = 1
    CONTINUE = 2
    END = 3

    @property
    def is_starting(self):
        return self in {self.COMPLETE, self.START}

    @property
    def is_ending(self):
        return self in {self.COMPLETE, self.END}


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
    class Status(IntEnum):
        NOOP = 0x0
        JR_CLOCK = 0x1
        JR_TIMESTAMP = 0x2
        DELTA_CLOCKSTAMP_TPQ = 0x3
        DELTA_CLOCKSTAMP = 0x4

    status: Status = field(init=False)

    def __post_init__(self):
        self.mt = MessageType.UTILITY

    @classmethod
    def parse(cls, words, **kwargs):
        status = cls.Status((words[0] >> 20) & 0xF)
        return UTILITY_BY_STATUS[status].parse(words, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.status << 20


@dataclass
class NoOp(Utility):
    def __post_init__(self):
        super().__post_init__()
        self.status = Utility.Status.NOOP

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(**kwargs)


@dataclass
class JRClock(Utility):
    timestamp: int

    def __post_init__(self):
        super().__post_init__()
        self.status = Utility.Status.JR_CLOCK

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
        self.status = Utility.Status.JR_TIMESTAMP

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(timestamp=words[0] & 0xFFFFF, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.timestamp & 0xFFFFF


# System Real Time Messages
@dataclass
class SystemRealTime(UMP):
    class Status(IntEnum):
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

    status: Status = field(init=False)

    def __post_init__(self):
        self.mt = MessageType.SYSTEM_REAL_TIME

    @classmethod
    def parse(cls, words, **kwargs):
        status = SystemRealTime.Status((words[0] >> 16) & 0xFF)
        return SYSTEM_RT_BY_STATUS.get(status, cls).parse(words, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.status << 16


@dataclass
class MIDITimeCode(SystemRealTime):
    class TimeUnit(IntEnum):
        FRAME_LOW_NIBBLE = 0
        FRAME_HIGH_NIBBLE = 1
        SECONDS_LOW_NIBBLE = 2
        SECONDS_HIGH_NIBBLE = 3
        MINUTES_LOW_NIBBLE = 4
        MINUTES_HIGH_NIBBLE = 5
        HOURS_LOW_NIBBLE = 6
        RATE_AND_HOURS_HIGH_NIBBLE = 7

    type: TimeUnit
    value: int

    def __post_init__(self):
        super().__post_init__()
        self.status = SystemRealTime.Status.MIDI_TIME_CODE

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            type=cls.TimeUnit((words[0] >> 12) & 0x07),
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
        self.status = SystemRealTime.Status.SONG_POSITION_POINTER

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
    class Status(IntEnum):
        NOTE_OFF = 0x8
        NOTE_ON = 0x9
        POLY_PRESSURE = 0xA
        CONTROL_CHANGE = 0xB
        PROGRAM_CHANGE = 0xC
        CHANNEL_PRESSURE = 0xD
        PITCH_BEND = 0xE

    group: int
    status: Status = field(init=False)
    channel: int

    def __post_init__(self):
        self.mt = MessageType.MIDI_1_CHANNEL_VOICE

    @property
    def midi1(self) -> bytes:
        """Return the message contained in this UMP in MIDI1 format"""
        raise NotImplementedError()

    @classmethod
    def parse(cls, words, **kwargs):
        group = (words[0] >> 24) & 0xF
        status = cls.Status((words[0] >> 20) & 0xF)
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
        self.status = MIDI1ChannelVoice.Status.NOTE_OFF

    @property
    def midi1(self) -> bytes:
        return bytes([(self.status << 4) | self.channel, self.note, self.velocity])

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
        self.status = MIDI1ChannelVoice.Status.NOTE_ON

    @property
    def midi1(self) -> bytes:
        return bytes([(self.status << 4) | self.channel, self.note, self.velocity])

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
        self.status = MIDI1ChannelVoice.Status.CONTROL_CHANGE

    @property
    def midi1(self) -> bytes:
        return bytes([(self.status << 4) | self.channel, self.controller, self.value])

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
        self.status = MIDI1ChannelVoice.Status.PROGRAM_CHANGE

    @property
    def midi1(self) -> bytes:
        return bytes([(self.status << 4) | self.channel, self.program])

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
        self.status = MIDI1ChannelVoice.Status.PITCH_BEND

    @property
    def midi1(self) -> bytes:
        msb = self.value >> 7
        lsb = self.value & 0x7F
        return bytes([(self.status << 4) | self.channel, lsb, msb])

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
    class Status(IntEnum):
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

    group: int
    status: Status = field(init=False)
    channel: int

    def __post_init__(self):
        self.mt = MessageType.MIDI_2_CHANNEL_VOICE

    @classmethod
    def parse(cls, words, **kwargs):
        group = (words[0] >> 24) & 0xF
        status = cls.Status((words[0] >> 20) & 0xF)
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
        self.status = MIDI2ChannelVoice.Status.NOTE_OFF

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
        self.status = MIDI2ChannelVoice.Status.NOTE_ON

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
        self.status = MIDI2ChannelVoice.Status.CONTROL_CHANGE

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
        self.status = MIDI2ChannelVoice.Status.PROGRAM_CHANGE

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
        self.status = MIDI2ChannelVoice.Status.PITCH_BEND

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
    status: StreamFormat
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
            status=StreamFormat((words[0] >> 20) & 0xF),
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
    status: StreamFormat
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
            status=StreamFormat((words[0] >> 20) & 0xF),
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
    class StatusBank(IntEnum):
        SETUP_AND_PERFORMANCE_EVENTS = 0x00
        METADATA_TEXT = 0x01
        PERFORMANCE_TEXT_EVENTS = 0x02

    group: int
    form: StreamFormat
    address: int
    channel: int
    status_bank: StatusBank = field(init=False)

    def __post_init__(self):
        self.mt = MessageType.FLEX_DATA

    @classmethod
    def parse(cls, words, **kwargs):
        status_bank = cls.StatusBank((words[0] >> 8) & 0xFF)
        return FLEX_DATA_BY_STATUS_BANK[status_bank].parse(
            words,
            group=(words[0] >> 24) & 0xF,
            form=StreamFormat((words[0] >> 22) & 0x3),
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
    class Status(IntEnum):
        SET_TEMPO = 0x00
        SET_TIME_SIGNATURE = 0x01
        SET_METRONOME = 0x02
        SET_KEY_SIGNATURE = 0x05
        SET_CHORD_NAME = 0x06
        TEXT_EVENT = 0x10

    status: Status

    def __post_init__(self):
        self.status_bank = FlexData.StatusBank.SETUP_AND_PERFORMANCE_EVENTS

    @classmethod
    def parse(cls, words, status, **kwargs):
        return cls(status=cls.Status(status))

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.status


@dataclass
class MetadataText(FlexData):
    class Status(IntEnum):
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

    status: Status

    def __post_init__(self):
        self.status_bank = FlexData.StatusBank.METADATA_TEXT

    @classmethod
    def parse(cls, words, status, **kwargs):
        return cls(status=cls.Status(status))

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.status


@dataclass
class PerformanceTextEvent(FlexData):
    class Status(IntEnum):
        UNKNOWN = 0x00
        LYRICS = 0x01
        LYRICS_LANGUAGE = 0x02
        RUBY = 0x03
        RUBY_LANGUAGE = 0x04

    status: Status

    def __post_init__(self):
        self.status_bank = FlexData.StatusBank.PERFORMANCE_TEXT_EVENTS

    @classmethod
    def parse(cls, words, status, **kwargs):
        return cls(status=cls.Status(status))

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= self.status


# UMP Stream Messages (keeping your existing implementation)
@dataclass
class UMPStream(UMP):
    class Status(IntEnum):
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

    form: StreamFormat
    status: Status = field(init=False)

    def __post_init__(self):
        self.mt = MessageType.UMP_STREAM

    @classmethod
    def parse(cls, words, **kwargs):
        form = StreamFormat((words[0] >> 26) & 0x03)
        status = UMPStream.Status((words[0] >> 16) & 0x3FF)
        return UMP_STREAM_BY_STATUS[status].parse(words, form=form, **kwargs)

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.form << 26) | (self.status << 16)


@dataclass
class EndpointDiscovery(UMPStream):
    class Filter(IntFlag):
        ENDPOINT_INFO_NOTIFICATION = 1 << 0
        DEVICE_IDENTITY_NOTIFICATION = 1 << 1
        ENDPOINT_NAME_NOTIFICATION = 1 << 2
        PRODUCT_INSTANCE_ID_NOTIFICATION = 1 << 3
        STREAM_CONFIGURATION_NOTIFICATION = 1 << 4
        ALL = 0x1F

    ump_version: tuple[int, int]
    filter: Filter

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStream.Status.ENDPOINT_DISCOVERY

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            ump_version=((words[0] >> 8) & 0xFF, words[0] & 0xFF),
            filter=cls.Filter(words[1] & 0x1F),
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.ump_version[0] << 8) | self.ump_version[1]
        words[1] |= self.filter


@dataclass
class EndpointInfoNotification(UMPStream):
    ump_version: tuple[int, int]
    static: bool
    n_function_blocks: int
    midi2: bool
    midi1: bool
    rxjr: bool
    txjr: bool

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStream.Status.ENDPOINT_INFO_NOTIFICATION

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            ump_version=((words[0] >> 8) & 0xFF, words[0] & 0xFF),
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
        words[0] |= (self.ump_version[0] << 8) | self.ump_version[1]
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
        self.status = UMPStream.Status.DEVICE_IDENTITY_NOTIFICATION
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
            (family_lsb, family_msb, model_lsb, model_msb),
            byteorder="big",
        )
        words[3] = int.from_bytes(self.software_revision, byteorder="big")


@dataclass
class EndpointNameNotification(UMPStream):
    name: str

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStream.Status.ENDPOINT_NAME_NOTIFICATION

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
        self.status = UMPStream.Status.PRODUCT_INSTANCE_ID_NOTIFICATION

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

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStream.Status.STREAM_CONFIGURATION_REQUEST

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            protocol=(words[0] >> 8) & 0xFF,
            extensions=bool(words[0] & (1 << 7)),
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.protocol << 8) | (self.extensions << 7)


@dataclass
class StreamConfigurationNotification(UMPStream):
    protocol: int
    extensions: bool

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStream.Status.STREAM_CONFIGURATION_NOTIFICATION

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            protocol=(words[0] >> 8) & 0xFF,
            extensions=bool(words[0] & (1 << 7)),
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.protocol << 8) | (self.extensions << 7)


@dataclass
class FunctionBlockDiscovery(UMPStream):
    class Filter(IntFlag):
        FUNCTION_BLOCK_INFO = 1 << 0
        FUNCTION_BLOCK_NAME = 1 << 1
        ALL = 0x03

    block_num: int
    filter: Filter

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStream.Status.FUNCTION_BLOCK_DISCOVERY

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            block_num=(words[0] >> 8) & 0xFF,
            filter=words[0] & 0xFF,
            **kwargs,
        )

    def encode_into(self, words: list[int]) -> None:
        super().encode_into(words)
        words[0] |= (self.block_num << 8) | self.filter


@dataclass
class FunctionBlockInfoNotification(UMPStream):
    class MIDI1Mode(IntEnum):
        NOT_MIDI1 = 0x00
        MIDI1 = 0x01
        MIDI1_RESTRICT_BANDWITH = 0x02

        @property
        def is_midi1(self):
            return self in {self.MIDI1, self.MIDI1_RESTRICT_BANDWITH}

        @property
        def is_restricted_31_25kbps(self):
            return self is self.MIDI1_RESTRICT_BANDWITH

    active: bool
    function_block_id: int
    ui_hint_sender: bool
    ui_hint_receiver: bool
    midi1: MIDI1Mode
    is_output: bool
    is_input: bool
    first_group: int
    number_of_groups: int
    midi_ci_version: int
    max_sysex_8_streams: int

    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStream.Status.FUNCTION_BLOCK_INFO_NOTIFICATION

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(
            active=bool((words[0] >> 15) & 1),
            function_block_id=(words[0] >> 8) & 0x7F,
            ui_hint_sender=bool((words[0] >> 5) & 1),
            ui_hint_receiver=bool((words[0] >> 4) & 1),
            midi1=cls.MIDI1Mode((words[0] >> 2) & 0x03),
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
            | (self.ui_hint_sender << 5)
            | (self.ui_hint_receiver << 4)
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
        self.status = UMPStream.Status.FUNCTION_BLOCK_NAME_NOTIFICATION

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
    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStream.Status.START_OF_CLIP

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(**kwargs)


@dataclass
class EndOfClip(UMPStream):
    def __post_init__(self):
        super().__post_init__()
        self.status = UMPStream.Status.END_OF_CLIP

    @classmethod
    def parse(cls, words, **kwargs):
        return cls(**kwargs)


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
    Utility.Status.NOOP: NoOp,
    Utility.Status.JR_CLOCK: JRClock,
    Utility.Status.JR_TIMESTAMP: JRTimestamp,
}

SYSTEM_RT_BY_STATUS = {
    SystemRealTime.Status.MIDI_TIME_CODE: MIDITimeCode,
    SystemRealTime.Status.SONG_POSITION_POINTER: SongPositionPointer,
}

MIDI1_BY_STATUS = {
    MIDI1ChannelVoice.Status.NOTE_OFF: MIDI1NoteOff,
    MIDI1ChannelVoice.Status.NOTE_ON: MIDI1NoteOn,
    MIDI1ChannelVoice.Status.CONTROL_CHANGE: MIDI1ControlChange,
    MIDI1ChannelVoice.Status.PROGRAM_CHANGE: MIDI1ProgramChange,
    MIDI1ChannelVoice.Status.PITCH_BEND: MIDI1PitchBend,
}

MIDI2_BY_STATUS = {
    MIDI2ChannelVoice.Status.NOTE_OFF: MIDI2NoteOff,
    MIDI2ChannelVoice.Status.NOTE_ON: MIDI2NoteOn,
    MIDI2ChannelVoice.Status.CONTROL_CHANGE: MIDI2ControlChange,
    MIDI2ChannelVoice.Status.PROGRAM_CHANGE: MIDI2ProgramChange,
    MIDI2ChannelVoice.Status.PITCH_BEND: MIDI2PitchBend,
}

FLEX_DATA_BY_STATUS_BANK = {
    FlexData.StatusBank.SETUP_AND_PERFORMANCE_EVENTS: SetupAndPerformanceEvent,
    FlexData.StatusBank.METADATA_TEXT: MetadataText,
    FlexData.StatusBank.PERFORMANCE_TEXT_EVENTS: PerformanceTextEvent,
}

UMP_STREAM_BY_STATUS = {
    UMPStream.Status.ENDPOINT_DISCOVERY: EndpointDiscovery,
    UMPStream.Status.ENDPOINT_INFO_NOTIFICATION: EndpointInfoNotification,
    UMPStream.Status.DEVICE_IDENTITY_NOTIFICATION: DeviceIdentityNotification,
    UMPStream.Status.ENDPOINT_NAME_NOTIFICATION: EndpointNameNotification,
    UMPStream.Status.PRODUCT_INSTANCE_ID_NOTIFICATION: ProductInstanceIdNotification,
    UMPStream.Status.STREAM_CONFIGURATION_REQUEST: StreamConfigurationRequest,
    UMPStream.Status.STREAM_CONFIGURATION_NOTIFICATION: StreamConfigurationNotification,
    UMPStream.Status.FUNCTION_BLOCK_DISCOVERY: FunctionBlockDiscovery,
    UMPStream.Status.FUNCTION_BLOCK_INFO_NOTIFICATION: FunctionBlockInfoNotification,
    UMPStream.Status.FUNCTION_BLOCK_NAME_NOTIFICATION: FunctionBlockNameNotification,
    UMPStream.Status.START_OF_CLIP: StartOfClip,
    UMPStream.Status.END_OF_CLIP: EndOfClip,
}
