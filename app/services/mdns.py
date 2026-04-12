import logging
import os
import socket
from dataclasses import dataclass

from zeroconf import IPVersion, ServiceInfo, Zeroconf

from ..config import settings

logger = logging.getLogger(__name__)


def _detect_host_ip() -> str:
    if settings.service_advertise_host.strip():
        return settings.service_advertise_host.strip()
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp.connect(("8.8.8.8", 80))
        return udp.getsockname()[0]
    except OSError:
        pass
    finally:
        udp.close()
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


def _detect_port() -> int:
    if settings.service_advertise_port > 0:
        return settings.service_advertise_port
    web_port = os.getenv("WEB_PORT", "").strip()
    if web_port.isdigit() and int(web_port) > 0:
        return int(web_port)
    return 3000


@dataclass
class ServiceEndpoint:
    host: str
    port: int


class ServiceDiscoveryBroadcaster:
    def __init__(self) -> None:
        self._zeroconf: Zeroconf | None = None
        self._service_info: ServiceInfo | None = None
        self._endpoint: ServiceEndpoint | None = None

    def start(self) -> None:
        if not settings.service_discovery_enabled:
            return
        endpoint = ServiceEndpoint(host=_detect_host_ip(), port=_detect_port())
        service_type = settings.service_discovery_type
        if not service_type.endswith("."):
            service_type = f"{service_type}."
        instance_name = f"{settings.service_discovery_name}.{service_type}"
        properties = {
            b"host": endpoint.host.encode("utf-8"),
            b"mappedPort": str(endpoint.port).encode("utf-8"),
            b"url": f"http://{endpoint.host}:{endpoint.port}".encode("utf-8"),
        }
        self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self._service_info = ServiceInfo(
            type_=service_type,
            name=instance_name,
            addresses=[socket.inet_aton(endpoint.host)],
            port=endpoint.port,
            properties=properties,
            server=f"{settings.service_discovery_name.lower()}.local.",
        )
        self._zeroconf.register_service(self._service_info, allow_name_change=True)
        self._endpoint = endpoint
        logger.info("mDNS service registered: %s %s:%s", service_type, endpoint.host, endpoint.port)

    def stop(self) -> None:
        if self._zeroconf and self._service_info:
            try:
                self._zeroconf.unregister_service(self._service_info)
            finally:
                self._zeroconf.close()
        self._zeroconf = None
        self._service_info = None
        self._endpoint = None

    @property
    def endpoint(self) -> ServiceEndpoint | None:
        return self._endpoint
