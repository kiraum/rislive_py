#!/usr/bin/env python3
"""RIPE RIS Live streaming client for monitoring BGP updates."""

import argparse
import asyncio
import ipaddress
import json
import logging
import re
import signal
import ssl
from typing import Any, Dict, Optional

from websockets.legacy.client import WebSocketClientProtocol, connect


def validate_rrc(value: str) -> list:
    """Validate RRC host format."""
    rrc_list = [rrc.strip() for rrc in value.split(",")]
    for rrc in rrc_list:
        if not re.match(r"^rrc\d{2}$", rrc):
            raise argparse.ArgumentTypeError(f"Invalid RRC format '{rrc}'. Must be in format 'rrcXX' where X is a digit")
    return rrc_list


def validate_peer(value: str) -> str:
    """Validate peer IP address."""
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Invalid IP address format") from exc


def validate_aspath(value: str) -> list:
    """Validate AS path format."""
    path_list = [path.strip() for path in value.split(",")]
    validated_paths = []
    for path in path_list:
        clean_path = path.strip("^$")
        try:
            for asn in clean_path.split(","):
                if asn:
                    asn_int = int(asn)
                    if not (0 <= asn_int <= 4294967295):
                        raise ValueError
            validated_paths.append(path)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid AS path format in '{path}'. Must be comma-separated ASNs") from exc
    return validated_paths


def validate_prefix(value: str) -> list:
    """Validate network prefix."""
    prefix_list = [prefix.strip() for prefix in value.split(",")]
    validated_prefixes = []
    for prefix in prefix_list:
        if "/" not in prefix:
            raise argparse.ArgumentTypeError(f"Network prefix '{prefix}' must include mask in CIDR notation (e.g. 192.0.2.0/24 or 2001:db8::/32)")
        try:
            ipaddress.ip_network(prefix, strict=False)
            validated_prefixes.append(prefix)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid network prefix format: {prefix}") from exc
    return validated_prefixes


class RipeRisStreamer:
    """A class for streaming updates from the RIPE RIS Live project"""

    def __init__(self, options: argparse.Namespace):
        """
        Initialize the RipeRisStreamer.

        Args:
            options (argparse.Namespace): Command-line arguments.
        """
        self._options = options
        self._ws: Optional[WebSocketClientProtocol] = None
        self._sslcontext = ssl.create_default_context()
        self._sslcontext.check_hostname = False
        self._sslcontext.verify_mode = ssl.CERT_NONE

    # [Previous methods remain unchanged]
    async def start_streaming(self) -> None:
        """Start streaming data from RIPE RIS Live."""
        uri = "wss://ris-live.ripe.net/v1/ws/?client=RipeRisStreamer"
        logging.debug("Creating websocket connection...")
        async with connect(uri, ssl=self._sslcontext) as websocket:
            self._ws = websocket
            logging.debug("Sending RIS parameters...")
            logging.debug("RIS parameters: %s ", {self._get_ris_params()})
            await websocket.send(self._get_ris_params())
            print("Listening...")
            logging.debug("Starting the reception loop...")
            async for message in websocket:
                try:
                    print(message)
                except ValueError as e:
                    print(f"Error processing message: {str(e)}")

    def _get_ris_params(self) -> str:
        """Generate RIS parameters based on command-line options."""
        params: Dict[str, Any] = {
            "socketOptions": {"includeRaw": bool(self._options.include_raw)},
            "moreSpecific": bool(self._options.more_specific),
            "lessSpecific": bool(self._options.less_specific),
            "autoReconnect": not self._options.disable_auto_reconnect,
        }

        optional_params = {
            "host": self._options.filter_host[0] if self._options.filter_host else None,
            "type": self._options.filter_type,
            "require": (self._options.filter_key[0] if self._options.filter_key else None),
            "peer": self._options.filter_peer,
            "path": (",".join(self._options.filter_aspath) if self._options.filter_aspath else None),
            "prefix": (self._options.filter_prefix if self._options.filter_prefix else None),
        }

        params.update({k: v for k, v in optional_params.items() if v is not None})
        return json.dumps({"type": "ris_subscribe", "data": params})

    async def disconnect(self) -> bool:
        """Disconnect from the websocket."""
        if self._ws:
            await self._ws.close()
        return True


async def handle_shutdown(streamer: RipeRisStreamer, loop: asyncio.AbstractEventLoop) -> None:
    """Handle shutdown signals gracefully."""
    try:
        print("Disconnecting...")
        await streamer.disconnect()
    except ConnectionError as e:
        print(f"Error during disconnect: {str(e)}")
    print("Shutting down...")
    for task in asyncio.all_tasks(loop):
        if task is not asyncio.current_task():
            task.cancel()


async def main() -> int:
    """Main function to run the RIPE RIS Live streamer."""
    parser = argparse.ArgumentParser(description="Monitor the streams from RIPE RIS Live.")

    parser.add_argument(
        "-H",
        "--host",
        dest="filter_host",
        type=validate_rrc,
        help="Filter messages by a specific RRC (format: rrcXX).",
    )
    parser.add_argument(
        "-t",
        "--type",
        dest="filter_type",
        choices=["UPDATE", "OPEN", "NOTIFICATION", "KEEPALIVE", "RIS_PEER_STATE"],
        help="Filter messages by BGP or RIS type.",
    )
    parser.add_argument(
        "-k",
        "--key",
        dest="filter_key",
        choices=["announcements", "withdrawals"],
        help='Filter messages containing a specific key ("announcements" or "withdrawals").',
    )

    parser.add_argument(
        "-p",
        "--peer",
        dest="filter_peer",
        type=validate_peer,
        help="Filter messages by BGP peer IP address.",
    )
    parser.add_argument(
        "-a",
        "--aspath",
        dest="filter_aspath",
        type=validate_aspath,
        help='Filter by AS path. Use "^" for start, "$" for end (e.g., "^123,456,789$").',
    )
    parser.add_argument(
        "-f",
        "--prefix",
        dest="filter_prefix",
        type=validate_prefix,
        help="Filter UPDATE messages by IPv4/IPv6 prefix (e.g., 192.0.2.0/24 or 2001:db8::/32).",
    )

    # [Rest of the arguments remain unchanged]
    parser.add_argument(
        "-m",
        "--more-specific",
        action="store_true",
        help="Match prefixes that are more specific (part of) the given prefix.",
    )
    parser.add_argument(
        "-l",
        "--less-specific",
        action="store_true",
        help="Match prefixes that are less specific (contain) the given prefix.",
    )
    parser.add_argument(
        "-r",
        "--include-raw",
        action="store_true",
        help="Include Base64-encoded original binary BGP message.",
    )
    parser.add_argument(
        "-d",
        "--disable-auto-reconnect",
        action="store_true",
        help="Disable auto-reconnect on connection drop.",
    )
    parser.add_argument(
        "-D",
        "--debug",
        action="store_true",
        help="Enable debug logging output.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    streamer = RipeRisStreamer(args)

    async def shutdown():
        print("\nDisconnecting...")
        await streamer.disconnect()
        print("Shutting down...")
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        asyncio.get_event_loop().stop()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown()))

    try:
        while not args.disable_auto_reconnect:
            try:
                await streamer.start_streaming()
            except asyncio.CancelledError:
                break
            except ConnectionError as e:
                print(f"Streamer encountered an error: {str(e)}")
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
