"""Home-Assistant-style ONVIF WS-Discovery on the local LAN.

Sends a WS-Discovery Probe for ``NetworkVideoTransmitter`` devices and returns
host IPs found on the network. Credentials and RTSP profile URLs are filled in
by the user (same as HA's ONVIF / Generic Camera flow).
"""

from __future__ import annotations

import re
import socket
import struct
import uuid
from typing import List, Set
from urllib.parse import urlparse

from ..utils.logging import get_logger

log = get_logger("roomos.video.onvif")

_WS_DISCOVERY_ADDR = ("239.255.255.250", 3702)
_PROBE_TYPES = "dn:NetworkVideoTransmitter"
_PROBE_BODY = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
  xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
  xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery">
  <soap:Header>
    <wsa:MessageID>uuid:{uuid.uuid4()}</wsa:MessageID>
    <wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>
  </soap:Header>
  <soap:Body>
    <wsd:Probe>
      <wsd:Types>{_PROBE_TYPES}</wsd:Types>
    </wsd:Probe>
  </soap:Body>
</soap:Envelope>""".encode("utf-8")

_XADDR_RE = re.compile(
    r"<[^>]*XAddrs[^>]*>([^<]+)</[^>]*XAddrs[^>]*>",
    re.IGNORECASE,
)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _extract_hosts_from_payload(payload: str) -> Set[str]:
    hosts: Set[str] = set()
    for match in _XADDR_RE.findall(payload):
        for part in match.split():
            try:
                parsed = urlparse(part.strip())
                if parsed.hostname and not parsed.hostname.startswith("127."):
                    hosts.add(parsed.hostname)
            except Exception:
                pass
    for ip in _IP_RE.findall(payload):
        if not ip.startswith("127.") and not ip.startswith("169.254."):
            hosts.add(ip)
    return hosts


def discover_onvif_hosts(*, timeout_sec: float = 2.5) -> List[str]:
    """Return sorted LAN IPs that responded to an ONVIF WS-Discovery Probe."""
    seen: Set[str] = set()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.settimeout(0.35)
        ttl = struct.pack("b", 2)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        sock.sendto(_PROBE_BODY, _WS_DISCOVERY_ADDR)

        import time

        end = time.monotonic() + max(0.5, float(timeout_sec))
        while time.monotonic() < end:
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(min(0.4, remaining))
            try:
                data, _addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                continue
            seen.update(_extract_hosts_from_payload(text))
    except OSError as e:
        log.debug("ONVIF WS-Discovery failed: %s", e)
    finally:
        try:
            sock.close()
        except Exception:
            pass

    hosts = sorted(seen)
    if hosts:
        log.info("ONVIF WS-Discovery found %d host(s): %s", len(hosts), ", ".join(hosts))
    return hosts
