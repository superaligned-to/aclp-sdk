import re
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from conftest import free_port

README = Path(__file__).parent.parent / "README.md"


def test_readme_example_prints_what_it_promises() -> None:
    text = README.read_text()
    code = re.search(r"```python\n(.*?)```", text, re.S)
    promised = re.search(r"```text\n(.*?)\n```", text, re.S)

    assert code is not None
    assert promised is not None

    out = StringIO()

    with redirect_stdout(out):
        exec(code.group(1).replace("8787", str(free_port())), {"__name__": "readme"})  # noqa: S102  # runs the repository's own README

    assert out.getvalue().strip() == promised.group(1)
