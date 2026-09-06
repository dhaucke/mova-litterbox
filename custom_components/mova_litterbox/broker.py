"""Transparent MQTT-over-TLS proxy standing in front of MOVA's real cloud
broker.

The litter box's WiFi module doesn't validate the broker's TLS
certificate properly (confirmed by direct testing against the real
device), so it accepts our self-signed one without complaint. Rather
than terminating the connection here (which would leave the official
MOVAhome app unable to see the device as online), this relays every
MQTT packet through to MOVA's real broker in both directions - the
device and the app both keep working normally, and we get to read
(and eventually inject) every message along the way.

Requires a one-time manual DNS rewrite (in your router/AdGuard/Pi-hole)
pointing eu.iot.mova-tech.com and the device's own MQTT subdomain
(shown in its /pair/ handshake, e.g. 20000.mt.eu.iot.mova-tech.com) at
this Home Assistant instance - not something this integration can
configure on your network for you.
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

MQTT_PUBLISH = 3
MQTT_DISCONNECT = 14

# 1+2+4+8+16+30 = ~61s of retrying a transient WAN outage before giving up.
UPSTREAM_CONNECT_RETRIES = 6


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


def build_server_ssl_context(cert_path: Path, key_path: Path) -> ssl.SSLContext:
    """Build the TLS *server* context (for the device connecting to us).

    Blocking (disk I/O) - run via executor.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert_path), str(key_path))
    return ctx


def resolve_public(hostname: str, dns_servers: list[str]) -> str:
    """Resolve hostname via a public DNS server, bypassing the local
    resolver entirely.

    We rewrote this exact hostname locally to point at ourselves, so the
    system resolver (or anything upstream of it, like a router-wide
    AdGuard/Pi-hole rule) can't be trusted for looking up where the real
    MOVA server actually is - it would just point back at us again.
    Blocking (network I/O) - run via executor.
    """
    import dns.resolver

    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = dns_servers
    answer = resolver.resolve(hostname, "A")
    return str(answer[0])


async def _read_mqtt_packet(reader: asyncio.StreamReader) -> tuple[int, bytes, bytes] | None:
    """Read one full MQTT packet. Returns (packet_type, payload, raw_bytes)."""
    header = await reader.readexactly(1)
    first_byte = header[0]
    packet_type = first_byte >> 4

    multiplier = 1
    remaining_len = 0
    len_bytes = b""
    while True:
        b = await reader.readexactly(1)
        len_bytes += b
        byte = b[0]
        remaining_len += (byte & 0x7F) * multiplier
        if (byte & 0x80) == 0:
            break
        multiplier *= 128

    payload = await reader.readexactly(remaining_len) if remaining_len else b""
    return packet_type, payload, header + len_bytes + payload


def _parse_publish(first_byte: int, payload: bytes) -> tuple[str, bytes]:
    topic_len = struct.unpack(">H", payload[0:2])[0]
    topic = payload[2:2 + topic_len].decode("utf-8", "replace")
    rest = payload[2 + topic_len:]
    qos = (first_byte >> 1) & 0x03
    if qos > 0:
        rest = rest[2:]
    return topic, rest


class MovaLocalBroker:
    """Accepts the device's connection and transparently proxies it to
    MOVA's real broker, inspecting (and one day: injecting) messages."""

    def __init__(
        self,
        ssl_context: ssl.SSLContext,
        port: int,
        upstream_host: str,
        upstream_port: int,
        upstream_ip: str,
        on_message: Callable[[dict], None],
    ) -> None:
        self._port = port
        self._upstream_host = upstream_host
        self._upstream_port = upstream_port
        self._upstream_ip = upstream_ip
        self._on_message = on_message
        self._ctx = ssl_context
        self._server: asyncio.base_events.Server | None = None
        # Built once (not per-connection): plain SSLContext, not
        # create_default_context(), so it never touches the system trust
        # store - which is blocking disk I/O and we ignore it anyway since
        # verification is disabled (the device's DNS is already forcibly
        # redirected here; we trust whatever answers on that IP).
        self._upstream_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._upstream_ctx.check_hostname = False
        self._upstream_ctx.verify_mode = ssl.CERT_NONE

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, host="0.0.0.0", port=self._port, ssl=self._ctx
        )
        _LOGGER.info(
            "MOVA local proxy listening on 0.0.0.0:%s, relaying to %s (%s:%s)",
            self._port, self._upstream_host, self._upstream_ip, self._upstream_port,
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_client(
        self, device_reader: asyncio.StreamReader, device_writer: asyncio.StreamWriter
    ) -> None:
        peer = device_writer.get_extra_info("peername")
        _LOGGER.debug("Connection from %s", peer)

        upstream_reader = upstream_writer = None
        delay = 1
        for attempt in range(UPSTREAM_CONNECT_RETRIES):
            try:
                upstream_reader, upstream_writer = await asyncio.open_connection(
                    self._upstream_ip,
                    self._upstream_port,
                    ssl=self._upstream_ctx,
                    server_hostname=self._upstream_host,
                )
                break
            except Exception:  # pylint: disable=broad-except
                # Most commonly a transient WAN outage (e.g. the nightly
                # forced reconnect German ISPs do) - keep retrying with
                # backoff instead of giving up until HA is restarted.
                if attempt == UPSTREAM_CONNECT_RETRIES - 1:
                    _LOGGER.exception(
                        "Could not reach real MOVA broker %s:%s for %s after %s attempts",
                        self._upstream_ip, self._upstream_port, peer, UPSTREAM_CONNECT_RETRIES,
                    )
                    device_writer.close()
                    return
                _LOGGER.debug(
                    "Upstream connect attempt %s/%s failed for %s, retrying in %ss",
                    attempt + 1, UPSTREAM_CONNECT_RETRIES, peer, delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

        try:
            await asyncio.gather(
                self._relay(device_reader, upstream_writer, "device->cloud"),
                self._relay(upstream_reader, device_writer, "cloud->device"),
            )
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error proxying connection for %s", peer)
        finally:
            device_writer.close()
            upstream_writer.close()
            _LOGGER.debug("Connection from %s closed", peer)

    async def _relay(
        self,
        src: asyncio.StreamReader,
        dst: asyncio.StreamWriter,
        direction: str,
    ) -> None:
        while True:
            packet = await _read_mqtt_packet(src)
            if packet is None:
                break
            packet_type, payload, raw = packet

            dst.write(raw)
            await dst.drain()

            if packet_type == MQTT_PUBLISH:
                try:
                    _, msg = _parse_publish(raw[0], payload)
                    data = json.loads(msg)
                    self._on_message(data)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.debug("Unparsed PUBLISH (%s): %r", direction, payload)
            elif packet_type == MQTT_DISCONNECT:
                break
