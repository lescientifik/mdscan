---
description: Interactive demo of all mdscan CLI features with captured output.
---
# mdscan CLI Demo

*2026-03-02T20:42:10Z by Showboat 0.6.1*
<!-- showboat-id: fb58f15b-ea54-41ee-85de-ed8137c921a8 -->

mdscan scans directories for .md files and displays their YAML frontmatter descriptions. It helps AI agents quickly discover relevant documentation without reading entire files.

## Setup

Create a sample docs/ directory with linked files, a CLAUDE.md entrypoint, an undocumented file, a verbose file, and files in excluded directories.

```bash
rm -rf /tmp/demo_docs
mkdir -p /tmp/demo_docs/guides /tmp/demo_docs/node_modules /tmp/demo_docs/.claude

cat > /tmp/demo_docs/CLAUDE.md << 'INNER'
---
description: Project instructions for AI agents.
---
# Instructions
See [README](README.md) for project overview.
See [API docs](api.md) for gateway details.
INNER

cat > /tmp/demo_docs/README.md << 'INNER'
---
description: Project overview and getting started guide.
---
# My Project
See [setup](setup.md) to get started and [deploy](guides/deploy.md) for production.
INNER

cat > /tmp/demo_docs/api.md << 'INNER'
---
description: API gateway rate limiting strategies and configuration.
---
# API Gateway
See [setup](setup.md) for prerequisites.
INNER

cat > /tmp/demo_docs/setup.md << 'INNER'
---
description: Development environment setup guide for new contributors.
---
# Setup
INNER

cat > /tmp/demo_docs/guides/deploy.md << 'INNER'
---
description: Step-by-step deployment guide for production environments.
---
# Deployment
See [API config](../api.md) for gateway setup.
INNER

cat > /tmp/demo_docs/notes.md << 'INNER'
# Meeting Notes
No frontmatter here.
INNER

LONG=$(python3 -c "print(\" \".join([\"word\"] * 160))")
cat > /tmp/demo_docs/verbose.md << INNER
---
description: $LONG
---
# Verbose
INNER

cat > /tmp/demo_docs/node_modules/lib.md << 'INNER'
---
description: Should be ignored by mdscan.
---
INNER

cat > /tmp/demo_docs/.claude/settings.md << 'INNER'
---
description: Claude agent settings.
---
INNER

echo "Done. Files created:"
find /tmp/demo_docs -name "*.md" | sort
```

```output
Done. Files created:
/tmp/demo_docs/api.md
/tmp/demo_docs/CLAUDE.md
/tmp/demo_docs/.claude/settings.md
/tmp/demo_docs/guides/deploy.md
/tmp/demo_docs/node_modules/lib.md
/tmp/demo_docs/notes.md
/tmp/demo_docs/README.md
/tmp/demo_docs/setup.md
/tmp/demo_docs/verbose.md
```

## Basic scan

Scan the directory. Valid descriptions go to stdout with detected links, diagnostics to stderr. CLAUDE.md is excluded from the scan by default. Exit code 1 because some files have issues.

```bash
mdscan /tmp/demo_docs 2>&1; echo "exit code: $?"
```

```output
warn: 1 file missing YAML frontmatter description:
  - notes.md
  fix: for EACH file, have a dedicated agent (e.g. fast model like Haiku) read the file and run `mdscan set-description <file> "..."`
hint: 1 file with description too long (max 150 words), truncated in output:
  - verbose.md (160 words)
  fix: for EACH file, have a dedicated agent (e.g. fast model like Haiku) read the file and run `mdscan set-description <file> "..."` with a shorter description
README.md         Project overview and getting started guide.
                    → links: setup.md, guides/deploy.md
api.md            API gateway rate limiting strategies and configuration.
                    → links: setup.md
guides/deploy.md  Step-by-step deployment guide for production environments.
                    → links: ../api.md
setup.md          Development environment setup guide for new contributors.
verbose.md        word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word ...
exit code: 1
```

Note: CLAUDE.md, node_modules/lib.md and .claude/settings.md are excluded from the scan. Links between files appear as → lines below each description. Warnings are grouped by type with a single fix instruction per group.

## JSON output

`--json` includes all files with `null` for missing descriptions and a `links` array for each file.

```bash
mdscan --json /tmp/demo_docs 2>/dev/null
```

```output
[
  {
    "path": "README.md",
    "description": "Project overview and getting started guide.",
    "links": [
      "setup.md",
      "guides/deploy.md"
    ]
  },
  {
    "path": "api.md",
    "description": "API gateway rate limiting strategies and configuration.",
    "links": [
      "setup.md"
    ]
  },
  {
    "path": "guides/deploy.md",
    "description": "Step-by-step deployment guide for production environments.",
    "links": [
      "../api.md"
    ]
  },
  {
    "path": "notes.md",
    "description": null,
    "links": []
  },
  {
    "path": "setup.md",
    "description": "Development environment setup guide for new contributors.",
    "links": []
  },
  {
    "path": "verbose.md",
    "description": "word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word ...",
    "links": []
  }
]
```

## check-links — all reachable

Verify that every .md file is reachable from the entrypoint via link chains. CLAUDE.md is the default entrypoint when present.

```bash
mdscan check-links /tmp/demo_docs 2>&1; echo "exit code: $?"
```

```output
entrypoint: CLAUDE.md
warn: 2 files unreachable from CLAUDE.md (no link chain connects them):
  - notes.md
  - verbose.md
  fix: for EACH file, have a dedicated agent (e.g. smart model like Opus) review the file and either link it from a reachable doc, or confirm with the user that it can be removed
5/7 files reachable from CLAUDE.md
exit code: 1
```

