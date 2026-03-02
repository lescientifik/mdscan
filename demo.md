---
description: Interactive demo of all mdscan CLI features with captured output.
---
# mdscan CLI Demo

*2026-03-02T16:02:26Z by Showboat 0.6.1*
<!-- showboat-id: 73fd9168-786c-4ff1-8a59-06701c6e3d76 -->

mdscan scans directories for .md files and displays their YAML frontmatter descriptions. It helps AI agents quickly discover relevant documentation without reading entire files.

## Setup

Create a sample docs/ directory with well-documented files, an undocumented file, a file with a too-long description, and a file in an excluded directory.

```bash
mkdir -p /tmp/demo_docs/guides /tmp/demo_docs/node_modules

cat > /tmp/demo_docs/api.md << 'INNER'
---
description: API gateway rate limiting strategies and configuration.
---
# API Gateway
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

echo "Done. Files created:"
find /tmp/demo_docs -name "*.md" | sort
```

```output
Done. Files created:
/tmp/demo_docs/api.md
/tmp/demo_docs/guides/deploy.md
/tmp/demo_docs/node_modules/lib.md
/tmp/demo_docs/notes.md
/tmp/demo_docs/setup.md
/tmp/demo_docs/verbose.md
```

## Basic scan

Scan the directory. Valid descriptions go to stdout, diagnostics to stderr. Exit code 1 because some files have issues.

```bash
mdscan /tmp/demo_docs 2>&1; echo "exit code: $?"
```

```output
warn: notes.md — missing YAML frontmatter description, no summary available
  fix: spawn ONE haiku agent to read notes.md and run `mdscan set-description notes.md "..."`
hint: verbose.md — description too long (160 words, max 150), truncated in output
  fix: spawn ONE haiku agent to read verbose.md and run `mdscan set-description verbose.md "..."` with a shorter description
api.md            API gateway rate limiting strategies and configuration.
guides/deploy.md  Step-by-step deployment guide for production environments.
setup.md          Development environment setup guide for new contributors.
verbose.md        word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word ...
exit code: 1
```

Note: node_modules/lib.md is silently excluded (hardcoded). verbose.md description is truncated to 150 words + "..." in output. Each fix message tells the agent exactly which file to handle and which command to run.

## JSON output

`--json` includes all files with `null` for missing descriptions. Useful for programmatic consumption.

```bash
mdscan --json /tmp/demo_docs 2>/dev/null
```

```output
[
  {
    "path": "api.md",
    "description": "API gateway rate limiting strategies and configuration."
  },
  {
    "path": "guides/deploy.md",
    "description": "Step-by-step deployment guide for production environments."
  },
  {
    "path": "notes.md",
    "description": null
  },
  {
    "path": "setup.md",
    "description": "Development environment setup guide for new contributors."
  },
  {
    "path": "verbose.md",
    "description": "word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word ..."
  }
]
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
mdscan set-description /tmp/demo_docs/verbose.md "word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word" 2>&1; echo "exit code: $?"
```

```output
hint: description too long (160 words, max 150)
  fix: spawn ONE haiku agent to read /tmp/demo_docs/verbose.md and run `mdscan set-description /tmp/demo_docs/verbose.md "..."` with a shorter description
wrote: /tmp/demo_docs/verbose.md
exit code: 1
```

## Depth limiting and custom ignores

```bash
echo "=== --max-depth 0 (root only) ==="
mdscan --max-depth 0 /tmp/demo_docs 2>/dev/null
echo ""
echo "=== --ignore \"notes*\" ==="
mdscan --ignore "notes*" /tmp/demo_docs 2>/dev/null
```

```output
=== --max-depth 0 (root only) ===
api.md      API gateway rate limiting strategies and configuration.
notes.md    Weekly team meeting notes and action items.
setup.md    Development environment setup guide for new contributors.
verbose.md  word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word ...

=== --ignore "notes*" ===
api.md            API gateway rate limiting strategies and configuration.
guides/deploy.md  Step-by-step deployment guide for production environments.
setup.md          Development environment setup guide for new contributors.
verbose.md        word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word ...
```

## Test suite

```bash
uv run pytest -q
```

```output
..................                                                       [100%]
18 passed in 0.67s
```

