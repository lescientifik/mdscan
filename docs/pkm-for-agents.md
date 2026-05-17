---
description: Analysis of Obsidian PKM features translated into agent-facing primitives for an AI-native knowledge system built on top of mdscan.
---

# PKM for AI Agents — Obsidian Translated

**Date**: 2026-05-14
**Context**: Design research for evolving mdscan into an agent-focused knowledge system.

---

## 1. Core Obsidian Features

Ten features that make Obsidian genuinely useful for humans:

| Feature | What it does for a human |
|---|---|
| **Backlinks** | Shows every note that links to the current one, revealing unexpected connections and context. |
| **Graph view** | Visual 2-D map of the entire vault's link topology, useful for spotting orphans and clusters. |
| **Tags** | Freeform labels that cut across folder hierarchies, enabling thematic grouping without moving files. |
| **Aliases** | Let a note be referenced by multiple names (e.g. "API" → "Application Programming Interface"). |
| **Embeds / transclusions** | Inline another file or section into the current note (`![[note]]`), avoiding copy-paste drift. |
| **Dataview** | SQL-like query language that generates dynamic tables from frontmatter fields across all files. |
| **Canvas** | Spatial 2-D whiteboard for arranging notes visually; moodboard for ideas. |
| **MOCs (Maps of Content)** | Index notes that explicitly enumerate and contextualise child notes, functioning as human-curated tables of contents. |
| **Properties / frontmatter** | Structured YAML at the top of each file; Obsidian renders it as a typed form and Dataview queries it. |
| **Templates** | Stamp a new note with a predefined skeleton (headings, frontmatter fields, boilerplate). |

---

## 2. Knowledge Organisation Methodologies

Common systems Obsidian users layer on top of the tool:

| Method | Core idea |
|---|---|
| **Zettelkasten** | Each note is atomic (one idea), densely cross-linked, and given a unique ID so it can be cited precisely. |
| **PARA** | Files live in one of four buckets: Projects, Areas, Resources, Archive — organised by actionability, not topic. |
| **LATCH** | Five organisational lenses: Location, Alphabet, Time, Category, Hierarchy — choose the one that serves the query. |
| **Atomic notes** | Each file answers exactly one question; avoids the "mega-note" that becomes impossible to link precisely. |
| **Evergreen notes** | Notes are maintained and refined over time (vs. daily-notes-style append-only capture). |
| **MOCs** | Curated index pages that impose narrative structure on a cluster of notes without forcing folder hierarchy. |

---

## 3. The Translation Exercise — Feature by Feature

This is the substance. For each feature: does it make sense for an AI agent, and if so, in what concrete form?

### 3.1 Backlinks → `--incoming-links <file>`

**For a human**: serendipitous discovery of who references this note.
**For an agent**: structured, on-demand. An agent reads `ARCHITECTURE.md` and immediately needs to know which other notes cite it — to understand scope, to find callers, to trace a concept's use. A `mdscan backlinks src/ARCHITECTURE.md --json` command returning a list of `{file, line, context}` is directly consumable. This is more valuable for an agent than for a human, because an agent can act on the structured list immediately without cognitive overhead.

**Form**: `mdscan backlinks <file>` → JSON array of `{path, line, excerpt}`. No graph rendering needed.

### 3.2 Graph view → irrelevant as display; relevant as data

**For a human**: visual topology for orientation. Beautiful, cognitively useful.
**For an agent**: a PNG or even an ASCII graph is noise. However, the *underlying adjacency data* is valuable. `mdscan graph --json` outputting `{nodes: [...], edges: [...]}` lets an agent run reachability analysis, detect clusters, spot orphans — programmatically. The visualisation is for humans; the adjacency list is for agents.

**Form**: expose graph as a machine-readable adjacency list. Skip any visual rendering.

### 3.3 Tags → structured frontmatter field, queryable

**For a human**: freeform labels applied loosely, browsed in a sidebar panel.
**For an agent**: tags only matter if they are declared in frontmatter (`tags: [architecture, api, wip]`) and can be queried. `mdscan scan --tag wip` returning only files tagged `wip` is useful. But ad-hoc inline `#tags` scattered in prose are invisible noise to an agent. Enforce tags as a frontmatter field; treat inline hashtags as a parsing error.

