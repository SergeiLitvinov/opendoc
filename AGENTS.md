# OpenDoc contributor contract

OpenDoc is an independent Python library. Distribution and import: `opendoc`. JSON identifier: `opendoc.document`, write version 2, read versions 1 and 2. Consumers own adapters, migration of their legacy formats, user interfaces and task storage. Production modules may import only the standard library, OpenDoc and lazy optional `lxml`; never a consuming application.

[Coding standards](CODING_STANDARDS.md) define the enforced rules. Required order: `uv sync --all-extras` → `uv run ruff check` → `uv run ruff format --check` → `uv run pytest`. Verify a dependency-free wheel in an empty environment with `tools/check_wheel.py`. MathML fingerprinting uses the optional `math` extra.

Behavior belongs to `docs/guide/`, future work only to `TODO.md`. Never hand-edit `docs/reference/`: run `uv run python -m tools.docs generate`, then `uv run python -m tools.docs check`. Navigation uses AST, direct test imports are not coverage claims. Preview: `uv run python -m tools.docs serve` (127.0.0.1:8003). Generated files belong to `.opendoc/`.
