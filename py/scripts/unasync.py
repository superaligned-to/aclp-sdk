import re
import sys
from pathlib import Path

from generate import ROOT, ruff_format

PAIRS = {
    ROOT / "src/aclp/_async_http.py": ROOT / "src/aclp/_sync_http.py",
    ROOT / "src/aclp/_async_client.py": ROOT / "src/aclp/_sync_client.py",
}

RULES = [
    (r"\basync with\b", "with"),
    (r"\basync def\b", "def"),
    (r"\bawait ", ""),
    (r"\b__aenter__\b", "__enter__"),
    (r"\b__aexit__\b", "__exit__"),
    (r"\bAsyncClient\b", "Client"),
    (r"\bdiscover_async\b", "discover"),
    (r"\b_async_io\b", "_sync_io"),
    (r"\b_async_http\b", "_sync_http"),
]

HEADER = "# Generated from {src} by scripts/unasync.py; edit the async source instead.\n"


def render(src: Path) -> str:
    text = src.read_text()

    for pattern, repl in RULES:
        text = re.sub(pattern, repl, text)

    return ruff_format(HEADER.format(src=src.name) + text)


def main() -> int:
    check = "--check" in sys.argv[1:]
    stale = [
        (src, dst)
        for src, dst in PAIRS.items()
        if not dst.exists() or dst.read_text() != render(src)
    ]

    if check:
        for _, dst in stale:
            print(f"{dst.relative_to(ROOT)} is stale; run scripts/unasync.py", file=sys.stderr)
        return 1 if stale else 0

    for src, dst in stale:
        dst.write_text(render(src))

    return 0


if __name__ == "__main__":
    sys.exit(main())
