import ipaddress
import re

_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*")
_PCT = r"%[0-9A-Fa-f]{2}"
_UNRESERVED_SUB = r"A-Za-z0-9\-._~!$&'()*+,;="
_USERINFO = re.compile(rf"(?:[{_UNRESERVED_SUB}:]|{_PCT})*")
_REG_NAME = re.compile(rf"(?:[{_UNRESERVED_SUB}]|{_PCT})*")
_PATH = re.compile(rf"(?:[{_UNRESERVED_SUB}:@/]|{_PCT})*")
_QUERY = re.compile(rf"(?:[{_UNRESERVED_SUB}:@/?]|{_PCT})*")
_PORT = re.compile(r"[0-9]*")
_IPV_FUTURE = re.compile(rf"[vV][0-9A-Fa-f]+\.[{_UNRESERVED_SUB}:]+")


def _host(host: str) -> bool:
    if host.startswith("[") and host.endswith("]"):
        literal = host[1:-1]

        if _IPV_FUTURE.fullmatch(literal):
            return True

        try:
            ipaddress.IPv6Address(literal)
        except ValueError:
            return False

        return "%" not in literal

    return _REG_NAME.fullmatch(host) is not None


def _authority(authority: str) -> bool:
    userinfo, at, hostport = authority.rpartition("@")

    if at and not _USERINFO.fullmatch(userinfo):
        return False

    if hostport.startswith("["):
        end = hostport.find("]")

        if end < 0:
            return False

        host, rest = hostport[: end + 1], hostport[end + 1 :]

        if rest and not (rest.startswith(":") and _PORT.fullmatch(rest[1:])):
            return False

        return _host(host)

    host, colon, port = hostport.partition(":")

    return _host(host) and (not colon or _PORT.fullmatch(port) is not None)


def is_uri(val: str) -> bool:
    """Whether `val` is an absolute URI under RFC 3986, the JSON Schema `uri` format.

    >>> is_uri("https://example.com/a?b#c")
    True
    >>> is_uri("relative/path")
    False
    """
    scheme, colon, rest = val.partition(":")

    if not colon or not _SCHEME.fullmatch(scheme):
        return False

    rest, hash_, fragment = rest.partition("#")

    if hash_ and not _QUERY.fullmatch(fragment):
        return False

    rest, mark, query = rest.partition("?")

    if mark and not _QUERY.fullmatch(query):
        return False

    if rest.startswith("//"):
        authority, slash, path = rest[2:].partition("/")
        return _authority(authority) and _PATH.fullmatch(slash + path) is not None

    return _PATH.fullmatch(rest) is not None
