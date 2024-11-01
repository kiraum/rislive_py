# RIPE RIS Live Streaming Client

A Python client for monitoring BGP updates in real-time using the RIPE RIS Live service.

## Features

- Stream BGP updates from RIPE RIS collectors;
- Filter updates by various criteria;
- Support for IPv4 and IPv6 prefixes;
- Automatic reconnection on connection drops;
- Debug logging capabilities.

## Requirements

- Python 3.12+
- websockets library

## Installation

```bash
pip install websockets
```

## Usage

Basic usage:
```bash
» python3 rislive.py -h
usage: rislive.py [-h] [-H FILTER_HOST] [-t {UPDATE,OPEN,NOTIFICATION,KEEPALIVE,RIS_PEER_STATE}] [-k {announcements,withdrawals}] [-p FILTER_PEER] [-a FILTER_ASPATH] [-f FILTER_PREFIX] [-m] [-l] [-r] [-d] [-D]

Monitor the streams from RIPE RIS Live.

options:
  -h, --help            show this help message and exit
  -H, --host FILTER_HOST
                        Filter messages by a specific RRC (format: rrcXX).
  -t, --type {UPDATE,OPEN,NOTIFICATION,KEEPALIVE,RIS_PEER_STATE}
                        Filter messages by BGP or RIS type.
  -k, --key {announcements,withdrawals}
                        Filter messages containing a specific key ("announcements" or "withdrawals").
  -p, --peer FILTER_PEER
                        Filter messages by BGP peer IP address.
  -a, --aspath FILTER_ASPATH
                        Filter by AS path. Use "^" for start, "$" for end (e.g., "^123,456,789$").
  -f, --prefix FILTER_PREFIX
                        Filter UPDATE messages by IPv4/IPv6 prefix (e.g., 192.0.2.0/24 or 2001:db8::/32).
  -m, --more-specific   Match prefixes that are more specific (part of) the given prefix.
  -l, --less-specific   Match prefixes that are less specific (contain) the given prefix.
  -r, --include-raw     Include Base64-encoded original binary BGP message.
  -d, --disable-auto-reconnect
                        Disable auto-reconnect on connection drop.
  -D, --debug           Enable debug logging output.
```

## Examples

Filter updates for a specific prefix:
```bash
python rislive.py -f 192.0.2.0/24
```

Monitor specific RRC with debug logging:
```bash
python rislive.py -H rrc00 -D
```

Filter by AS path and message type:
```bash
python rislive.py -a "^64496,64497$" -t UPDATE
```

## Contributing

Contributions are welcome! Please ensure your code follows the existing style and includes appropriate tests.
