from dataclasses import dataclass

from aclp._endpoint import Endpoint
from aclp._errors import InvalidResponseError, TransportError
from aclp._json import MAX_BODY_BYTES

MAX_LINE_BYTES = 16_384

MAX_HEAD_BYTES = 16_384


@dataclass(frozen=True, slots=True)
class Reply:
    status: int
    json: bool
    body: bytes


@dataclass(frozen=True, slots=True)
class Head:
    status: int
    headers: tuple[tuple[str, str], ...]

    def values(self, name: str) -> list[str]:
        return [v for k, v in self.headers if k == name]

    @property
    def json(self) -> bool:
        types = self.values("content-type")
        return len(types) == 1 and types[0].split(";", 1)[0].strip().lower() == "application/json"

    @property
    def chunked(self) -> bool:
        codings = ",".join(self.values("transfer-encoding")).split(",")
        return codings[-1].strip().lower() == "chunked"

    @property
    def length(self) -> int | None:
        vals = {v.strip() for v in self.values("content-length")}

        if not vals:
            return None

        if len(vals) > 1 or not all(v.isascii() and v.isdigit() for v in vals):
            raise TransportError("ACLP response has an invalid Content-Length")

        n = int(vals.pop())

        if n > MAX_BODY_BYTES:
            raise InvalidResponseError("ACLP response exceeds 1 MiB")

        return n

    @property
    def bodiless(self) -> bool:
        return self.status in (204, 304)


def request_head(method: str, ep: Endpoint, headers: list[tuple[str, str]], body: bytes) -> bytes:
    lines = [
        f"{method} {ep.target} HTTP/1.1",
        f"Host: {ep.authority}",
        "Connection: close",
        f"Content-Length: {len(body)}",
        *(f"{k}: {v}" for k, v in headers),
    ]
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")


def parse_status(line: bytes) -> int:
    parts = line.rstrip(b"\r\n").split(b" ", 2)

    if len(parts) < 2 or parts[0] not in (b"HTTP/1.1", b"HTTP/1.0"):
        raise TransportError("ACLP response has an invalid status line")

    code = parts[1]

    if len(code) != 3 or not code.isdigit():
        raise TransportError("ACLP response has an invalid status line")

    return int(code)


def parse_header(line: bytes) -> tuple[str, str]:
    name, colon, val = line.rstrip(b"\r\n").partition(b":")

    if not colon or not name or name != name.strip():
        raise TransportError("ACLP response has an invalid header")

    try:
        return name.decode("ascii").lower(), val.strip().decode("latin-1")
    except UnicodeError as err:
        raise TransportError("ACLP response has an invalid header") from err


def chunk_size(line: bytes) -> int:
    size = line.split(b";", 1)[0].strip()

    if not size or len(size) > 8 or size.strip(b"0123456789abcdefABCDEF"):
        raise TransportError("ACLP response has an invalid chunk")

    return int(size, 16)
