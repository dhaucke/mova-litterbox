"""Embedded local MQTT-over-TLS server standing in for MOVA's cloud broker.

The litter box's WiFi module doesn't validate the broker's TLS
certificate properly (confirmed by direct testing against the real
device), so a self-signed certificate is accepted - no vendor CA
needed. This implements just enough MQTT (CONNECT/CONNACK,
SUBSCRIBE/SUBACK, PINGREQ/PINGRESP, PUBLISH) for the device to stay
"connected" and keep reporting properties.

Requires a one-time manual DNS rewrite (in your router/AdGuard/Pi-hole)
pointing eu.iot.mova-tech.com and its per-device MQTT subdomain
(shown in the device's own /pair/ handshake, e.g.
20000.mt.eu.iot.mova-tech.com) at this Home Assistant instance - not
something this integration can configure on your network for you.
"""
from __future__ import annotations

import asyncio
import json
import logging
import ssl
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

_LOGGER = logging.getLogger(__name__)

MQTT_CONNECT = 1
MQTT_PUBLISH = 3
MQTT_SUBSCRIBE = 8
MQTT_PINGREQ = 12
MQTT_DISCONNECT = 14


def ensure_self_signed_cert(cert_path: Path, key_path: Path, common_name: str) -> None:
    """Generate a self-signed cert/key pair if they don't already exist."""
    if cert_path.exists() and key_path.exists():
        return
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc).replace(year=datetime.now().year + 5))
        .sign(key, hashes.SHA256())
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


async def _read_remaining_length(reader: asyncio.StreamReader) -> int | None:
    multiplier = 1
    value = 0
    while True:
        b = await reader.readexactly(1)
        byte = b[0]
        value += (byte & 0x7F) * multiplier
        if (byte & 0x80) == 0:
            break
        multiplier *= 128
    return value


def _parse_publish(first_byte: int, payload: bytes) -> tuple[str, bytes]:
    topic_len = struct.unpack(">H", payload[0:2])[0]
    topic = payload[2:2 + topic_len].decode("utf-8", "replace")
    rest = payload[2 + topic_len:]
    qos = (first_byte >> 1) & 0x03
    if qos > 0:
        rest = rest[2:]
    return topic, rest


class MovaLocalBroker:
    """One embedded TLS+MQTT listener per config entry."""

    def __init__(
        self,
        cert_path: Path,
        key_path: Path,
        port: int,
        on_message: Callable[[dict], None],
    ) -> None:
        self._port = port
        self._on_message = on_message
        self._ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._ctx.load_cert_chain(str(cert_path), str(key_path))
        self._server: asyncio.base_events.Server | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, host="0.0.0.0", port=self._port, ssl=self._ctx
        )
        _LOGGER.info("MOVA local broker listening on 0.0.0.0:%s", self._port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        _LOGGER.debug("Connection from %s", peer)
        try:
            while True:
                header = await reader.readexactly(1)
                first_byte = header[0]
                packet_type = first_byte >> 4
                remaining_len = await _read_remaining_length(reader)
                payload = await reader.readexactly(remaining_len) if remaining_len else b""

                if packet_type == MQTT_CONNECT:
                    writer.write(bytes([0x20, 0x02, 0x00, 0x00]))
                    await writer.drain()
                elif packet_type == MQTT_SUBSCRIBE:
                    pkt_id = payload[0:2]
                    writer.write(bytes([0x90, 0x03]) + pkt_id + bytes([0x00]))
                    await writer.drain()
                elif packet_type == MQTT_PUBLISH:
                    topic, msg = _parse_publish(first_byte, payload)
                    try:
                        data = json.loads(msg)
                        self._on_message(data)
                    except Exception:  # pylint: disable=broad-except
                        _LOGGER.debug("Unparsed PUBLISH on %s: %r", topic, msg)
                elif packet_type == MQTT_PINGREQ:
                    writer.write(bytes([0xD0, 0x00]))
                    await writer.drain()
                elif packet_type == MQTT_DISCONNECT:
                    break
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error handling MOVA device connection from %s", peer)
        finally:
            writer.close()
            _LOGGER.debug("Connection from %s closed", peer)