**Form**: `tags` as a required-optional frontmatter field; `mdscan scan --tag <tag>` filter; `mdscan tags` listing all tags with file counts.

### 3.4 Aliases → important, underrated

**For a human**: convenience for linking ("I always type `[[API]]` but the note is named `Application Programming Interface`").
**For an agent**: critical for disambiguation. A project may call the same concept "auth", "authentication", "AuthService", and "identity". An `aliases` frontmatter field lets an agent find the canonical note for any of these terms. This also enables a `mdscan resolve <term>` command — "which file is the authoritative source for this concept?" — which is exactly the kind of lookup an agent needs when reading unfamiliar code.

**Form**: `aliases: [auth, AuthService, identity]` in frontmatter; `mdscan resolve <term>` returning the canonical file path.

### 3.5 Embeds / transclusions → translate as `related` and `see-also` fields

**For a human**: avoids copy-paste; keeps a master definition in one place and surfaces it inline.
**For an agent**: the agent can always read both files. Transclusion syntax (`![[note#section]]`) in raw markdown is parsing noise. The *semantic intent* — "this file depends on that file for a definition" — is valuable. Express it as a structured frontmatter field: `depends_on: [glossary.md, auth/overview.md]`. The agent can then decide whether to pre-fetch those files before reading the current one.

**Form**: `depends_on` frontmatter field; `mdscan scan --include-deps` optionally expands to also return dependency files.

### 3.6 Dataview → the single highest-value feature for agents

**For a human**: replaces manual index maintenance; tables update automatically as notes are added.
**For an agent**: this is exactly what structured frontmatter + a query layer enables. An agent can ask "give me all files where `status: draft` and `area: authentication`" and get a ranked list without reading every file. This collapses the exploration problem from O(files) to O(query result). It is the core primitive for context-efficient knowledge retrieval.

**Form**: `mdscan query 'status=draft AND tags=authentication'` → JSON list of matching files with their full frontmatter. This is the most important new command to build.

### 3.7 Canvas → irrelevant

A spatial whiteboard is a human cognitive tool. An agent has no use for spatial reasoning over a 2-D layout. Skip entirely.

### 3.8 MOCs (Maps of Content) → the entrypoint primitive, formalised

**For a human**: a hand-curated index that says "here are the 7 notes that together explain how authentication works, and here is the order to read them."
**For an agent**: enormously valuable, but only if machine-readable. A MOC expressed as a frontmatter field (`children: [step1.md, step2.md, step3.md]`) lets an agent fetch a structured reading path for any topic in one query, rather than crawling links. The existing `mdscan tree` command is a rudimentary MOC renderer, but it is discovery-based (follows links) rather than author-declared. Both matter.

**Form**: `children` or `index` frontmatter field for author-declared reading order; `mdscan tree` for discovered topology. `mdscan entry <topic>` resolving to the MOC file for a topic.

### 3.9 Properties / frontmatter → the agent's primary API surface

**For a human**: Obsidian renders a form; Dataview queries it. Useful but most users don't fill it systematically.
**For an agent**: frontmatter *is* the knowledge system. Every other feature listed here collapses to: "express it in frontmatter, then query it." The current mdscan `description` field is a single-field version of this. The evolution is a richer, validated schema: `description`, `status`, `tags`, `aliases`, `depends_on`, `children`, `area`, `owner`, `last_updated`. The agent never needs to read body prose to understand a file's role in the system.

**Form**: define a canonical schema; `mdscan validate` checks files against it; `mdscan set-field <file> <key> <value>` writes individual fields. Schema should be declared in `[tool.mdscan.schema]` in `pyproject.toml`.

### 3.10 Templates → `mdscan new <template>`

**For a human**: consistency and less friction when creating notes.
**For an agent**: the agent creates documentation files too. A template system ensures every file created by the agent (or by a developer following agent instructions) includes the required frontmatter fields. More importantly, templates encode the schema — creating a new `decision record` file automatically seeds `status: proposed`, `tags: [decision]`, `area: null`.