notes.md and verbose.md are orphans — no link chain from CLAUDE.md reaches them. Both appear in a single grouped warning with one fix instruction. The fix messages distinguish fast tasks (broken links → Haiku) from smart tasks (orphan review → Opus).

## check-links — broken link

Introduce a broken link to see the diagnostic.

```bash
cat > /tmp/demo_docs/api.md << 'INNER'
---
description: API gateway rate limiting strategies and configuration.
---
# API Gateway
See [setup](setup.md) for prerequisites.
See [auth docs](auth.md) for authentication.
INNER

mdscan check-links /tmp/demo_docs 2>&1; echo "exit code: $?"
```

```output
entrypoint: CLAUDE.md
warn: 2 files unreachable from CLAUDE.md (no link chain connects them):
  - notes.md
  - verbose.md
  fix: for EACH file, have a dedicated agent (e.g. smart model like Opus) review the file and either link it from a reachable doc, or confirm with the user that it can be removed
warn: 1 broken link (target file not found):
  - api.md → auth.md
  fix: for EACH source file, have a dedicated agent (e.g. fast model like Haiku) fix or remove its broken links
5/7 files reachable from CLAUDE.md
exit code: 1
```

## check-links — explicit entrypoint

Use `--entrypoint` to override the default CLAUDE.md entrypoint.

```bash
mdscan check-links --entrypoint README.md /tmp/demo_docs 2>&1; echo "exit code: $?"
```

```output
entrypoint: README.md
warn: 3 files unreachable from README.md (no link chain connects them):
  - CLAUDE.md
  - notes.md
  - verbose.md
  fix: for EACH file, have a dedicated agent (e.g. smart model like Opus) review the file and either link it from a reachable doc, or confirm with the user that it can be removed
warn: 1 broken link (target file not found):
  - api.md → auth.md
  fix: for EACH source file, have a dedicated agent (e.g. fast model like Haiku) fix or remove its broken links
4/7 files reachable from README.md
exit code: 1
```

## check-links — with --ignore

Use `--ignore` to exclude files from the scan. Useful for files that are intentionally unlinked (e.g. meeting notes, drafts). Restore api.md first.

```bash
cat > /tmp/demo_docs/api.md << 'INNER'
---
description: API gateway rate limiting strategies and configuration.
---
# API Gateway
See [setup](setup.md) for prerequisites.
INNER

mdscan check-links --ignore "notes.md" --ignore "verbose.md" /tmp/demo_docs 2>&1; echo "exit code: $?"
```

```output
entrypoint: CLAUDE.md
5/5 files reachable from CLAUDE.md
exit code: 0
```

## Fixing missing frontmatter with set-description

Each file gets its own agent. The agent reads the file and runs `mdscan set-description`.

```bash
mdscan set-description /tmp/demo_docs/notes.md "Weekly team meeting notes and action items."
echo "---"
cat /tmp/demo_docs/notes.md
```

```output
wrote: /tmp/demo_docs/notes.md
---
---
description: Weekly team meeting notes and action items.
---
# Meeting Notes
No frontmatter here.
```

## Too-long description triggers a hint

set-description still writes the file, but exits 1 and tells the agent to rewrite.

```bash
mdscan set-description /tmp/demo_docs/verbose.md "$(python3 -c "print(\" \".join([\"word\"] * 160))")" 2>&1; echo "exit code: $?"
```

```output
hint: description too long (160 words, max 150)
  fix: have ONE agent (e.g. fast model like Haiku) read /tmp/demo_docs/verbose.md and run `mdscan set-description /tmp/demo_docs/verbose.md "..."` with a shorter description
wrote: /tmp/demo_docs/verbose.md
exit code: 1
```

## Depth limiting and custom ignores

`--ignore` patterns match against both filenames and relative paths, so `guides/*` excludes everything under the guides/ subdirectory.

```bash
echo "=== --max-depth 0 (root only) ==="
mdscan --max-depth 0 /tmp/demo_docs 2>/dev/null
echo ""
echo "=== --ignore \"notes*\" ==="
mdscan --ignore "notes*" /tmp/demo_docs 2>/dev/null
echo ""
echo "=== --ignore \"guides/*\" (relative path) ==="
mdscan --ignore "guides/*" /tmp/demo_docs 2>/dev/null
```

```output
=== --max-depth 0 (root only) ===
README.md   Project overview and getting started guide.
              → links: setup.md, guides/deploy.md
api.md      API gateway rate limiting strategies and configuration.
              → links: setup.md
notes.md    Weekly team meeting notes and action items.
setup.md    Development environment setup guide for new contributors.
verbose.md  word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word ...

=== --ignore "notes*" ===
README.md         Project overview and getting started guide.
                    → links: setup.md, guides/deploy.md
api.md            API gateway rate limiting strategies and configuration.
                    → links: setup.md
guides/deploy.md  Step-by-step deployment guide for production environments.
                    → links: ../api.md
setup.md          Development environment setup guide for new contributors.
verbose.md        word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word ...

=== --ignore "guides/*" (relative path) ===
README.md   Project overview and getting started guide.
              → links: setup.md, guides/deploy.md
api.md      API gateway rate limiting strategies and configuration.
              → links: setup.md
notes.md    Weekly team meeting notes and action items.
setup.md    Development environment setup guide for new contributors.
verbose.md  word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word ...
```

## Test suite

```bash
uv run pytest -q
```

```output
...................................                                      [100%]
35 passed in 1.75s
```
