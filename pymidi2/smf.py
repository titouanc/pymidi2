from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

# See https://ccrma.stanford.edu/~craig/14q/midifile/MidiFileFormat.html
# also https://www.blitter.com/~russtopia/MIDI/~jglatt/tech/midifile.htm

MIDI1_EVLEN = {
    0x80: 3,  # Note off
    0x90: 3,  # Note on
    0xA0: 3,  # Polyphonic key pressure
    0xB0: 3,  # Control Change
    0xC0: 2,  # Program Change
    0xD0: 2,  # Channel pressure
    0xE0: 3,  # Pitch bend
    0xF1: 2,  # MIDI Time code
    0xF2: 3,  # Song position pointer
    0xF3: 2,  # Song select
    0xF6: 1,  # Tune request
    0xF8: 1,  # Timing clock
    0xFA: 1,  # Start
    0xFB: 1,  # Continue
    0xFC: 1,  # Stop
    0xFE: 1,  # Active sensing
    0xFF: 1,  # Reset
}


def get_varint(data: bytes) -> tuple[int, bytes]:
    res = 0
    for i in range(len(data)):
        res <<= 7
        res |= data[i] & 0x7F
        if data[i] & 0x80 == 0:
            return res, data[i + 1 :]
    return res, b""


def get_midi(data: bytes) -> tuple[bytes, bytes]:
    for i in range(1, len(data)):
        if data[i] & 0x80:
            return data[:i], data[i:]
    return data, b""


@dataclass
class Event:
    delta_time: int
    data: bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> tuple[Event, bytes]:
        t, data = get_varint(data)

        if data[0] == 0xFF:
            metatype = data[1]
            evlen, data = get_varint(data[2:])
            meta_event = MetaEvent(
                delta_time=t,
                meta_type=MetaEvent.MetaType(metatype),
                data=data[:evlen],
            )
            return meta_event, data[evlen:]

        elif data[0] in {0xF0, 0xF7}:
            for i in range(1, len(data)):
                if data[i] == 0xF7:
                    return SysexEvent(delta_time=t, data=data[1:i]), data[i + 1 :]

        evlen = MIDI1_EVLEN[data[0] & 0xF0 if data[0] < 0xF0 else data[0]]
        return MIDIEvent(delta_time=t, data=data[:evlen]), data[evlen:]


class SysexEvent(Event):
    pass


class MIDIEvent(Event):
    pass


@dataclass
class MetaEvent(Event):
    class MetaType(IntEnum):
        SEQUENCE_NUMBER = 0x00
        TEXT_EVENT = 0x01
        COPYRIGHT_NOTICE = 0x02
        SEQUENCE_OR_TRACK_NAME = 0x03
        INSTRUMENT_NAME = 0x04
        LYRICS_TEXT = 0x05
        MARKER_TEXT = 0x06
        CUE_POINT = 0x07
        CHANNEL_PREFIX_ASSIGNMENT = 0x20
        END_OF_TRACK = 0x2F
        TEMPO_SETTING = 0x51
        SMPTE_OFFSET = 0x54
        TIME_SIGNATURE = 0x58
        KEY_SIGNATURE = 0x59
        SEQUENCER_SPECIFIC = 0x7F

    meta_type: MetaType


@dataclass
class Track:
    events: list[Event]

    @classmethod
    def from_io(cls, io):
        mtrk, tlen = struct.unpack(">II", io.read(8))
        if mtrk != 0x4D54726B:
            raise ValueError("Expected 'MTrk' magic")

        events = []
        track_data = io.read(tlen)
        while track_data:
            event, track_data = Event.from_bytes(track_data)
            events.append(event)
        return cls(events=events)


@dataclass
class File:
    division: int
    tracks: list[Track]

    @classmethod
    def open(cls, path: str):
        with Path(path).open("rb") as fd:
            return cls.from_io(fd)

    @classmethod
    def from_io(cls, io):
        mthd, hlen, fmt, ntracks, division = struct.unpack(">IIHHH", io.read(14))
        if mthd != 0x4D546864:
            raise ValueError("Expected 'MThd' magic")

        if hlen != 6:
            raise ValueError("Expected header len of 6")

        return cls(
            division=division,
            tracks=[Track.from_io(io) for i in range(ntracks)],
        )

    def __iter__(self):
        tick = 0
        track_i = len(self.tracks) * [0]
        track_dt = len(self.tracks) * [0]

        to_yield = []

        while True:
            min_dt = 0

            while min_dt == 0:
                # Get next event for each track
                events = [
                    (t.events[i] if i < len(t.events) else None)
                    for t, i in zip(self.tracks, track_i)
                ]

                if not any(events):
                    return

                min_dt = min(
                    e.delta_time - track_dt[i]
                    for i, e in enumerate(events)
                    if e is not None
                )

                tick += min_dt
                for i, e in enumerate(events):
                    if e and e.delta_time - track_dt[i] == min_dt:
                        to_yield.append(e)
                        track_i[i] += 1
                        track_dt[i] = 0
                    else:
                        track_dt[i] += min_dt
            yield tick / self.division, to_yield
            to_yield = []
