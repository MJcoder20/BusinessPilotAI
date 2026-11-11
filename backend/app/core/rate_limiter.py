import ipaddress

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def get_client_ip(request: Request) -> str:
    """Identify clients safely behind Render's Cloudflare proxy."""

    if settings.app_env == "production":
        forwarded_ip = request.headers.get("cf-connecting-ip")

        if forwarded_ip:
            try:
                return str(ipaddress.ip_address(forwarded_ip.strip()))
            except ValueError:
                pass

    return get_remote_address(request)


limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[],
    headers_enabled=True,
)
