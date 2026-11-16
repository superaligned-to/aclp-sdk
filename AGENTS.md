# Repository rules

- One SDK per directory: `ts`, `rs`, `py`. Each is self-contained, with its own toolchain, lockfile, gate and `AGENTS.md`; read that file before changing the SDK.
- Protocol definitions belong in `superaligned-to/aclp`. Every SDK vendors the same schema and pins the same revision in its `protocol-source.json`; bump them together.
- Keep wire behavior at parity across SDKs. A wire fix in one SDK lands in the others in the same change, with a test in each. Run `cargo xtask interop ../ts` from `rs` after changing wire behavior.
- CI runs one workflow per SDK, filtered by path, plus `interop`. Releases are tag-driven: `ts-vX.Y.Z`, `rs-vX.Y.Z`, `py-vX.Y.Z`, each checked against the SDK's manifest version.
- Use one-line conventional commits with the SDK as scope where it applies, for example `fix(py): ...`.
