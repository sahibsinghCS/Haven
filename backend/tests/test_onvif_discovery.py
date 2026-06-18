"""Tests for ONVIF WS-Discovery host extraction."""

from roomos.video.onvif_discovery import _extract_hosts_from_payload


def test_extract_hosts_from_xaddrs() -> None:
    payload = """
    <d:ProbeMatches>
      <d:ProbeMatch>
        <d:XAddrs>http://192.168.1.55:80/onvif/device_service</d:XAddrs>
      </d:ProbeMatch>
    </d:ProbeMatches>
    """
    hosts = _extract_hosts_from_payload(payload)
    assert "192.168.1.55" in hosts


def test_extract_hosts_ignores_loopback() -> None:
    payload = "<d:XAddrs>http://127.0.0.1:80/</d:XAddrs>"
    hosts = _extract_hosts_from_payload(payload)
    assert "127.0.0.1" not in hosts
