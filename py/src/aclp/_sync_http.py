# Generated from _async_http.py by scripts/unasync.py; edit the async source instead.
import ssl

from aclp import _sync_io as io
from aclp._endpoint import Endpoint
from aclp._errors import InvalidResponseError, TransportError
from aclp._http import (
    MAX_HEAD_BYTES,
    Head,
    Reply,
    chunk_size,
    parse_header,
    parse_status,
    request_head,
)
from aclp._json import MAX_BODY_BYTES


def _read_head(stream: io.Stream) -> Head:
    line = stream.readline()
    status = parse_status(line)
    size = len(line)
    headers: list[tuple[str, str]] = []

    while True:
        line = stream.readline()
        size += len(line)

        if size > MAX_HEAD_BYTES:
            raise TransportError("ACLP response head exceeds 16 KiB")

        if line in (b"\r\n", b"\n"):
            return Head(status, tuple(headers))

        headers.append(parse_header(line))


def _read_chunked(stream: io.Stream) -> bytes:
    body = bytearray()

    while True:
        n = chunk_size(stream.readline())

        if len(body) + n > MAX_BODY_BYTES:
            raise InvalidResponseError("ACLP response exceeds 1 MiB")

        if n == 0:
            break

        body += stream.readexactly(n)

        if stream.readexactly(2) != b"\r\n":
            raise TransportError("ACLP response has an invalid chunk")

    size = 0

    while (line := stream.readline()) not in (b"\r\n", b"\n"):
        size += len(line)

        if size > MAX_HEAD_BYTES:
            raise TransportError("ACLP response trailers exceed 16 KiB")

    return bytes(body)


def _read_to_eof(stream: io.Stream) -> bytes:
    body = bytearray()

    while chunk := stream.read(65_536):
        body += chunk

        if len(body) > MAX_BODY_BYTES:
            raise InvalidResponseError("ACLP response exceeds 1 MiB")

    return bytes(body)


def _read_body(stream: io.Stream, head: Head) -> bytes:
    if head.bodiless:
        return b""

    if head.chunked:
        return _read_chunked(stream)

    n = head.length

    if n is not None:
        return stream.readexactly(n)

    return _read_to_eof(stream)


def exchange(
    ep: Endpoint,
    ctx: ssl.SSLContext | None,
    method: str,
    headers: list[tuple[str, str]],
    body: bytes,
    deadline: float,
) -> Reply:
    stream = io.connect(ep, ctx, deadline)

    try:
        stream.write(request_head(method, ep, headers, body) + body)
        head = _read_head(stream)

        while 100 <= head.status < 200:
            if head.status == 101:
                raise TransportError("ACLP does not support HTTP protocol upgrades")

            head = _read_head(stream)

        return Reply(head.status, head.json, _read_body(stream, head))
    finally:
        stream.close()
