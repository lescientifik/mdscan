---
description: Interactive demo of all mdscan CLI features with captured output.
---
# mdscan CLI Demo

*2026-03-02T19:52:21Z by Showboat 0.6.1*
<!-- showboat-id: 8e0cc05c-7c17-4c12-8b4d-4cb6718c863e -->

mdscan scans directories for .md files and displays their YAML frontmatter descriptions. It helps AI agents quickly discover relevant documentation without reading entire files.

## Setup

Create a sample docs/ directory with linked files, a CLAUDE.md entrypoint, an undocumented file, a verbose file, and a file in an excluded directory.

```bash
rm -rf /tmp/demo_docs
mkdir -p /tmp/demo_docs/guides /tmp/demo_docs/node_modules

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

echo "Done. Files created:"
find /tmp/demo_docs -name "*.md" | sort
```

```output
Done. Files created:
/tmp/demo_docs/api.md
/tmp/demo_docs/CLAUDE.md
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
warn: notes.md — missing YAML frontmatter description, no summary available
  fix: have ONE agent (e.g. fast model like Haiku) read notes.md and run `mdscan set-description notes.md "..."`
hint: verbose.md — description too long (160 words, max 150), truncated in output
  fix: have ONE agent (e.g. fast model like Haiku) read verbose.md and run `mdscan set-description verbose.md "..."` with a shorter description
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

Note: CLAUDE.md and node_modules/lib.md are excluded from the scan. Links between files appear as → lines below each description. Each fix message tells the agent exactly which file to handle.

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
warn: notes.md — unreachable from CLAUDE.md (no link chain connects them)
  fix: have ONE agent (e.g. smart model like Opus) review this file and either link it from a reachable doc, or confirm with the user that it can be removed
warn: verbose.md — unreachable from CLAUDE.md (no link chain connects them)
  fix: have ONE agent (e.g. smart model like Opus) review this file and either link it from a reachable doc, or confirm with the user that it can be removed
5/7 files reachable from CLAUDE.md
exit code: 1
```

notes.md and verbose.md are orphans — no link chain from CLAUDE.md reaches them. The fix messages distinguish fast tasks (broken links) from smart tasks (deciding what to do with orphans).

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
warn: api.md — broken link to auth.md (file not found)
  fix: have ONE agent (e.g. fast model like Haiku) read api.md and fix or remove the broken link to auth.md
warn: notes.md — unreachable from CLAUDE.md (no link chain connects them)
  fix: have ONE agent (e.g. smart model like Opus) review this file and either link it from a reachable doc, or confirm with the user that it can be removed
warn: verbose.md — unreachable from CLAUDE.md (no link chain connects them)
  fix: have ONE agent (e.g. smart model like Opus) review this file and either link it from a reachable doc, or confirm with the user that it can be removed
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
warn: CLAUDE.md — unreachable from README.md (no link chain connects them)
  fix: have ONE agent (e.g. smart model like Opus) review this file and either link it from a reachable doc, or confirm with the user that it can be removed
warn: notes.md — unreachable from README.md (no link chain connects them)
  fix: have ONE agent (e.g. smart model like Opus) review this file and either link it from a reachable doc, or confirm with the user that it can be removed
warn: verbose.md — unreachable from README.md (no link chain connects them)
  fix: have ONE agent (e.g. smart model like Opus) review this file and either link it from a reachable doc, or confirm with the user that it can be removed
4/7 files reachable from README.md
exit code: 1
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

```bash
echo "=== --max-depth 0 (root only) ==="
mdscan --max-depth 0 /tmp/demo_docs 2>/dev/null
echo ""
echo "=== --ignore \"notes*\" ==="
mdscan --ignore "notes*" /tmp/demo_docs 2>/dev/null
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
```

## Test suite

```bash
uv run pytest -q
```

```output
................................                                         [100%]
32 passed in 1.62s
```
