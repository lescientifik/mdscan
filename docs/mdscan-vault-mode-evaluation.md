---
description: Critical evaluation of whether mdscan should evolve into a vault-aware tool like Obsidian (cross-project KB, persistent index, wikilinks, backlinks global) — final verdict, three scenarios, and explicit recommendation for the v0.4+ roadmap.
---

# mdscan vault mode — should we go there?

> **Status**: design evaluation, written 2026-05-14. Companion to [pkm-for-agents.md](pkm-for-agents.md), [obsidian-query-survey.md](obsidian-query-survey.md), [mdscan-taskwarrior-synergy.md](mdscan-taskwarrior-synergy.md) and [taskwarrior-design-ideas-for-mdscan.md](taskwarrior-design-ideas-for-mdscan.md). The question: **should mdscan acquire a "vault mode" — a unified, persistent, cross-project knowledge base à la Obsidian — or stay project-scoped?** Answer below, with confidence.

## TL;DR

- A "vault mode" sounds attractive — one place for all your markdown, cross-project search, Obsidian parity — but the use cases that actually demand it are **thinner than they look**, and almost all of them are addressable by `mdscan path1 path2 ...` plus shell pipes.
- The hard costs are real: **persistent index** (state, invalidation, multi-machine sync), **name conflicts** (two `setup.md`), **tag/kind semantics drift** across corpora, **wikilink resolution** (Obsidian's "shortest unique path" requires a global symbol table), and **lifetime ownership** (who creates/destroys the vault?).
- These costs **directly violate three v0.4 design principles**: standalone (vault config implies coupling), no DSL (wikilink resolver is a DSL of paths), stateless (persistent index is state).
- The agent IA argument **cuts the other way than instinct**: a Claude Code session works in **one project at a time**, has a bounded context window, and is **harmed**, not helped, by a 5000-note global index it cannot fit. The agent's actual need is *better signal per byte in the current project*, not more bytes globally.
- The ecosystem already provides the alternative cleanly: **Obsidian is the vault manager**, mdscan is the headless graph reader. If you want Obsidian features, run Obsidian. mdscan's win is being the **CLI side** of the same plain-text vault — composable, scriptable, agent-friendly — not a competitor.
- **Recommendation (confidence high)**: **reject the vault-manager pivot (scenario C). Accept a small, opportunistic compromise (scenario B-lite): mdscan stays project-scoped, gains a multi-root flag (`mdscan path1 path2 ...`) that aggregates without persistent state, and documents in `docs/recipes.md` how to point it at an existing Obsidian vault.**
- The wikilink resolver (`[[Note]]` → path) is the **single Obsidian-specific feature** that might be worth adding behind an opt-in `--wikilinks` flag if (and only if) a user shows up with an actual Obsidian vault and asks for it. Until then: YAGNI.
- The vault-mode question is **not the same conversation** as Taskwarrior synergy or the L1-L4 disclosure model. Both of those keep working under the recommendation. The vault question is a positioning question, not a feature question.
- Concrete action for spec v0.4: **add Scenario B-lite to the roadmap as a 1-page item, close the vault question, do not re-open it without a concrete user request with named files.**

---

## 1. The question, restated with its ambiguities

"Vault mode" hides at least four distinct propositions, and the choice between them is most of the evaluation:

| Proposition | What it means |
|---|---|
| **V1 — Multi-root scan** | `mdscan /path/A /path/B` aggregates results from N independent corpora. No persistent state, no cross-corpus linking. Pure scope widening. |
| **V2 — Vault as union of projects** | A user-declared "vault" (config file in `~/`) lists N project paths; mdscan treats them as a single graph, resolves cross-project links, computes global backlinks. Implies an index and a config root. |
| **V3 — Obsidian vault reader (read-only)** | mdscan recognises `.obsidian/` as a vault marker, learns to parse `[[Wikilinks]]`, resolves them using Obsidian's shortest-path-when-possible algorithm. mdscan becomes the *CLI face* of an existing Obsidian vault. No write semantics beyond what mdscan already does. |
| **V4 — Vault manager** | mdscan becomes the source of truth: `mdscan vault init`, `mdscan vault list`, persistent index, wikilink resolution, backlinks computed globally, possibly a daemon (`mdscan serve`). mdscan replaces Obsidian for headless use. |

The user's prompt collapses these. They're worth keeping separate because **V1 has almost no cost**, **V2 has medium cost and medium benefit**, **V3 has bounded cost and unclear benefit**, and **V4 has very high cost and no defensible market**. Most of the rest of this doc argues that distinction.

A second ambiguity: **who is the user?** This matters.

- **A solo developer with one project at a time** (the dominant mdscan target as of v0.3): vault mode adds noise. Their context window is bounded by the project anyway.
- **A researcher / writer with a single life-wide Obsidian vault** (the literature-review profile from [mdscan-taskwarrior-synergy.md §6](mdscan-taskwarrior-synergy.md)): vault mode is meaningful — they really do want cross-project search across years of notes. But this user **already has Obsidian**. Their need is a CLI face, not a replacement.
- **An agent IA serving multiple repos**: an agent that works in one repo per session does not need a vault. An agent that is asked to answer "what do I know about X across all my projects?" might benefit — but the right answer there is a search engine (ripgrep, vector index, or Anthropic's own retrieval), not a graph CLI.

Holding these three profiles in mind: the case for V2/V3/V4 is **strongest for profile 2, weakest for profiles 1 and 3**. Profile 2 is also the profile that gets the **least** benefit from mdscan-becoming-Obsidian (they already have Obsidian).

---

## 2. Obsidian vault — anatomy and what it actually buys

### 2.1 Storage model

An Obsidian vault is **a folder of files**. That's it. There is no proprietary store. Markdown files, optional attachments, optional canvas files (`.canvas` JSON), optional bases (`.base` YAML) ([Obsidian: How Obsidian stores data](https://obsidian.md/help/Files+and+folders/How+Obsidian+stores+data)).

Everything else is in `.obsidian/`:

- `app.json`, `appearance.json` — user preferences
- `core-plugins.json`, `community-plugins.json` — plugin enablement
- `workspace.json`, `workspace-mobile.json` — pane layout (treated as machine-local, often `.gitignore`'d)
- `graph.json` — graph view settings
- `hotkeys.json` — keyboard
- `plugins/<plugin-id>/` — installed community plugins (JS bundles + their own `data.json`)
- `cache/` — index cache (treated as **disposable**, always `.gitignore`'d) — this is where Obsidian persists its metadata index between launches

The **metadata index** is held in memory at runtime (`app.metadataCache`, [MetadataCache API](https://docs.obsidian.md/Reference/TypeScript+API/MetadataCache)) and serialised to `cache/` for quick startup. It contains: parsed frontmatter, headings, links (resolved + unresolved), embeds, tags, blocks. Plugins query this cache rather than re-parsing files. The cache is **rebuilt automatically** on file changes — there is no manual invalidation.

### 2.2 Wikilink resolution

The Obsidian-specific feature most people mean by "vault" is `[[Note]]` links. The resolution algorithm ([Obsidian forum: shortest path](https://forum.obsidian.md/t/settings-new-link-format-what-is-shortest-path-when-possible/6748)):

1. **Bare basename** (`[[my note]]`) → match the file whose basename (case-insensitive, ignoring `.md`) is `my note`. If unique, done.
2. **Ambiguous basename** → require the shortest disambiguating path prefix (`[[folder/my note]]`).
3. **Alias** → if `aliases: [API gateway]` in another file's frontmatter, `[[API gateway]]` resolves to that file.
4. **Heading anchor** (`[[Note#Heading]]`) and **block anchor** (`[[Note^block-id]]`) handled by parsing the target file's headings/blocks.

Critically, this requires a **global symbol table** of `{basename → list[path]}` for the entire vault. There is no way to resolve a bare `[[my note]]` from one file without knowing every other file in the vault. **This is the technical reason Obsidian needs a vault concept at all** — `[[]]` collapses without it.

Standard markdown links `[text](path/to/file.md)` need no such table; the path is explicit and relative. mdscan v0.3 already handles those correctly.

### 2.3 What the vault concept buys you (and what it costs)

| Buys | Costs |
|---|---|
| Bare-name links (`[[my note]]`) anywhere | Global symbol table, ambiguity diagnostics |
| Backlinks over the whole vault, not just the project | Index of inbound edges, kept fresh on every write |
| Tag pane that lists tags across all notes | Tag index, fresh on every write |
| Graph view spanning all notes | Adjacency matrix held in memory |
| Quick switcher with alias resolution | Alias index |
| Embeds across files (`![[note]]`, `![[note#section]]`) | Lookup at render time |

Everything in the right column is **persistent state**. Obsidian pays it with an in-memory cache + on-disk serialisation. The user never sees it because Obsidian is a long-running process. **A CLI tool is not a long-running process** — every invocation pays the full re-scan cost or relies on a daemon.

That's the architectural hinge. mdscan v0.4's pitch is *stateless, mono-shot, headless*. Adopting wikilinks at vault scope means either (a) accepting state, or (b) re-scanning the entire vault on every invocation (which scales badly past a few thousand notes).

For perspective: a 5000-note vault is normal for a serious Obsidian user ([Sébastien Dubois: PKM at scale](https://www.dsebastien.net/personal-knowledge-management-at-scale-analyzing-8-000-notes-and-64-000-links/) reports 8000 notes / 64000 links). Parsing 5000 markdown files cold-cache is a 1–3 second hit on modern hardware. Tolerable for `mdscan scan`, painful for `mdscan backlinks <file>` run interactively.

---

## 3. Use cases — which are real, which are hypothetical

The prompt suggests five candidate use cases. Honest evaluation:

### 3.1 "Cross-project literature review"

**Real but specific.** A researcher who has a vault of papers (e.g., the FES-PET review of [mdscan-taskwarrior-synergy.md §6](mdscan-taskwarrior-synergy.md)) wants to ask "which papers I've taken notes on mention tag X?" across years.

**But**: this user has the notes in **one folder** already. They don't have ten Git repos full of paper notes. Their need is `mdscan ~/notes/` plus jq — V1 (multi-root scan) is overkill, V2 (declared vault) is overkill. The bare command already works.

The cross-*project* angle only emerges if a researcher keeps lab-specific notes in lab repos and personal notes elsewhere. That's a real workflow, addressed by `mdscan ~/notes/ ~/lab-repo/docs/` (V1, zero state).

**Verdict: addressable by V1. Does not justify V2+.**

### 3.2 "Personal notes linking to project code"

The agent IA reads `~/notes/auth-research.md` while working in `~/projects/foo/src/auth/`. Today they can't — the notes live elsewhere.

**But this is a Git/path problem, not a vault problem.** If a project genuinely depends on personal notes, those notes belong in the project repo or in a Git submodule, or symlinked into `docs/`. Globalising mdscan to span those folders papers over the actual structural mistake (mixing personal and project knowledge).

The "vault" framing makes it sound like mdscan needs to grow. Actually, **the user needs to decide which knowledge is project-scoped and which is personal**, and store accordingly.

**Verdict: mostly a discipline problem, not a tool problem. Don't enable confusion.**

### 3.3 "Knowledge transfer between projects (dev)"

"I documented OAuth in project A. Project B is building OAuth too. The agent should reuse what I learned."

**Real, but the answer is not a vault.** Two clean answers:

1. **Promote shared knowledge to a shared location.** Cookbook, internal docs site, monorepo `/docs`. The shared corpus then *is* a project mdscan can scan ([Eric Ma: referencing code across repos with agents](https://ericmjl.github.io/blog/2025/11/17/how-to-reference-code-across-repositories-with-coding-agents/) — the consensus is "use explicit file paths and references, not magic").
2. **Let the agent re-read.** Project B's CLAUDE.md says `See also: ../project-a/docs/auth.md`. The agent follows. mdscan multi-root (`mdscan project-a project-b`) makes this explicit.

The "agent automatically discovers what I know across projects" framing is a **retrieval / RAG problem**, not a graph problem. The MCP-based local RAG servers ([knowledge-rag](https://github.com/lyonzin/knowledge-rag), [mcp-local-rag](https://github.com/shinpr/mcp-local-rag)) are the right shape for this. mdscan should not compete with vector search.

**Verdict: V1 (multi-root) covers the explicit case. The implicit "automatic discovery" case belongs to RAG, not mdscan.**

### 3.4 "Agent consults global KB + current project"

The dream: agent runs `mdscan` once, sees everything across all my projects, picks the right doc.

**This is exactly where the agent context budget breaks.** A 5000-note global L1 inventory is, at 1 line per note (path + description), ≈ 100kB of text — fits in context. But the agent doesn't *want* to read 5000 entries to find one. The right interface for that scale is **search**: vector or BM25.

mdscan's value proposition (per [pkm-for-agents.md §5](pkm-for-agents.md)) is "the agent reads a 50-line scan output for the current project, picks 3 relevant docs, reads them." That works at project scale. At vault scale (5000 entries) it does not.

A vault-aware mdscan would either:
- emit too many lines (overflow context), or
- need a query/filter step before output — i.e. re-invent search.

**Verdict: agents don't want a vault-scale L1. They want a project-scale L1 + global search. mdscan is the L1 tool; let `rg`, `fzf`, vector RAG be the search tool.**

### 3.5 "Aggregate stats across projects (docs coverage, orphans)"

`mdscan coverage` could in theory cover N projects.

**Yes — V1 handles this for free.** `mdscan coverage project-a project-b` aggregates. No persistent state needed. The result is one number per metric.

**Verdict: V1, near zero cost, real value for a multi-project dev.**

### 3.6 Summary of use cases

| Use case | Real? | Best addressed by |
|---|---|---|
| Literature review cross-folder | Real, narrow | V1 (multi-root) — or just put notes in one folder |
| Personal notes ↔ project code | Mostly a discipline problem | Don't paper over with V2 |
| Knowledge transfer between dev projects | Real | Shared docs location + V1; not a graph problem |
| Agent global KB consultation | Real at small scale, breaks at scale | RAG (MCP server), not mdscan |
| Cross-project stats | Real | V1 multi-root |

Five candidate use cases. **All addressable by V1 or by a separate tool.** None require V2/V3/V4. That's the empirical case for restraint.

---

## 4. Technical and conceptual cost of V2+

### 4.1 Persistent index

To do backlinks across N projects, or to resolve wikilinks at vault scope, mdscan needs an index of `{basename → paths}`, `{path → outgoing edges}`, `{path → incoming edges}`, optionally `{tag → paths}`.

The cheap implementations:

- **SQLite** — rejected for mdscan in [taskwarrior-design-ideas-for-mdscan.md §12.2](taskwarrior-design-ideas-for-mdscan.md): inverts the plain-text-first principle, introduces a binary store, complicates sync.
- **JSON in `~/.mdscan/index.json`** — readable, commitable in principle, but multi-MB at 5000 files and inefficient to mutate.
- **Per-file pickle / msgpack** — wrong granularity; the index is global by nature.
- **Re-scan every invocation, no index** — fine for small vaults, bad scaling.

Each option costs *something*: SQLite costs ideology, JSON costs space + I/O, re-scan costs latency at scale. Obsidian solves it by being a long-running process; mdscan can't.

Worse: **invalidation**. If a user edits a `.md` outside mdscan (with vim, `Edit`, GitHub web UI, anything), the index is stale. Obsidian watches the FS (long-running) and re-parses on FS events. mdscan would need either a daemon (out of scope), a "trust the index until told otherwise" model with a manual `mdscan reindex`, or a hash-check pass at every invocation (which scales like O(files), defeating the index's purpose).

The cleanest existing precedent is **[zk](https://github.com/zk-org/zk)** — a CLI Zettelkasten tool that uses a per-notebook SQLite index at `.zk/notebook.db`. It works because zk is opinionated: there is one notebook root, defined by `.zk/config.toml`, and zk owns the index. zk is V3-shaped (single vault per command, vault-aware, persistent index, wikilinks). It runs about 30k LoC of Go.

mdscan adopting zk's model is a 5–10× scope expansion. It would be a different tool.

### 4.2 Name conflicts across projects

Two docs called `setup.md` in projects A and B. In V1 (multi-root), paths are project-prefixed; no conflict. In V2/V3/V4 with wikilinks, `[[setup]]` is ambiguous and resolution requires either:

- a global shortest-path rule (Obsidian's choice — works, but produces non-deterministic links when files are renamed)
- explicit `[[project-a/setup]]` (defeats the convenience)
- aliases (an additional schema field — explicitly excluded from v0.4 frontmatter)

This is solvable but it's a permanent foot-gun. Obsidian users have learned to live with it. mdscan adopting it imports the foot-gun into a CLI context where errors are less debuggable.

### 4.3 Tag and kind drift

`tags: [auth]` in project A means "JWT bearer tokens"; in project B it means "OAuth flows"; in personal notes it means "the police". Globalising tag listing produces a list dominated by accidental homonymy.

`kind: decision` is universal enough to hold up; `tags` are not. A vault-wide `mdscan tags` command listing all tags across projects produces noise unless the user has invested in a vocabulary discipline. Most don't.

**This is the same problem Obsidian users complain about with cross-vault tag soup.** They solve it with prefixes (`auth-jwt`, `auth-oauth`, `daily-2026-05`) or with rigid PARA-style folders. Both are conventions, both require discipline; mdscan can't enforce them.

### 4.4 Lifecycle ownership

Who creates the vault? Who destroys it? In Obsidian, the user clicks "Open another vault" → folder picker → done. In a CLI:

- `mdscan vault init ~/Documents/notes/` creates `~/Documents/notes/.mdscan-vault/` with config + index.
- `mdscan vault add ~/projects/foo` registers a second project root. (Or use a globbing config: `paths: ["~/projects/*", "~/notes"]`.)
- `mdscan vault list` shows registered vaults.
- `mdscan vault destroy` cleans up.

Plus: multi-machine sync. The config can live in `~/.config/mdscan/`, but the index can't (paths differ per machine, paths-relative-to-vault-root). Result: per-machine index, rebuilt on each machine, with all the staleness problems above.

None of this is impossible. It's just **mdscan becoming a different tool with a new persistent-state surface**, in direct violation of the v0.4 stance.

### 4.5 Multi-machine

Three options:
1. Per-machine index, rebuilt on demand (current proposal — acceptable but loses caching value).
2. Index in the repo (commit `.mdscan/index.json`) — works only for vault = one repo. Doesn't help multi-project union.
3. Index in a sync service (Dropbox, Syncthing, custom) — out of scope.

Obsidian sidesteps this by selling Obsidian Sync ($$$) or relying on user-managed Git/Dropbox/iCloud. **A CLI that mandates a sync story is doomed**; one that punts is half-functional. Pick your poison.

### 4.6 Summary of costs

Every V2+ feature pays one or more of: state, complexity, sync, drift, ambiguity. The v0.4 spec's three core principles (standalone, no DSL, stateless) were chosen exactly to **avoid** these. Re-introducing them through "vault mode" is a regression to where the spec already moved away from.

---

## 5. Tension with the v0.4 positioning

| v0.4 principle | Vault mode position | Resolvable? |
|---|---|---|
| **Standalone** (no coupling to git, Obsidian, Claude Code) | V3 *is* coupling to Obsidian's vault format. V2/V4 invent a new format. | V1 only; V3 violates as opt-in (acceptable behind a flag); V4 violates structurally. |
| **No DSL** (jq for filters, rg for body search) | Wikilink resolver is a DSL of paths. Backlinks-at-vault-scope is a query primitive. | Wikilink resolver violates if implemented as a parser. V1 doesn't violate; V3 violates lightly (one resolver). |
| **Stateless / mono-shot** | Persistent index is state. Long-running daemon (`mdscan serve`) is mono-shot's opposite. | V1 keeps stateless; V2/V3/V4 require state. |
| **JSON-first / pipe-friendly** | Vault mode is *more* JSON-friendly (more to emit) — compatible. | Compatible across the board. |
| **Minimal frontmatter** | Vault mode might want `aliases`, `vault-id`, `cross-refs` fields. v0.4 already excluded aliases. | V3 might force aliases back in (Obsidian uses them). Re-opening that decision. |

The principles were chosen pragmatically; the question is whether vault mode is **important enough** to revisit them. The use-case analysis (§3) says no.

The contrast with [taskwarrior-design-ideas-for-mdscan.md](taskwarrior-design-ideas-for-mdscan.md): that doc adopted Taskwarrior patterns (reports, DOM dotted-path) **only where they didn't violate principles**, explicitly rejected hooks, SQLite, custom parser, recurrence. The same discipline applies here: adopt the part that fits (V1), reject the parts that don't (V2/V4), evaluate V3 narrowly as an opt-in compatibility layer.

---

## 6. The agent IA angle — sharper this time

The implicit assumption behind "vault mode for agents" is *more knowledge = better agent*. The actual constraint is **context budget**, not knowledge availability.

A Claude Code session in `~/projects/foo` has:

- ~200k-1M tokens of context window (model-dependent).
- A current task, scoped to one repo.
- An L1 inventory of the project's `docs/` from `mdscan --json` (≈ a few KB).
- Files it loads via `Read` on demand.

What helps this session:
- **Smaller, sharper L1 in the current project** → covered by v0.4 schema work (kind, tags, validate, stale).
- **Faster relevance filtering** → covered by reports + jq filters.
- **Knowing the *links* in the current project** → covered by `tree`, `backlinks`, `check-links`.

What does **not** help:
- A 5000-note global L1 the agent can't fit.
- A wikilink resolver in a project that uses standard markdown links.
- A backlinks query that returns hits from unrelated projects.

The pattern observed in the wild — Karpathy-style LLM wikis, Claude Code + Obsidian setups ([Cross-Project Knowledge Base with Vault System](https://dev.to/newbe36524/building-cross-project-knowledge-base-for-the-ai-era-with-vault-system-306o), [How I Turned My Obsidian Vault Into Claude Code's Brain](https://michaelcrist.substack.com/p/context-engineering)) — uses **RAG retrieval** to surface relevant notes, not a directory tree walk. The agent asks "what do I know about X?" and the RAG layer returns the top-k. mdscan's value is *after* retrieval: once a doc is identified as relevant, the agent reads it and follows its links.

This **bounds mdscan's role correctly**: it is the "follow the links, see the description, decide what to read" tool at the *current project* level. It is not the "search 5 years of personal notes" tool.

The corollary: **AGENTS.md / CLAUDE.md / Claude Code Skills are the cross-project knowledge primitive**. Each project ships its own `CLAUDE.md` entry point. Cross-project recall happens via the user explicitly pasting context or via MCP RAG, not via a magic global graph ([GitHub blog: how to write AGENTS.md](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/) — the consensus is "small, scoped, scoped again").

---

## 7. Alternatives explored

Going from cheapest to most expensive.

### 7.1 Multi-root flag (V1) — `mdscan path-a path-b`

Cost: ~30 LoC. The `scan` and most graph commands already take a directory; lift the constraint to "1+ directories". JSON output gets a `root` field per file to disambiguate. Backlinks across roots work if links use relative paths that *resolve* across roots (rare in practice).

Value: covers literature review across folders, cross-project coverage stats, ad-hoc aggregation. No new state, no new schema, no new coupling.

**Recommended**.

### 7.2 Symlinks + V1

The user maintains a `~/notes/` folder with symlinks into project repos: `~/notes/foo-auth.md → ~/projects/foo/docs/auth.md`. `mdscan ~/notes/` then sees everything. The user is in charge of the curation.

Cost to mdscan: zero. Cost to user: maintain symlinks, but the structure is explicit and they own it.

**Mentionable in `docs/recipes.md`. Not a feature.**

### 7.3 Git submodules / monorepo

For dev knowledge that is genuinely shared across projects, the right answer is a Git submodule (`docs-shared/`) or a monorepo `/docs/`. mdscan operates on it natively.

Cost to mdscan: zero. Cost to user: Git submodule discipline (real, non-trivial).

**Mentionable in `docs/recipes.md`. Not a feature.**

### 7.4 Companion tool (`mdvault`)

A second binary that wraps mdscan invocations, holds the vault config in `~/.config/mdvault/`, and orchestrates per-project mdscan calls + aggregates JSON. mdscan stays clean; orchestration lives elsewhere.

Cost: building a second tool. Real, but isolates the complexity.

**Reasonable in principle, premature in practice. Build it the day a user needs it, not before.**

### 7.5 Read existing Obsidian vault (V3)

mdscan recognises `.obsidian/` as a vault marker. Behind a `--wikilinks` flag, parses `[[Note]]` links by reading every `.md` basename in the vault root. No persistent index — re-scan on each invocation. No write support for wikilinks (set-description etc. still write markdown links). Aliases supported via `aliases:` frontmatter, opt-in.

Cost: ~200 LoC parser + symbol table builder. No new persistent state (re-scan each time — fine up to 1000-2000 notes, slow beyond).

Value: makes mdscan immediately useful for the profile-2 user (Obsidian vault owner). Their Claude Code agent can pipe `mdscan --wikilinks --json` and follow links across their notes.

**Worth considering — but only if a real user shows up asking for it.** YAGNI until then.

### 7.6 Become Obsidian (V4)

Build `mdscan vault init/add/sync`, persistent SQLite or JSON index, wikilink resolver with shortest-path, daemon for FS watching, aliases as first-class, cross-vault links, etc.

Cost: massive. Five-to-ten times the current codebase. Re-opens every closed v0.4 design decision.

Value: doesn't compete with Obsidian (which has 10 years of UX), doesn't compete with zk (purpose-built, polished). mdscan in V4 has no defensible niche.

**Reject definitively.**

---

## 8. Three scenarios — comparative table

| Dimension | A. Project-scoped (status quo + V1 sprinkle) | B. Read existing Obsidian vault (V3, opt-in) | C. Become vault manager (V4) |
|---|---|---|---|
| **Multi-corpus aggregation** | `mdscan path-a path-b` (no state) | `mdscan path-a path-b` + `mdscan --vault ~/Documents/notes` | Persistent `mdscan vault` subsystem |
| **Wikilinks `[[Note]]`** | Not supported | Parsed and resolved on read with shortest-path, opt-in `--wikilinks` | First-class, with aliases, anchors |
| **Backlinks scope** | Per scan invocation, on the paths given | Per scan invocation, including the vault | Globally indexed, persistent |
| **Persistent index** | None | None (cold scan each time) | SQLite or JSON, ~MB scale |
| **Frontmatter schema impact** | None (4 fields hold) | Optional `aliases` re-introduced | `aliases`, `vault-id`, possibly more |
| **CLAUDE.md / standalone** | Preserved | Preserved (Obsidian is read, not required) | Violated (mdscan becomes a vault platform) |
| **Implementation cost** | ~50 LoC (multi-root) | ~200-400 LoC (wikilink resolver) | 5000+ LoC, new subsystems |
| **What the agent gains** | Slight ergonomics (one command for N roots) | Can navigate an Obsidian vault headlessly | Theoretically: a global KB. Practically: noise. |
| **What the agent loses** | Nothing | Nothing | Signal-to-noise in current project |
| **Blast radius on v0.4 spec** | One paragraph in CLI surface, one recipe | One opt-in flag, one schema concession | Re-write half the spec |
| **Reversibility** | Trivial (drop the flag) | Trivial (keep behind opt-in) | Effectively irreversible |
| **Risk** | Near-zero | Low | High |
| **Target user fit** | Profiles 1, 3 | Profile 2 | None of the three cleanly |

Scenarios B and C share the same direction; C just takes it further. The honest reading:

- **A** is what v0.4 already does, with a single sensible improvement.
- **B** is a reasonable next step **iff** a user with an Obsidian vault asks for it. Not before.
- **C** is a strategic mistake.

A graduates to B if and only if there's pull. C is closed.

---

## 9. Recommendation

**Adopt scenario A (status quo + V1 multi-root). Defer scenario B behind an explicit user request. Reject scenario C.**

Concretely, for the v0.4 roadmap:

1. **Phase 1 (already planned)**: schema, validate, set-*, touch, state.json. Unchanged.
2. **Phase 2 (already planned)**: backlinks, show, stale, tags. Unchanged.
3. **Add to Phase 2 or 3**: **multi-root scan** — `mdscan path-a path-b path-c` aggregates. JSON output gains a per-file `root` field so downstream tooling can group. Backlinks operate within each root by default; `--cross-root` flag (off by default) to resolve relative links across roots if they happen to match.
4. **Add to Phase 4 (recipes)**: a section "Running mdscan against an Obsidian vault" — explains `mdscan path/to/vault`, notes that wikilinks are ignored by default, recommends Obsidian + mdscan as complementary, not competitive.
5. **Document the closure**: in `spec-v0.4.md` open-questions section, replace the "Backlinks scope — wikilinks?" open question with a closed decision: *wikilinks are deferred behind an opt-in `--wikilinks` flag, to be implemented if and when a user requests it; no persistent vault index will be built.*
6. **Do not** add `mdscan vault init`, `vault list`, `vault destroy`, or any persistent vault concept.
7. **Do not** add an alias frontmatter field.
8. **Do not** build a daemon.

### Confidence

**High.** The reasoning is converging across four independent angles:

- *Use cases*: every plausible vault-mode use case dissolves on inspection (§3).
- *Architecture*: v0.4 principles forbid the moves vault mode requires (§5).
- *Agent ergonomics*: vault-scale L1 hurts more than it helps the agent (§6).
- *Ecosystem*: Obsidian exists, zk exists, RAG MCP servers exist; mdscan's niche is the *headless CLI on a project corpus*, which is unclaimed and useful (§7).

I would only revise this if:

1. A real user shows up with an Obsidian vault and a concrete cross-vault workflow Claude Code can't currently serve (→ implement V3 narrowly), or
2. The L4 (full read) latency on cold-scan starts hurting (→ consider a small cache file in `.mdscan/`, not a full vault subsystem).

Neither is on the horizon as of 2026-05.

### Why this is *not* a "more research needed" answer

The temptation, given the depth of Obsidian + the genuine appeal of "one place for everything", is to say "let's prototype it and see". Three reasons to refuse:

- **A vault mode prototype that meets even half the bar (wikilinks + cross-project backlinks + persistent index) is ~2 months of work**. That's the entire v0.4 budget consumed by a feature whose addressable user base, on inspection, is one person with one Obsidian vault.
- **A half-built vault mode is worse than none**: the "headless, agnostic" pitch collapses into "headless, sort of, sometimes". Mixed messaging kills CLI tools.
- **The decision is reversible at almost no cost** if I'm wrong: scenario B can be added later as a clean opt-in. The current refusal forecloses nothing.

The TaskWarrior synergy ([mdscan-taskwarrior-synergy.md](mdscan-taskwarrior-synergy.md)) reached the same conclusion via the same logic: don't build inside mdscan what an existing tool already does well, and don't grow the schema to cover use cases that aren't yours.

---

## 10. Implications for adjacent decisions

### 10.1 Taskwarrior synergy

Unaffected. The bicephalic architecture (notes in `.md`, tasks in Taskwarrior, link via UDA `note:`) operates at project scope and works identically whether mdscan is multi-root or not. The "vault" concept is orthogonal: a user with five Taskwarrior projects and five mdscan roots gets a 5×5 matrix of project intersections, queryable via `task project:X note:Y` — no vault needed.

### 10.2 Schema (kind, status)

Unchanged from [knowledge-organisation-research.md §6](knowledge-organisation-research.md): `reference | guide | explanation | decision`, plus optional `status` lifecycle field. Vault mode would have pressured `aliases` back in (Obsidian needs them for wikilink disambiguation). The recommendation **keeps aliases excluded** (consistent with v0.4 §4).

### 10.3 Reports (Taskwarrior idea)

Unaffected. Reports defined per-project in `pyproject.toml` ([taskwarrior-design-ideas-for-mdscan.md §2](taskwarrior-design-ideas-for-mdscan.md)). A multi-root invocation can either apply reports per-root or aggregate first; the simple default is per-root. Vault-wide reports would imply vault-wide schema, which we're refusing.

### 10.4 Progressive disclosure (L1-L4)

Unaffected. L1 inventory is project-scoped by design; vault L1 is what we just rejected. L2-L4 happen on individual files irrespective of scope.

### 10.5 The `--wikilinks` question

Currently in v0.4 open questions as: "*Backlinks scope — only `[txt](path.md)` markdown links, or also wikilinks `[[name]]` (Obsidian-style)?*"

Recommended closure: **default to standard markdown links only. Wikilinks deferred to a future opt-in `--wikilinks` flag, implemented only if a user with an Obsidian vault requests it.** Document in spec.

This closes one of the seven open questions and resolves the "vault-aware" temptation in a single sentence.

---

## 11. What would change my mind

In the spirit of falsifiability:

- **A user opens an issue: "I have a 3000-note Obsidian vault, I use Claude Code daily, I want to navigate it from the CLI with mdscan."** → Implement V3 (scenario B). Scoped, opt-in, no persistent index, possibly add `aliases` reluctantly.
- **A benchmark on a realistic 5000-note corpus shows that cold-scan latency on `mdscan --json` exceeds 5 seconds and breaks agent flow.** → Build a small per-project cache in `.mdscan/cache.json` (still not a vault — just a per-project speed-up).
- **The Claude Code / Anthropic ecosystem ships a standard "knowledge skill" that wants mdscan to expose a vault-shaped interface.** → Implement V3, possibly with an MCP server adapter. But this is event-driven, not speculation-driven.

Nothing else moves the recommendation.

---

## 12. Bibliography

### Internal mdscan docs (read for this evaluation)

- [/home/thenry/Projects/mdscan/CLAUDE.md](../CLAUDE.md) — project orientation
- [docs/spec-v0.4.md](spec-v0.4.md) — living v0.4 specification
- [docs/pkm-for-agents.md](pkm-for-agents.md) — Obsidian features → agent primitives
- [docs/obsidian-query-survey.md](obsidian-query-survey.md) — Dataview / Bases deep dive
- [docs/knowledge-organisation-research.md](knowledge-organisation-research.md) — methodology survey, `kind` enum
- [docs/mdscan-taskwarrior-synergy.md](mdscan-taskwarrior-synergy.md) — bicephalic architecture
- [docs/taskwarrior-design-ideas-for-mdscan.md](taskwarrior-design-ideas-for-mdscan.md) — patterns to steal / reject
- [src/mdscan/](../src/mdscan/) — current code (cli.py, scanner.py, links.py, frontmatter.py, tree.py, config.py)

### Obsidian — anatomy and APIs

- [Obsidian — How Obsidian stores data](https://obsidian.md/help/Files+and+folders/How+Obsidian+stores+data)
- [Obsidian — Manage vaults](https://obsidian.md/help/manage-vaults)
- [Obsidian Developer Docs — MetadataCache](https://docs.obsidian.md/Reference/TypeScript+API/MetadataCache)
- [Obsidian Developer Docs — CachedMetadata](https://docs.obsidian.md/Reference/TypeScript+API/CachedMetadata)
- [DeepWiki — MetadataCache and Link Resolution](https://deepwiki.com/obsidianmd/obsidian-api/2.4-metadatacache-and-link-resolution)
- [Obsidian forum — Shortest path when possible](https://forum.obsidian.md/t/settings-new-link-format-what-is-shortest-path-when-possible/6748)
- [Obsidian forum — Wikilink resolution does not honor frontmatter aliases (1.12.7)](https://forum.obsidian.md/t/wikilink-resolution-does-not-honor-frontmatter-aliases-1-12-7/113902)
- [Obsidian forum — Convert from shortest to absolute path](https://forum.obsidian.md/t/convert-existing-wikilinks-from-shortest-to-absolute-path/86685)
- [zoni/obsidian-export #58 — How Obsidian resolves file paths](https://github.com/zoni/obsidian-export/discussions/58)
- [Steffo99/obsidian-file-index](https://github.com/Steffo99/obsidian-file-index) — plugin that surfaces the Obsidian index as a JSON file

### Comparable tools

- [zk-org/zk](https://github.com/zk-org/zk) — CLI Zettelkasten with `.zk/config.toml` and SQLite index (V3-shaped)
- [zk-org docs — Configuration file](https://zk-org.github.io/zk/config/config.html)
- [artempyanykh/marksman](https://github.com/artempyanykh/marksman) — markdown LSP with workspace indexing
- [marksman/docs/features.md](https://github.com/artempyanykh/marksman/blob/main/docs/features.md)
- [Feel-ix-343/markdown-oxide](https://github.com/Feel-ix-343/markdown-oxide) — PKM markdown LSP
- [Markdown-Oxide Wiki](https://oxide.md/)
- [silverbulletmd/silverbullet](https://github.com/silverbulletmd/silverbullet) — self-hosted markdown wiki
- [Dendron — Hierarchies](https://wiki.dendron.so/notes/f3a41725-c5e5-4851-a6ed-5f541054d409/)
- [Dendron — Multi Vault Setup](https://wiki.dendron.so/notes/24b176f1-685d-44e1-a1b0-1704b1a92ca0/)
- [Slant — Logseq vs Dendron 2025](https://www.slant.co/versus/39125/41500/~logseq_vs_dendron)
- [Rost Glukhov — Obsidian vs LogSeq 2025](https://www.glukhov.org/post/2025/11/obsidian-vs-logseq-comparison/)

### Agent IA + knowledge base patterns

- [Eric Ma — How to reference code across repositories with coding agents](https://ericmjl.github.io/blog/2025/11/17/how-to-reference-code-across-repositories-with-coding-agents/)
- [GitHub Blog — How to write a great agents.md](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/)
- [AGENTS.md spec](https://agents.md/)
- [Steering AI Agents in Monorepos with AGENTS.md (DEV)](https://dev.to/datadog-frontend-dev/steering-ai-agents-in-monorepos-with-agentsmd-13g0)
- [RepoSwarm — Give AI Agents Context Across All Your Repos](https://robotpaper.ai/reposwarm-give-ai-agents-context-across-all-your-repos/)
- [Building Cross-Project Knowledge Base for the AI Era with Vault System (DEV)](https://dev.to/newbe36524/building-cross-project-knowledge-base-for-the-ai-era-with-vault-system-306o)
- [How I Turned My Obsidian Vault Into Claude Code's Brain](https://michaelcrist.substack.com/p/context-engineering)
- [Sébastien Dubois — PKM at scale: 8000 notes, 64000 links](https://www.dsebastien.net/personal-knowledge-management-at-scale-analyzing-8-000-notes-and-64-000-links/)

### RAG / local KB for Claude Code

- [lyonzin/knowledge-rag](https://github.com/lyonzin/knowledge-rag)
- [shinpr/mcp-local-rag](https://github.com/shinpr/mcp-local-rag)
- [0xrdan/mcp-rag-server](https://github.com/0xrdan/mcp-rag-server)
- [Claude Code issue #28196 — Built-in Personal Knowledge Base with Semantic RAG](https://github.com/anthropics/claude-code/issues/28196)

### Vault structure conventions

- [Steph Ango — How I use Obsidian (vault structure)](https://stephango.com/vault)
- [Forte Labs — PARA](https://fortelabs.com/blog/para/)
- [Johnny.Decimal](https://johnnydecimal.com/)

---

*The vault question has been asked. It has been answered. The answer is "no, but with a small yes". This document closes the question.*
