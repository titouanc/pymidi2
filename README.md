# pymidi2

A pure Python implementation of MIDI2 Universal MIDI Packets (UMP).

**Note**: This project is currently incomplete, and serves as a workbench for other developments

Currently, it supports:

- Raw UMP endpoints over ALSA (linux)
- UMP endpoints over UDP (network / multiplatform)
    - Authentication (shared secret or user:password)
    - Network discovery via zeroconf (DNS-SD)
- Endpoint topology discovery via UMP Stream messages
- Reading Standard MIDI File version 1 (.mid)

## Installation

This project is managed with `uv`, make sure it is installed on your system.
On Archlinux for example:

```bash
pacman -S python-uv
```

Then clone this repository and ensure it works:

```bash
git clone git@github.com:titouanc/pymidi2
cd pymidi2
uv run pymidi2 --help
```

## Endpoint URLs

The UMP endpoints can be located with URLs. Two supported schemes:

- `file://` for raw UMP ALSA endpoints
- `udp://` for network endpoints

The UMP Group number (0-15) can be specified in the URL fragment (`...#<group>`).

Authentication for the UDP endpoints can be passed in the URL:

- `udp://<shared-key>@host`
- `udp://<username>:<password>@host`

Some valid examples:

- `file:///dev/snd/umpC2D0`
- `udp://my-host:5673` (no authentication)
- `udp://the-key@my-host:5673` (shared key authentication)
- `udp://user:password@my-host:5673#3` (user/password auth, UMP Group number 3)

## Command line tool

Run the command line tool with `uv run pymidi2`

Pass `-h / --help` to `pymidi2` or any of its subcommands to enquire about its
options and usage.

```
$ uv run pymidi2 -h
usage: pymidi2 [-h] [-I] [-D] {find,topo,play,send1} ...

positional arguments:
  {find,topo,play,send1}
    find                Find available UMP endpoints
    topo                Print UMP endpoint topology
    play                Play a MIDI file
    send1               Send MIDI1 events

options:
  -h, --help            show this help message and exit
  -I, --info            Enable info logging (default: False)
  -D, --debug           Enable debug logging (default: False)
```

### `find`: Finding available Universal MIDI Endpoints

To find all UMP endpoints that can be reached through all supported transports:

```
$ uv run pymidi2 find
Zephyr-UDP-MIDI2 (udp://192.168.129.35:53982)
- Block #0 [io : Recv/Send] 'Synthesizer' UMP groups {0, 1, 2, 3} [MIDI1 + MIDI2]
- Block #1 [i- : Recv     ] 'Keyboard' UMP groups {8} [MIDI1 only]
- Block #2 [-o :      Send] 'External output (MIDI DIN-5)' UMP groups {9} [MIDI1 31.25kb/s]
```

### `topo`: Viewing a particular endpoint's topology

If a UDP endpoint requires authentication, you can request its topology by
passing the authentication credentials in the url with `pymidi2 topo`

```
$ uv run pymidi2 topo udp://user:password@192.168.129.35:53982
Zephyr-UDP-MIDI2 (udp://192.168.129.35:53982)
- Block #0 [io : Recv/Send] 'Synthesizer' UMP groups {0, 1, 2, 3} [MIDI1 + MIDI2]
- Block #1 [i- : Recv     ] 'Keyboard' UMP groups {8} [MIDI1 only]
- Block #2 [-o :      Send] 'External output (MIDI DIN-5)' UMP groups {9} [MIDI1 31.25kb/s]
```

### `play`: Playing a MIDI file

Pass the option `-q / --quiet` to suppress MIDI1 events being printed to stdout.

```
$ uv run pymidi2 play -e 'udp://192.168.129.35:53982#9' under-the-sea.mid
BE0750
8D3E40
902264
9E2264
...
```

### `send1`: Sending MIDI1 events

Pass one or more MIDI1 events, in hexadecimal form

```
$ uv run pymidi2 send1 udp://192.168.129.35:53982#9 90407F 90427F 90457F
```

### `recv1`: Receiving MIDI1 events

This prints out only MIDI1 events from a single UMP group, in MIDI1 format.
Pass an endpoint url including the UMP group.

```
$ uv run pymidi2 recv1 udp://192.0.2.1:45486#9
904060
804060
904060
...
```

### `send2`: Sending MIDI2 events

Pass one or more UMP, in hexadecimal form. Separate the 32-bit words of a same
packet by commas,.

```
 $ uv run pymidi2 send2 udp://192.168.129.35:53982 49904000,FFFF0000 2990427F
```

### `recv2`: Receiving MIDI2 events

This prints out all Universal MIDI Packets from an endpoint, in UMP format.
Pass an endpoint url, if specifying the UMP group, then only packets from this
group are printed.

```
$ uv run pymidi2 recv2 udp://192.0.2.1:45486
29904060
29804060
29904060
...
```

## Reference documents

* [**User Datagram Protocol for Universal MIDI Packets** _Network MIDI 2.0 (UDP) Transport Specification_](https://drive.google.com/file/d/1dtsOgMLbtif9Fp-OaZhwnRs9an4dn3uv/edit)

* [**Universal MIDI Packet (UMP) Format and MIDI 2.0 Protocol** _With MIDI 1.0 Protocol in UMP Format_](https://drive.google.com/file/d/1l2L5ALHj4K9hw_LalQ2jJZBMXDxc9Uel/view)
