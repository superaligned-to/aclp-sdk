import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Every CPython release that has not reached end of life; 3.10 ended in October 2026.
PYTHONS = ("3.11", "3.12", "3.13", "3.14")

# Free-threaded builds are supported from 3.14; their result is informational until stable.
FREE_THREADED = "3.14t"


def step(*cmd: str, cwd: Path = ROOT) -> None:
    print(f"$ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def readme_snippet(tmp: Path) -> Path:
    code = re.search(r"```python\n(.*?)```", (ROOT / "README.md").read_text(), re.S)

    if code is None:
        raise SystemExit("README.md has no Python example")

    path = tmp / "readme_example.py"
    path.write_text(code.group(1))
    return path


def wheel_suite(py: str, wheel: Path, reqs: Path, tmp: Path) -> None:
    env = tmp / f"venv-{py}"
    python = str(env / "bin/python")

    step("uv", "venv", "--quiet", "--python", py, str(env))
    step("uv", "pip", "install", "--quiet", "--python", python, "-r", str(reqs), str(wheel))
    step(python, "-c", "import aclp, sys; sys.exit('site-packages' not in aclp.__file__)")
    step(python, "-m", "pytest", "-q", "-p", "no:cacheprovider")


def main() -> int:
    step("uv", "run", "--locked", "ruff", "format", "--check", ".")
    step("uv", "run", "--locked", "ruff", "check", ".")
    step("uv", "run", "--locked", "python", "scripts/generate.py", "--check")
    step("uv", "run", "--locked", "python", "scripts/unasync.py", "--check")
    step("uv", "run", "--locked", "mypy")

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        step("uv", "run", "--locked", "mypy", "--strict", str(readme_snippet(tmp)))

        reqs = tmp / "test-requirements.txt"
        audit = tmp / "requirements.txt"
        step(
            "uv",
            "export",
            "--locked",
            "--quiet",
            "--no-emit-project",
            "--only-group",
            "test",
            "-o",
            str(reqs),
        )
        step(
            "uv",
            "export",
            "--locked",
            "--quiet",
            "--no-emit-project",
            "--all-groups",
            "-o",
            str(audit),
        )
        step(
            "uv",
            "run",
            "--locked",
            "pip-audit",
            "--disable-pip",
            "--require-hashes",
            "--progress-spinner",
            "off",
            "-r",
            str(audit),
        )

        dist = tmp / "dist"
        step("uv", "build", "--quiet", "--out-dir", str(dist))
        wheel = next(dist.glob("*.whl"))

        for py in PYTHONS:
            wheel_suite(py, wheel, reqs, tmp)

        try:
            wheel_suite(FREE_THREADED, wheel, reqs, tmp)
        except subprocess.CalledProcessError:
            print(f"informational: the {FREE_THREADED} suite failed", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
