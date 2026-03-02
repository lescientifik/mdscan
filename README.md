# mdscan

Scan `.md` files and display their YAML frontmatter descriptions.
Built for AI agents that need to discover relevant documentation without reading entire files.

## Install

```bash
uv tool install git+https://github.com/lescientifik/mdscan.git
```

This installs `mdscan` globally. Run it from anywhere.

## Usage

See the full interactive demo: [demo.md](demo.md)

Quick overview:

```bash
# Scan a directory — descriptions on stdout, diagnostics on stderr
mdscan docs/

# JSON output (includes all files, null for missing descriptions)
mdscan --json docs/

# Write or update a file's frontmatter description
mdscan set-description docs/notes.md "Weekly meeting notes and action items."

# Limit depth, exclude patterns
mdscan --max-depth 1 --ignore "draft*" docs/
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0`  | All `.md` files have valid frontmatter |
| `1`  | Scan OK but some files have warnings |
| `2`  | Usage error (bad args, directory not found) |
