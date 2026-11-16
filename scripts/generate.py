import hashlib
import json
import keyword
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypeAlias

ROOT = Path(__file__).resolve().parent.parent

SCHEMA = ROOT / "src/aclp/schema.json"

PIN = ROOT / "protocol-source.json"

EVENTS = ROOT / "src/aclp/events.py"

METHODS = ROOT / "src/aclp/_methods.py"

SKIP = {
    "ErrorResponse",
    "InvocationEnvelope",
    "NotificationEnvelope",
    "RequestEnvelope",
    "RpcError",
    "Schema",
    "StandardInvocation",
    "SuccessResponse",
}

SCALARS = {"string": "str", "integer": "int", "number": "float", "boolean": "bool", "null": "None"}

Node: TypeAlias = Mapping[str, Any]


def pascal(val: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in val.replace("-", "_").split("_"))


def ref_name(node: Node) -> str | None:
    ref = node.get("$ref")
    return ref.rsplit("/", 1)[1] if isinstance(ref, str) else None


def literal(vals: Sequence[object]) -> str:
    return "Literal[" + ", ".join(json.dumps(v) for v in vals) + "]"


class Generator:
    def __init__(self, defs: Mapping[str, Node]) -> None:
        self.defs = defs
        self.blocks: list[str] = []
        self.names: list[str] = []

    def is_scalar(self, name: str) -> bool:
        d = self.defs[name]
        return d.get("type") in SCALARS and "properties" not in d

    def type_of(self, node: Node) -> str:
        name = ref_name(node)

        if name == "Schema":
            return "JsonSchema"

        if name is not None:
            return self.type_of(self.defs[name]) if self.is_scalar(name) else name

        if "const" in node:
            return literal([node["const"]])

        enum = node.get("enum")

        if isinstance(enum, list):
            return literal(enum)

        for key in ("anyOf", "oneOf"):
            branches = node.get(key)

            if isinstance(branches, list) and "type" not in node:
                return " | ".join(dict.fromkeys(self.type_of(b) for b in branches))

        all_of = node.get("allOf")

        if isinstance(all_of, list) and "type" not in node:
            return self.type_of(all_of[0])

        kind = node.get("type")

        if kind == "array":
            items = node.get("items")
            return f"list[{self.type_of(items) if isinstance(items, Mapping) else 'JsonValue'}]"

        if isinstance(kind, str) and kind in SCALARS:
            return SCALARS[kind]

        return "JsonValue"

    def refined(self, node: Node, key: str, base: Node) -> str:
        weak = not base or (base.get("type") == "array" and "items" not in base)
        branches = node.get("oneOf")

        if not weak or not isinstance(branches, list):
            return self.type_of(base)

        types = []

        for b in branches:
            props = b.get("properties", {})

            if key in props:
                types.append(self.type_of(props[key]))

        return " | ".join(types) if types else self.type_of(base)

    def typed_dict(self, name: str, node: Node) -> None:
        props: Mapping[str, Node] = node.get("properties", {})
        required = set(node.get("required", []))
        fields = []

        for key, sub in props.items():
            typ = self.refined(node, key, sub)
            fields.append((key, typ if key in required else f"NotRequired[{typ}]"))

        if any(keyword.iskeyword(k) or not k.isidentifier() for k, _ in fields):
            body = ", ".join(f"{json.dumps(k)}: {t}" for k, t in fields)
            self.blocks.append(f"{name} = TypedDict({json.dumps(name)}, {{{body}}})")
        else:
            lines = "\n".join(f"    {k}: {t}" for k, t in fields) or "    pass"
            self.blocks.append(f"class {name}(TypedDict):\n{lines}")

        self.names.append(name)

    def variant_name(self, name: str, branch: Node, others: Sequence[Node]) -> str:
        for sub in branch.get("properties", {}).values():
            if isinstance(sub, Mapping) and isinstance(sub.get("const"), str):
                return name + pascal(sub["const"])

        own = set(branch.get("required", []))

        for o in others:
            own -= set(o.get("required", []))

        return name + "".join(pascal(k) for k in sorted(own))

    def definition(self, name: str) -> None:
        node = self.defs[name]
        branches = node.get("oneOf")

        if "properties" in node:
            self.typed_dict(name, node)
            return

        if isinstance(branches, list) and all("properties" in b for b in branches):
            variants = []

            for b in branches:
                others = [o for o in branches if o is not b]
                vname = self.variant_name(name, b, others)
                self.typed_dict(vname, b)
                variants.append(vname)

            self.blocks.append(f"{name}: TypeAlias = {' | '.join(variants)}")
            self.names.append(name)
            return

        if isinstance(branches, list):
            self.blocks.append(f"{name}: TypeAlias = {self.type_of(node)}")
            self.names.append(name)


