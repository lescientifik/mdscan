---
description: Agent instructions and project overview for mdscan.
---

# mdscan

CLI tool that scans `.md` files and displays YAML frontmatter `description` fields.
Built for AI agents to discover documentation without reading entire files.

## Subcommands

- `mdscan scan [dir]` — list files with descriptions (default)
- `mdscan check-links [dir]` — verify all .md files reachable from entrypoint
- `mdscan tree [dir]` — display document link graph
- `mdscan coverage [dir]` — documentation completeness stats
- `mdscan set-description <file> <desc>` — write/update frontmatter description

## Project layout

- `src/mdscan/` — source code (cli, scanner, formatter, config, tree, links, frontmatter)
- `tests/` — pytest integration & unit tests
- `pyproject.toml` — project config, `[tool.mdscan]` section for CLI defaults

## Docs

- [CLI audit](docs/cli-audit.md) — analysis against clig.dev and agent CLI design principles
- [Plan v0.3](docs/plan-cli-v0.3.md) — implementation plan for CLI improvements
- [Plan v0.2](docs/plan-v0.2.md) — previous plan (config, tree, coverage, all-links)
- [Demo](demo.md) — interactive demo of all CLI features

## Dev workflow

```bash
uv run pytest              # tests
uv run ruff check .        # lint
uv run ty check            # type check
uv run mdscan check-links  # verify doc reachability
```