**Form**: templates stored in `.mdscan/templates/`; `mdscan new <template-name> <output-path>` creates the file with correct frontmatter skeleton and opens nothing (non-interactive, always).

---

## 4. Progressive Disclosure — Layered Information Architecture

An agent's context window is a fixed budget. The principle: **never pay for information you haven't decided you need.**

Four disclosure layers, each answerable without the next:

```
Layer 1 — Inventory      mdscan scan --json
  → {path, description, tags, status}  for every file
  → "What files exist and what are they about?" (one line per file)

Layer 2 — Profile        mdscan profile <file> --json
  → Full frontmatter of one file: all fields, children, depends_on, aliases
  → "What is this file's role and what does it connect to?"

Layer 3 — Outline        mdscan outline <file> --json
  → Heading tree (H1→H2→H3) with line numbers, no prose
  → "What sections does this file have? Where is section X?"

Layer 4 — Full read      (direct file read)
  → Body prose, code blocks, tables
  → Only read when the specific content is needed
```

The **metadata that enables this**:
- `description` — one sentence, required, L1 granularity
- `tags`, `status`, `area` — filter at L1 without reading anything
- `depends_on`, `children` — navigation at L2 without reading body
- `aliases` — term resolution before committing to a file path
- Section anchors (heading → line number mapping) — jump to L4 at the right offset

An agent exploring an unfamiliar codebase runs L1 once (scan all files), then L2 on candidates, then L3 to locate the relevant section, then L4 only on the specific section. Without this layering, the agent reads entire files to find one paragraph — a 10x context waste.

---

## 5. Three Killer Features to Build First

### K1 — Frontmatter Schema Validation (`mdscan validate`)

**Why first**: every other feature depends on frontmatter being present, correct, and consistent. Backlinks only help if files are linked. Tags only filter if tags are declared. Queries only work if fields exist. Without enforced schema, the knowledge graph degrades to the current state: a sparse `description` field filled in by no one. `mdscan validate` exits 1 with a structured list of violations; CI gates on it; agents trust the metadata because it is enforced.

**Minimum viable**: declare expected fields in `pyproject.toml`, run `mdscan validate` to catch missing or malformed fields, emit JSON errors with file+field+reason.

### K2 — Frontmatter Query (`mdscan query`)

**Why second**: this is the feature that makes the agent's exploration sublinear. Without it, "find all draft files in the authentication area" requires reading every file. With it, one command. The query also becomes the mechanism for MOC-like retrieval: `mdscan query 'children_of=auth/overview.md'` returns the reading list. It replaces manual graph traversal with declarative lookup — which is exactly what a context-constrained agent needs.

**Minimum viable**: field equality and AND conjunction; JSON output; no DSL parser needed initially (flags like `--status draft --tag authentication` are sufficient).

### K3 — Backlinks Index (`mdscan backlinks`)

**Why third**: once an agent reads a file, it immediately needs to answer "who uses this?" A developer adding a new auth flow needs to know which decision records, specs, and onboarding docs reference the old auth model. Without backlinks, the agent is blind to impact scope and risks writing advice that contradicts existing documentation. This is the feature that makes the knowledge graph bidirectional — the most important structural property of a Zettelkasten, and the one that scales with the size of the codebase rather than against it.

**Minimum viable**: `mdscan backlinks <file>` scanning all `.md` files for `[[wikilinks]]` and `[text](path)` references to the target file, returning `{path, line, context}` JSON.

---

## Appendix — Features Explicitly Not Worth Building

| Feature | Verdict | Reason |
|---|---|---|
| Graph visualisation | Skip | Agents don't see images; adjacency JSON is sufficient |
| Canvas | Skip | Spatial reasoning is a human cognitive primitive |
| Daily notes | Skip | Agents have no concept of days or journaling |
| Inline `#hashtags` | Skip | Unparseable in context; use frontmatter `tags` only |
| WYSIWYG editing | Skip | Agents write files via `set-description` / `new`; no editor needed |
| Publish / sync | Skip | Out of scope; agent knowledge lives in the repo |
