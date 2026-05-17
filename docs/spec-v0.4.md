---
description: Living specification for mdscan v0.4 — evolution toward "madge for markdown" with minimal frontmatter, graph primitives, and standalone CLI design. Updated as decisions are taken in discussion.
---

# mdscan v0.4 — Specification (living doc)

> **Status**: design baseline. Updated incrementally as decisions are taken. Section "Open questions" tracks what's still unresolved.

## Vision

Evolve mdscan from a markdown scanner into a **headless graph tool for markdown corpora**, designed primarily for AI coding agents (Claude Code) consuming a project's documentation.

The bet: an agent's bottleneck is its context window. A minimal, structured frontmatter (filter L1) plus a navigable link graph (parse, follow, query) lets the agent find and consume *just enough* documentation without flooding context.

**Positioning**: "madge for markdown" — like [madge](https://www.npmjs.com/package/madge) does dependency analysis for JS codebases, mdscan does graph analysis for a `.md` corpus. Headless, vault-agnostic, honors standard `[txt](path.md)` links, emits JSON for piping to standard unix tools (`jq`, `rg`, `awk`, `comm`, `xargs`).

## Core design principles

### 1. Standalone

No coupling to git (no `git log` for dates), no coupling to Claude Code hooks (no `PreToolUse` interception). State changes happen through explicit CLI commands. Discipline encoded in the CLI contract, not in fragile auto-magic.

### 2. Minimal frontmatter

Frontmatter contains **only what cannot be expressed as a markdown link in the body**. All relations (cross-references, reading order, dependencies, aliases, successors) live as body content. This eliminates desync risk between frontmatter and content.

### 3. No query DSL

mdscan emits rich structured JSON. Filtering, joining, projection are delegated to `jq`. Body content search goes to `rg`. mdscan owns what unix tools cannot do cheaply: parsing markdown links correctly, resolving relative paths, traversing the graph (reachability, backlinks, orphans).

Mental model borrowed from Obsidian Dataview's `FROM`/`WHERE` split:
- **FROM** = corpus selector = mdscan primitives (`mdscan`, `backlinks`, `unreachable`, `tree`)
- **WHERE** = predicate filter = `jq 'select(...)'` on the emitted JSON

## Frontmatter schema

Four fields total. Three required, one managed by mdscan.

```yaml
---
description: "One sentence. The L1 filter that decides whether the agent loads this doc."
kind: reference | guide | decision | tasks
tags: [auth, jwt]
last_updated: 2026-05-14
---
```

| Field | Required | Type | Role |
|---|---|---|---|
| `description` | ✅ | string (≤150 words) | The L1 filter. The agent loads/skips based on this. |
| `kind` | ✅ | enum | Controlled vocabulary. Changes how the agent *interprets* the doc. |
| `tags` | ✅ | list of strings | Primary retrieval filter. Free-form. Governance via `mdscan tags`. |
| `last_updated` | managed | ISO date | Written by mdscan whenever the doc changes through a mdscan command. **Never set manually.** |

### `kind` vocabulary

| Value | Answers | Temporality | Example |
|---|---|---|---|
| `reference` | "What exists?" | present | `ARCHITECTURE.md`, API docs, glossary |
| `guide` | "How do I do X?" | timeless | setup guides, runbooks, howtos |
| `decision` | "Why was this chosen?" | past | ADRs, retros, post-mortems |
| `tasks` | "What will we do?" | future | plans, roadmaps, todo lists |

Configurable per project:

```toml
[tool.mdscan.schema]
kinds = ["reference", "guide", "decision", "tasks", "experiment"]
```

### Fields explicitly excluded (and why)

| Excluded field | Rationale |
|---|---|
| `status` | A deprecated doc is a deleted doc. No stale-state to track. |
| `last_verified` | Subjective and prone to drift. Replaced by `last_updated` (objective, mdscan-managed) plus operational `last_read` (in state.json). |
| `aliases` | Express as body content: H1 heading, first paragraph mention, or `## Also known as` section. `rg -l "AuthService"` covers resolution. |
| `children` | Express as body content: `## Reading order` (or similar) with an ordered list of `[txt](path.md)` links. mdscan extracts links **in document order** in JSON output — the reading order is implicit and free. |
| `related` | Express as body content: `## See also` section with markdown links. Captured by the existing link extractor. |
| `depends_on` | Express as body content: contextual links in prose where the dependency matters. |
| `superseded_by` | Express as body content: opening sentence like `"This supersedes [old.md](old.md)."` |
| `sources` | Deferred — was intended for staleness-by-hash. May return if Phase 5 (advanced staleness) is built. |

**Principle applied**: any field that's "a list of paths" is redundant with markdown body links and creates desync risk. Keep frontmatter for what cannot be a link.

## Body conventions for relations

No enforced conventions — use markdown naturally. mdscan parses standard `[txt](path.md)` links and gives the agent everything it needs:

- **Cross-references** → `[link text](path.md)` anywhere in prose
- **Reading order** → ordered list of links in body (order preserved in `mdscan --json` output's `links` field)
- **"See also"** → section with links at the end
- **Dependencies** → mentioned contextually where they matter
- **Successors** → "Supersedes [old.md](old.md)" in opening prose

The agent reads the file and sees relations *in context*. mdscan's link extractor captures them for graph queries.

## CLI surface

### Default action (bare command)

```bash
mdscan                    # equivalent to `mdscan list` — list files with descriptions
mdscan docs/              # list a specific directory
mdscan --json             # emit JSON for piping
```

Bare `mdscan` is the default entry point. Subcommands (`backlinks`, `tree`, `check-links`, etc.) remain available explicitly.

### Output modes

| Flag | Format | For |
|---|---|---|
| (default) | Human-readable columns | Humans browsing |
| `--json` | Full structured output (path, description, kind, tags, last_updated, links in document order) | Agents and pipelines (jq, gron, miller) |

**Removed**: `--plain` (TSV), `-l`/`--paths-only`, `-0`/`--null`. The use cases are covered by `mdscan --json | jq -r '...'` and standard tools.

### Write commands

All write commands update `last_updated` automatically when content actually changes.

| Command | Audience | Effect |
|---|---|---|
| `mdscan set-description <file> "..."` | Agent | Write/update description field |
| `mdscan set-tags <file> tag1 tag2 ...` | Agent | Replace tags list |
| `mdscan set-kind <file> reference` | Agent | Set kind (validates against schema) |
| `mdscan edit <file>` | Human, interactive | Opens `$EDITOR`; on close, diffs and updates `last_updated` if content changed |
| `mdscan touch <file>` | Agent (after `Write`/`Edit`) | Explicit touch when body was modified outside mdscan commands |

### Graph commands

| Command | Purpose |
|---|---|
| `mdscan backlinks <file>` | "Who links to this file?" Parses markdown, resolves relative paths, handles ref-style links and wikilinks correctly. Returns `{source, line, excerpt}` per match in JSON. |
| `mdscan tree [--from <entrypoint>]` | Display the document link tree as a `cargo tree`-style ASCII output (or JSON). Cycles marked. Default entrypoint = `CLAUDE.md`, fallback `README.md`. |
| `mdscan check-links` | Verify `.md → .md` links resolve. Detect unreachable docs (orphans) from the entrypoint. The "killer" primitive: nobody does this correctly headless. |

**`--all-links` removed** from `check-links`. For checking non-.md assets and HTTP links, recommend [lychee](https://github.com/lycheeverse/lychee) in the README.

### Discovery commands

| Command | Purpose |
|---|---|
| `mdscan tags` | List all tags in use with counts. Governance via discovery, not enforcement. `--rename old new` for bulk normalization. |
| `mdscan stale [--unread-since 60d] [--unupdated-since 90d]` | Cross-reference `last_updated` (frontmatter) and `last_read` (state.json) to surface deletion candidates. |
| `mdscan audit` | Compare current file hashes against `.mdscan/state.json`. Surface docs whose `last_updated` is out of sync with their content (i.e., body edited without `mdscan touch`). |
| `mdscan coverage` | % of files with description, with kind, % reachable from entrypoint, broken links count, avg word count. |

### Read command

| Command | Purpose |
|---|---|
| `mdscan show <file>` | Emit the file's content. Updates `last_read` and `read_count` in `.mdscan/state.json`. Agents are encouraged (but not forced) to use this instead of direct `Read` when tracked consumption is desired. |

### Validation

| Command | Purpose |
|---|---|
| `mdscan validate` | Check all docs against the schema. Missing required fields, invalid `kind` values → warnings. Exit code non-zero for CI gating. |

### Commands removed (and why)

| Removed | Rationale |
|---|---|
| `mdscan query` | Replaced by `mdscan --json | jq '...'`. jq is mature, agent-friendly, infinitely composable. No DSL to design, parse, or maintain. |
| `mdscan outline` | Pandoc (`pandoc --toc`), `grep -nE '^#+' file.md`, or `awk` cover this. Don't reinvent. |
| `mdscan children <file>` | Use `mdscan --json | jq '.[] | select(.path == "X") | .links'` — `links` is already in document order. If body has an ordered list of `.md` links, that's the reading order. |

## Telemetry — `.mdscan/state.json`

Operational state, separate from the semantic frontmatter:

```json
{
  "files": {
    "docs/auth/overview.md": {
      "last_read": "2026-05-14T10:23:00Z",
      "read_count": 12,
      "content_hash": "sha256:abc123..."
    }
  }
}
```

- **Single consolidated file** at repo root — no per-doc write churn
- **Written only by mdscan** (never edited manually)
- **Default `.gitignore`'d** — operational, machine-local. Optionally committed if a team wants shared usage telemetry.

Used by `mdscan stale`, `mdscan audit`, and `mdscan show`.

## Composing with standard tools

mdscan emits JSON; everything else is the user's choice of standard unix tools. A `docs/recipes.md` file ships recipe patterns.

Examples:

```bash
# All decisions tagged auth
mdscan --json | jq '.[] | select(.kind=="decision" and (.tags | contains(["auth"])))'

# Guides not deprecated
mdscan --json | jq '.[] | select(.kind=="guide" and (.tags | index("deprecated") | not))'

# Files tagged auth AND jwt
mdscan --json | jq '.[] | select((.tags | index("auth")) and (.tags | index("jwt")))'

# Pipeline back into mdscan
mdscan --json | jq -r '.[] | select(.kind=="decision") | .path' | xargs -I{} mdscan show {}

# Count docs per kind
mdscan --json | jq -r '.[].kind' | sort | uniq -c

# Interactive selection (human)
mdscan --json | jq -r '.[].path' | fzf | xargs mdscan show

# Quick backlinks (cheap, partial) — for trivial cases
rg -lF '](auth.md)' .

# Authoritative backlinks (handles code blocks, ref-style links, path resolution)
mdscan backlinks docs/auth.md
```

Tools to know:
- `jq` — JSON filter, primary companion
- `rg` — ripgrep, for body content search
- `gron` — flatten JSON to greppable lines (alternative to jq)
- `fzf` — interactive fuzzy selection (human ergonomics)
- `comm` / `sort` / `uniq` — set operations on path lists
- `awk` — column-oriented filtering on TSV-like output
- `pandoc` — for outline/TOC extraction
- `lychee` — for HTTP and asset link checking

## Phasing (provisional)

**Phase 1 — Schema and write surface**
1. Schema validation (`mdscan validate`), controlled `kind` vocabulary
2. `mdscan set-kind`, `mdscan set-tags` (extending `set-description`)
3. `last_updated` managed field
4. `mdscan touch`, `mdscan audit`, `.mdscan/state.json` plumbing
5. Bare `mdscan` as default action (already mostly there)

**Phase 2 — Graph and discovery**
6. `mdscan backlinks` (proper parsing, not regex-via-rg)
7. `mdscan show` + read telemetry
8. `mdscan stale`
9. `mdscan tags` for governance via discovery
10. Drop `--all-links` from check-links

**Phase 3 — Human ergonomics**
11. `mdscan edit <file>` interactive

**Phase 4 — Recipes and docs**
12. `docs/recipes.md` with jq/rg/awk/comm/lychee patterns
13. README rewrite around "madge for markdown" positioning
14. CLAUDE.md updated to reflect v0.4 surface

**Phase 5 — Integration with Claude Code ecosystem** *(deferred)*
15. Emit `.claude/skills/<area>/SKILL.md` from docs folders
16. Emit `.claude/rules/<area>.md` with `paths:` scoping
17. Optional MCP server (`mdscan serve`)
18. Plugin packaging (`.claude-plugin/plugin.json`)

**Phase 6 — Advanced staleness** *(optional)*
19. `sources:` frontmatter field + hash of source code for semantic staleness detection

## Topics requiring deeper research (priority)

Two topics surfaced from [PKM for agents](pkm-for-agents.md) — points 3.10 and 4 — that should be designed concretely *before* committing to the Phase 2-3 implementation. They affect command surface and may revise the schema.

### Templates and the `new` command (from pkm-for-agents §3.10)

The principle: every file the agent creates should be seeded with a correct frontmatter skeleton matching its `kind`. This is the write-time complement to `mdscan validate`. Without it, agents (and humans) keep producing files that fail validation, and `validate` becomes an annoyance instead of a guardrail.

Open design points:
- Where do templates live? (`.mdscan/templates/<kind>.md` or `[tool.mdscan.templates]` table in `pyproject.toml`?)
- One template per `kind` value, or arbitrary named templates?
- Variable substitution (date, title, author) or pure skeleton?
- Should `mdscan new` open `$EDITOR`, or always be non-interactive (write file and return)?
- Interaction with `mdscan set-kind` — does setting a kind on an existing file inject the template's required fields if missing?

### Progressive disclosure layers (from pkm-for-agents §4)

The principle: an agent's context budget is bounded; never pay for information you haven't decided you need. The four-layer model:

```
L1 Inventory   — what files exist and what are they about?  → mdscan --json
L2 Profile     — what is this file's role and connections?  → ??? (not yet decided)
L3 Outline     — what sections does this file have?         → was dropped (pandoc/grep)
L4 Full read   — body content                                → mdscan show / direct Read
```

Open design points:
- **L2 — Profile**: do we need a dedicated `mdscan profile <file>` command, or is `mdscan --json | jq '.[]|select(.path=="X")'` sufficient? The former is more discoverable; the latter is more unix-y.
- **L3 — Outline**: we dropped it in favour of pandoc/grep, but the L3 layer is a real need in the disclosure model. Reconsider: keep dropped (and document the pandoc/grep recipe prominently), or re-instate as `mdscan outline --json` because the batch-and-JSON aspect actually adds value over a one-liner?
- **L4 — Read**: `mdscan show` covers tracked reads, but does it need anchor support (`mdscan show file.md#section`) for L4-with-precision?
- **Section anchors**: heading → line number mapping is mentioned as enabling "jump to L4 at the right offset". Does mdscan need to expose this?

### Knowledge organisation methodologies (driving the `kind` enum)

Our current `kind = reference|guide|decision|tasks` was chosen pragmatically but is **not derived from any established methodology**. Established frameworks exist (Diátaxis, Zettelkasten, PARA, LATCH) that may suggest better categories — or validate our current choice. Research is in flight (OPUS agent dispatched). Decision pending the research outcome.

The choice of `kind` values is load-bearing: it shapes how every doc gets categorised, how agents adapt their reading strategy, and how queries discriminate. Worth getting right before users (and AI agents) bake assumptions into their corpora.

## Open questions

- [ ] Migration: how to handle existing `.md` files without `kind` or `tags` — soft warn vs hard fail vs interactive prompt during `mdscan set-*`?
- [ ] `mdscan validate` — strict by default or opt-in via `--strict`?
- [ ] `.mdscan/state.json` location — repo root or `.mdscan/` subdirectory?
- [ ] Backlinks scope — only `[txt](path.md)` markdown links, or also wikilinks `[[name]]` (Obsidian-style)?
- [ ] When `mdscan` is run from a subdirectory of a project, how does it find the project root (the directory containing `pyproject.toml` with `[tool.mdscan]`)? Walk up like `git`?
- [ ] `mdscan show` — naming OK or prefer `read` / `view` / `cat`?
- [ ] `mdscan edit` — does it support editing frontmatter-only via `$EDITOR`, or only the full file?

## References

- [PKM for agents](pkm-for-agents.md) — Obsidian features translated into agent primitives (research)
- [Obsidian query survey](obsidian-query-survey.md) — deep dive into Dataview/Bases/built-in search (research)
- [CLI audit](cli-audit.md) — design principles guiding the CLI surface
- [Plan v0.3](plan-cli-v0.3.md) — previous phase, currently shipped
- [madge](https://www.npmjs.com/package/madge) — JS dependency graph CLI, the conceptual model for mdscan's positioning
- [lychee](https://github.com/lycheeverse/lychee) — recommended companion for HTTP/asset link checking
