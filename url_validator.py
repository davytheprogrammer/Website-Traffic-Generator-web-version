"""URL validation for configured, explicitly authorized test origins."""

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit


def normalize_host(value: str) -> str:
    """Normalize a configured DNS name or IP address for exact comparisons."""
    value = value.strip().rstrip(".").lower()
    if not value:
        return ""
    try:
        return ipaddress.ip_address(value).compressed
    except ValueError:
        pass
    try:
        ascii_host = value.encode("idna").decode("ascii")
    except UnicodeError:
        return ""
    if len(ascii_host) > 253 or not all(
        label and len(label) <= 63 and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
        for label in ascii_host.split(".")
    ):
        return ""
    return ascii_host


def normalize_origin(value: str) -> str | None:
    """Normalize an exact HTTP(S) origin; paths and wildcard hosts are rejected."""
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except (AttributeError, ValueError):
        return None
    scheme = parsed.scheme.lower()
    host = normalize_host(parsed.hostname or "")
    if (
        scheme not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        return None
    default_port = 443 if scheme == "https" else 80
    authority = f"[{host}]" if ":" in host else host
    if port is not None and port != default_port:
        authority = f"{authority}:{port}"
    return f"{scheme}://{authority}"


def validate_url(url: str, allowed_origins: set[str]) -> tuple[bool, str, str | None]:
    """Validate syntax and exact-origin authorization without making a request."""
    if not isinstance(url, str) or not url.strip():
        return False, "Enter a target URL.", None
    url = url.strip()
    if len(url) > 2048:
        return False, "The URL is too long (maximum 2048 characters).", None

    try:
        parsed = urlsplit(url)
        host = normalize_host(parsed.hostname or "")
        # Accessing .port validates malformed and out-of-range port values.
        port = parsed.port
    except ValueError:
        return False, "The URL contains an invalid hostname or port.", None

    if parsed.scheme.lower() not in {"http", "https"}:
        return False, "Use an http:// or https:// URL.", None
    if not host or not parsed.netloc:
        return False, "Enter a complete URL with a hostname.", None
    if parsed.username is not None or parsed.password is not None:
        return False, "Credentials in URLs are not allowed.", None
    if port is not None and not 1 <= port <= 65535:
        return False, "The URL port is out of range.", None

    normalized_allowed = {origin for item in allowed_origins if (origin := normalize_origin(item))}
    request_origin = normalize_origin(f"{parsed.scheme}://{parsed.netloc}")
    if request_origin not in normalized_allowed:
        if not normalized_allowed:
            return False, "No authorized origins are configured. Set LOADTEST_ALLOWED_ORIGINS first.", None
        return False, f"{request_origin or 'This URL origin'} is not in the configured authorized-origin list.", None

    # Normalize only the host; preserve the owner's path and query as supplied.
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    normalized_url = urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))
    return True, "Target is syntactically valid and its origin is allowlisted.", normalized_url