def render_events(schema: Node, methods: Mapping[str, str]) -> str:
    defs: Mapping[str, Node] = schema["definitions"]
    gen = Generator(defs)

    for name in defs:
        if name in SKIP or name == "JsonValue" or gen.is_scalar(name):
            continue

        gen.definition(name)

    names = sorted([*gen.names, "EventMethod", "JsonSchema", "JsonValue"])
    head = [
        '"""Typed parameters for the standard ACLP events, generated from the pinned schema."""',
        "",
        "from collections.abc import Mapping, Sequence",
        "from typing import Literal, NotRequired, TypeAlias, TypedDict",
        "",
        "__all__ = [" + ", ".join(json.dumps(n) for n in names) + "]",
        "",
        'JsonValue: TypeAlias = "bool | int | float | str | Sequence[JsonValue] | Mapping[str, JsonValue] | None"',
        "",
        "JsonSchema: TypeAlias = bool | Mapping[str, JsonValue]",
        "",
        f"EventMethod: TypeAlias = {literal(sorted(methods))}",
    ]
    return "\n\n".join(["\n".join(head), *gen.blocks]) + "\n"


def render_methods(methods: Mapping[str, str]) -> str:
    rows = "\n".join(f"    {json.dumps(m)}: {json.dumps(d)}," for m, d in methods.items())
    return f"PARAMS = {{\n{rows}\n}}\n"


def methods_of(schema: Node) -> dict[str, str]:
    defs: Mapping[str, Node] = schema["definitions"]
    all_of: Sequence[Node] = defs["StandardInvocation"]["allOf"]
    out = {}

    for branch in all_of[1]["oneOf"]:
        props = branch["properties"]
        out[props["method"]["const"]] = props["params"]["$ref"].rsplit("/", 1)[1]

    return out


def _ruff(args: list[str], src: str) -> str:
    res = subprocess.run(
        [sys.executable, "-m", "ruff", *args, "--stdin-filename", "src/aclp/generated.py", "-"],
        input=src,
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    return res.stdout


def ruff_format(src: str) -> str:
    return _ruff(["format"], _ruff(["check", "--select", "I", "--fix", "--quiet"], src))


def main() -> int:
    check = "--check" in sys.argv[1:]
    raw = SCHEMA.read_bytes()
    pin = json.loads(PIN.read_text())

    if hashlib.sha256(raw).hexdigest() != pin["schemaSha256"]:
        print("schema.json does not match protocol-source.json", file=sys.stderr)
        return 1

    schema = json.loads(raw)
    methods = methods_of(schema)
    outputs = {
        EVENTS: ruff_format(render_events(schema, methods)),
        METHODS: ruff_format(render_methods(methods)),
    }
    stale = [p for p, src in outputs.items() if not p.exists() or p.read_text() != src]

    if check:
        for p in stale:
            print(f"{p.relative_to(ROOT)} is stale; run scripts/generate.py", file=sys.stderr)
        return 1 if stale else 0

    for p in stale:
        p.write_text(outputs[p])

    return 0


if __name__ == "__main__":
    sys.exit(main())
