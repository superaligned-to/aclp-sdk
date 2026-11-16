import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from aclp._errors import ConfigError
from aclp.events import ClientInfo

_HEADER = re.compile(r"[\t\x20-\x7e]*")

_TARGET = re.compile(r"[\x21-\x7e]+")


@dataclass(frozen=True, slots=True)
class Endpoint:
    tls: bool
    name: str
    host: str
    port: int
    authority: str
    target: str

    def with_path(self, path: str) -> "Endpoint":
        return Endpoint(self.tls, self.name, self.host, self.port, self.authority, path)


def parse_endpoint(url: str) -> Endpoint:
    """Parse an `http` or `https` URL without credentials or a fragment."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as err:
        raise ConfigError("ACLP endpoint URL is invalid") from err

    host = parts.hostname

    if (
        parts.scheme not in ("http", "https")
        or not host
        or "@" in parts.netloc
        or "#" in url
        or not header_value(parts.netloc)
        or not _TARGET.fullmatch((parts.path or "/") + parts.query)
    ):
        raise ConfigError(
            "ACLP requires an HTTP or HTTPS endpoint without URL credentials or a fragment"
        )

    tls = parts.scheme == "https"
    target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")

    return Endpoint(
        tls=tls,
        name=host,
        host="127.0.0.1" if host == "localhost" else host,
        port=port or (443 if tls else 80),
        authority=parts.netloc,
        target=target,
    )


def header_value(val: str) -> bool:
    return _HEADER.fullmatch(val) is not None


def _product(name: str, version: str | None) -> str:
    return name if version is None else f"{name}/{version}"


def client_header(client: ClientInfo) -> str:
    """Render `ClientInfo` as `ACLP-Client` product tokens: the client, then the harness."""
    tokens = [_product(client["name"], client.get("version"))]
    harness = client.get("harness")

    if harness is not None:
        tokens.append(_product(harness["name"], harness.get("version")))

    return " ".join(tokens)
