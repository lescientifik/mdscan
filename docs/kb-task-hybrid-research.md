---
description: Reconciles mdscan's dual mandate as knowledge base + task tracker by separating doc-kind (content shape) from item-level tasks (GFM checkboxes with inline metadata), surveys hybrid plaintext PKM/PM tools, and proposes a concrete kind enum, syntax, and command surface.
---

# Reconciling knowledge and tasks in mdscan — a hybrid design

## TL;DR — the opinionated proposal

- **Tasks are item-level, not file-level.** A task is a GFM checkbox (`- [ ]`) inside any markdown file. The previous OPUS report's instinct that "tasks" was a lifecycle smell inside `kind` is correct — but the right fix is not to delete the task concept, it is to **move it to the right level of granularity.** Files are content; checkboxes are work.
- **`kind` keeps four values: `reference | guide | explanation | decision`.** Drop `tasks`. The reason isn't that mdscan doesn't track tasks — it's that "tasks" was the wrong unit. A roadmap is `kind: reference` whose body happens to contain checkboxes. A retro is `kind: decision` whose body happens to contain action-item checkboxes. The frontmatter describes the document's shape; the body holds the work.
- **One canonical task syntax**, GFM-compatible: `- [ ] task description @owner due:2026-05-20 !high #tag`. The five-state checkbox character set borrows from Logseq/Org but stays inside the GFM bracket: `[ ]` open, `[/]` doing, `[x]` done, `[-]` cancelled, `[?]` waiting. Renders as a checkbox in any GFM viewer; readable by every tool that already knows about task lists.
- **Five new commands**: `mdscan tasks`, `mdscan agenda`, `mdscan board`, `mdscan task add|done|cancel`. All operate on item-level tasks parsed from the corpus. `mdscan --json` gains a `tasks` array per file.
- **Zero new frontmatter fields.** Every project/PM dimension (deadlines, owners, priority, status) lives on the task line, not the file. The four-field schema (`description`, `kind`, `tags`, `last_updated`) is sufficient.

The headline claim: **mdscan should be Org-mode-shaped, not Linear-shaped.** Org-mode is the only system that has scaled "knowledge + tasks in the same plaintext corpus" for two decades. Every other hybrid either bifurcates (Notion: doc-table vs task-table) or layers tasks-as-feature on top of a docs-first substrate (Obsidian Tasks). mdscan should pick the side that matches its existing positioning: docs-first, body conventions, headless graph.

---

## 1. Survey: how successful plaintext hybrids handle the file-vs-item question

### 1.1 Comparison matrix

| Tool | Task granularity | Task syntax | Task states | File-level concept | Query model |
|---|---|---|---|---|---|
| **Org-mode** | Item-level (headline, any depth) | `* TODO foo` | Customisable: `TODO / NEXT / WAITING / DONE / CANCELED` (per-file or global) | "TODO file" is just a file with TODO headlines; not a distinct type | Agenda views (clocked, scheduled, deadline, tagged) |
| **Logseq** | Item-level (block — any bullet) | `- TODO foo` | Default: `TODO / DOING / DONE / LATER / NOW / WAITING / CANCELED` | None (blocks live in pages, no "task page" concept) | Datalog queries across the graph |
| **Obsidian Tasks** | Item-level (checkbox) | `- [ ] foo 📅 2026-05-20 ⏫` | GFM checkbox extended: `- [ ]`, `- [/]`, `- [x]`, `- [-]`, `- [?]` | None enforced — folder convention only | Per-codeblock query DSL |
| **TaskPaper** | Mixed: projects are headers (`Foo:`), tasks are items (`- foo`) | `- foo @due(2026-05-20) @priority(1)` | `@done`, `@cancelled` tags only | "Project" is a header line ending in `:` | Filter expressions on tags |
| **Dendron** | Item-level via "task notes" — special schema, not GFM | YAML frontmatter on a child note | `status` frontmatter field per note | "Task note" is a file with a task schema | None native; relies on schemas |
| **Linear** | File-level (every issue is a row) | N/A — issues live in a DB, not markdown | `Backlog / Todo / In Progress / In Review / Done / Canceled` | An issue *is* a task | SQL-like, GraphQL API |
| **GitHub Issues + Projects v2** | File-level (issues) + item-level (GFM checkboxes inside issue body) | `- [ ] subtask` inside an issue | Custom single-select fields | Issue is the unit | Saved views, custom fields |
| **Notion** | File-level (every row in a Task DB is a doc) | N/A — DB row with properties | Custom `Status` property (Backlog/In Progress/Done/etc.) | A doc can have any DB row's properties; "task" is a row in a Task DB, "page" is a row in a Docs DB | DB filters + relations |
| **Things 3** | Item-level (todo) under file-level project + area | Proprietary; `- todo` in TaskPaper export | `open / completed / canceled` | Project (with deadline) ≠ Area (ongoing) | Saved smart lists |
| **Bullet Journal** | Item-level (`• task`, `O event`, `– note`) | One line, glyph prefix | `• → x ›` (open/migrated/done/scheduled) | Daily/monthly/future logs are file-like | Manual review |
| **todo.txt** | Item-level | `(A) 2026-05-20 buy milk +grocery @home due:2026-05-25` | Two states (open / `x` prefix = done) | No file structure | grep / awk |

### 1.2 The grand divide

Two camps, no middle ground:

**Camp A — Item-level (plaintext-native PKM tools).** Org-mode, Logseq, Obsidian Tasks, TaskPaper, todo.txt, Bullet Journal. **All of them.** Tasks are lines or blocks, not files. Files contain mixed content. The unit of state is a line.

**Camp B — File-level (relational/SaaS).** Linear, Notion, Jira, GitHub Projects. Tasks are rows in a tasks table. Docs are rows in a docs table. The systems do not pretend a doc *is* a task; they relate them. The unit of state is a row in a typed table.

The lesson is unambiguous: **the moment you commit to plaintext, you commit to item-level.** Every plaintext system that tried to make tasks file-level (Dendron's "task notes", folder-of-files todo lists) ended up reinventing item-level tasks inside the files anyway, because file creation is heavyweight and most actionable items are small.

Camp B works because it has a *database*. mdscan is a corpus scanner, not a database. Camp A is the only camp it can live in.

### 1.3 Why Org-mode is the gold standard (and where it hurts)

Org-mode is 20+ years of accumulated wisdom on "knowledge + tasks in one plaintext corpus." Worth studying:

- **Headlines are the unit.** A heading `** TODO Implement OAuth` is simultaneously a section of a doc *and* a task. The whole subtree (its body, sub-headings, links) is the task's context. This is genius — there is no impedance mismatch between "where is the task" and "what is the task about."
- **Configurable workflow states per file.** `#+TODO: TODO(t) NEXT(n) WAITING(w@/!) | DONE(d) CANCELLED(c@)`. The vertical bar separates "not done" from "done". The `(t)` is a hotkey. The `@/!` means "log a note and timestamp" when transitioning. Pragmatic and decades-tested.
- **Three orthogonal date markers**: `SCHEDULED:`, `DEADLINE:`, `CLOSED:`. Distinct meanings — "I plan to start" vs. "must be done by" vs. "actually finished at." Not collapsing them is a real insight.
- **Tags** with inheritance up the headline hierarchy (`:auth:jwt:`).
- **Priorities** `[#A]`, `[#B]`, `[#C]` — three is enough, more is overkill.
- **Agenda view**: cross-file query for tasks by date/tag/state. The killer app.

**Where Org hurts** (from the research):
- Parses every byte to build the agenda. 100k-line files cause 20-second agenda generation. mdscan should avoid this trap by parsing lazily and caching per-file.
- The headline-as-task choice means **every task is a section**, which inflates document structure. A roadmap with 30 action items becomes 30 H3s. Awkward when the action items are small.
- Configurability is a footgun. Every Org user has their own workflow states and nobody else's `.org` file is intelligible without reading their `init.el`.

mdscan should learn from the wins (item-level, three date markers, three priorities, tags, agenda) and the losses (limit configurability, parse lazily, prefer GFM checkboxes over headlines so tasks are smaller-grained than sections).

### 1.4 The Logseq / Obsidian Tasks middle path

Logseq normalises Org-mode into block-level (any bullet). Obsidian Tasks normalises GFM checkboxes. Both keep item-level but reduce the syntactic weight: `- TODO foo` instead of `*** TODO foo` (no heading depth significance).

Obsidian Tasks' big innovation: **stay inside GFM**. `- [ ]` is universally rendered as a checkbox. Metadata after the description (emoji or `key:: value`) degrades gracefully — it's text in any non-Tasks viewer. This means an Obsidian Tasks file is a *valid GFM file* readable by GitHub, GitLab, `mdcat`, Pandoc, any AI agent that knows markdown. No special parser required.

This is the right substrate for mdscan: **GFM checkboxes + plain-text inline metadata**, not custom syntax.

### 1.5 Bullet Journal: the philosophical anchor

BuJo is older than Org-mode in concept (Ryder Carroll formalised it in 2013 but it codifies a pen-and-paper practice that's centuries old). Its three-glyph system is the conceptual ancestor of every plaintext hybrid:

- `•` task (open) — `x` done — `›` migrated — `<` scheduled — `-` cancelled
- `O` event
- `–` note

The dual mandate is built into the foundation: tasks, events, and notes coexist on the same page, distinguished by glyph. This is exactly the dual mandate the user is asking mdscan to support, validated by decades of practice. The takeaway: **don't pick one side. Both belong on the same page. Use a glyph (or, for us, a checkbox) to distinguish.**

---

## 2. Addressing the previous OPUS report's critique

The previous report argued `tasks` is "lifecycle masquerading as kind." Restated: it's a category error to put a temporal/workflow attribute (work-to-be-done) into a content-shape enum (what-this-doc-is).

**The critique is correct as stated. It is also misapplied.** The fix isn't to delete `tasks` from mdscan's purview — it's to put tasks at a different level. The previous report's hidden assumption was that "task" must live in frontmatter or nowhere. Once you accept that tasks live in the *body* (as checkboxes), the lifecycle critique evaporates:

- A roadmap is `kind: reference, tags: [planning]`. Its body has checkboxes. The frontmatter is purely content-shape; the lifecycle is on the items.
- A retro is `kind: decision`. Its body contains action-items as checkboxes. Same separation.
- A backlog/todo list (`TODO.md`, `docs/tasks/sprint-23.md`) is... still `kind: reference`. It is a reference document whose content happens to be primarily checkboxes. There is nothing about its file-level identity that demands a separate `kind`.

So:
- `kind` = doc shape (Diataxis-derived). Stays 4 values. **No `tasks` kind.**
- Task lifecycle = checkbox state inside the body. **Per-item, not per-file.**

This satisfies both the previous OPUS argument (no lifecycle in `kind`) *and* the user's dual-purpose mandate (tasks are first-class in mdscan, just at the right granularity).

The previous report's chooser stands:

1. Records a commitment? → `decision`
2. Tells you how to do something? → `guide`
3. Tells you what something is? → `reference`
4. Tells you why something is? → `explanation`

A roadmap full of checkboxes is `reference` (it documents the planned work). A spec full of checkboxes is `reference` (it documents what the system shall do). A retro with action items is `decision` (it records what was learned and what was committed to). The checkboxes carry the work; the document carries the shape.

---

## 3. The recommended task syntax

### 3.1 Constraints

- Must be valid GFM (renders correctly on GitHub, GitLab, in any markdown viewer).
- Must be parseable without ambiguity by mdscan.
- Must be writable by humans without consulting a reference card.
- Must be readable by AI agents without hidden semantics.
- Must be self-describing — no field-name reference required to understand a task line.

### 3.2 The syntax

```
- [ ] task description @owner due:2026-05-20 !high #tag
```

Anatomy:

| Element | Form | Required | Notes |
|---|---|---|---|
| Checkbox | `- [ ]` / `- [/]` / `- [x]` / `- [-]` / `- [?]` | yes | GFM checkbox; see §3.3 for states |
| Description | free text | yes | Anything between the checkbox and the first inline-metadata token |
| Owner | `@name` | no | Single token (no spaces). Multiple allowed: `@alice @bob`. |
| Date markers | `due:YYYY-MM-DD`, `scheduled:YYYY-MM-DD`, `done:YYYY-MM-DD` | no | ISO dates only. `done:` auto-stamped by `mdscan task done`. |
| Priority | `!high`, `!med`, `!low` | no | Three levels (Org-mode's wisdom). Default = no marker = unprioritised. |
| Tags | `#tag` | no | Same vocabulary as file-level `tags` frontmatter |
| ID | `^id` (e.g. `^abc123`) | no | Optional stable ID for cross-references. Generated by `mdscan task add` if `--id` requested. |

This is a **deliberate composite** of three established systems:
- **GFM checkbox** for the state (universally understood).
- **todo.txt** for `@context` and `+project` — except we use `@owner` (more PM-aligned) and `#tag` (markdown-native).
- **Obsidian Tasks `key:value`** for dates — but in plain `key:value` form, not `[key:: value]`, because the brackets are syntactic noise no one types willingly.

Crucially: **all metadata is on a single line, after the description.** No multi-line tasks. No indented metadata. This is the property that makes `rg`/`awk`/`grep` work on task lines as well as mdscan does.

### 3.3 The five task states

| Checkbox | Meaning | Mapped concept |
|---|---|---|
| `- [ ]` | open / not started | Org `TODO`, Linear `Todo`, Logseq `TODO` |
| `- [/]` | in progress / doing | Org `NEXT`/started, Linear `In Progress`, Logseq `DOING`/`NOW` |
| `- [x]` | done | Universal |
| `- [-]` | cancelled / won't do | Org `CANCELLED`, Linear `Canceled` |
| `- [?]` | waiting / blocked | Org `WAITING`, Linear "blocked" |

**Five states, fixed.** No configurability in v1. Rationale:

- Two states (vanilla GFM) is too thin — "in progress" is a real distinction every PM tool encodes.
- Six+ states (Logseq, Linear's expanded set) bifurcate the open/in-progress space (`TODO`/`NEXT`/`DOING` vs `LATER`/`NOW`) without enough payoff for an agent-facing CLI.
- Five states map cleanly to Linear's category-level (Backlog/Todo→`[ ]`, In Progress/In Review→`[/]`, Done→`[x]`, Canceled→`[-]`, plus the universally-needed `[?]` for blocked).
- All five characters are commonly used in GFM viewers and Obsidian Tasks. `[ ]` and `[x]` are standard GFM; `[/]`, `[-]`, `[?]` render as "non-standard but visible" checkboxes in most renderers, and as `[/]` / `[-]` / `[?]` literally in others — which is still legible.

A future `[tool.mdscan.tasks].states` config could allow extension, but v1 ships these five **fixed**, for the same reason mdscan ships four fixed `kind` values: cross-project agents need a stable contract. Extension comes after adoption.

### 3.4 What we deliberately do NOT support

- **Emoji metadata** (Obsidian Tasks' `📅 2026-05-20 ⏫`). Cute, but unparseable by humans on a terminal (which renders some emoji as wide glyphs and others as boxes), and emoji parsing is a stability risk. `due:`/`!high` is more agent-friendly.
- **Inline `[key:: value]`** (Dataview format). Same reason — bracket noise no one types willingly. We pay for one bracket pair (the checkbox); we don't pay for a second.
- **Recurrence rules** (`🔁 every Monday`). Real feature, but v1 mdscan doesn't process time. Defer.
- **Dependencies between tasks** (`dependsOn:abc123`). Tempting, but the moment you have task IDs and dependencies you've reinvented Linear. Body markdown links cover the 90% case: `Blocked by [auth spec](auth-spec.md#oauth-flow)`. Defer.
- **Subtasks via indentation**. GFM supports it (`  - [ ] subtask` under a parent), and mdscan should preserve the indentation in JSON output (so consumers can render the tree) — but mdscan should treat each line as its own task with a `depth` field. No special parent/child semantics in v1.

---

## 4. The reconciled `kind` enum

### 4.1 Final proposal

```yaml
kind: reference | guide | explanation | decision
```

**Four values. Drop `tasks`. No `status`.** Same as the previous OPUS conclusion — but for a *different* reason than that report gave.

The reason isn't "lifecycle is a category error" (true but secondary). The reason is **`kind` answers a different question than tasks need answered**. `kind` answers "what should the agent expect when it reads this body?" Tasks answer "what work is the team doing?" These are orthogonal. Trying to encode both in one field is the bug.

### 4.2 Where common doc archetypes land

| Document | `kind` | Body contains checkboxes? | Notes |
|---|---|---|---|
| API reference | `reference` | rarely | Pure information |
| Architecture overview | `reference` | rarely | Snapshot of system |
| Setup guide | `guide` | sometimes (step-by-step checklist) | Action-oriented |
| Incident runbook | `guide` | sometimes | Procedural |
| ADR | `decision` | rarely | Records past choice |
| Post-mortem | `decision` | sometimes (action items) | Records what was learned |
| Concept overview | `explanation` | rarely | The "why" |
| **Roadmap** | `reference` | **yes — primarily** | Documents planned work; the work is in the checkboxes |
| **Sprint backlog** | `reference` | **yes — primarily** | Same logic |
| **Spec / design doc** | `reference` | sometimes (open questions, TODOs) | A spec is a reference doc that may contain pending work markers |
| **Retro** | `decision` | yes (action items) | Decision-shaped; the body has commitments-as-checkboxes |
| **TODO.md** at repo root | `reference` | **yes — primarily** | A reference list of work; same as a roadmap, smaller scope |

The key insight: **"the doc is mostly checkboxes" is not a content-shape category**. A roadmap and an API reference are both `reference` because both describe what exists (planned, in the roadmap's case; current, in the API's case). The presence of checkboxes is a body characteristic, not a frontmatter classifier.

### 4.3 Why not a separate `status` axis (re-examining)

The previous report suggested a second axis (`status: draft | active | shipped | archived`). The user rejected it. The hybrid lens validates the user's rejection:

- File-level lifecycle (`draft`/`shipped`) is genuinely covered by the checkbox states in the body. A roadmap whose checkboxes are all `[x]` is shipped. A spec whose checkboxes are all `[ ]` is draft. **The lifecycle is computable from the contents** — no separate field needed.
- The dimension `status` was trying to encode is now **per-task**, where it belongs (work is per-task, not per-file).

So the user's "no `status` field" stance is **strengthened**, not weakened, by introducing item-level tasks.

### 4.4 Configurability stays minimal

Per the existing spec, `[tool.mdscan.schema] kinds = [...]` can add extra project-specific values (e.g. `experiment`, `runbook`). The four canonical values are fixed. Same rule for tasks: the five canonical checkbox states are fixed in v1. Both stay agent-predictable across projects.

---

## 5. Command surface additions

Five commands. All operate on item-level tasks discovered by parsing GFM checkboxes from `.md` bodies.

### 5.1 `mdscan tasks [path]`

The "list all tasks" command, analogous to `mdscan` (list all docs). Defaults to all open tasks (`[ ]`, `[/]`, `[?]`).

```bash
mdscan tasks                           # all open tasks, all files
mdscan tasks --state done              # done tasks
mdscan tasks --state all               # everything
mdscan tasks --owner @alice            # filter by owner
mdscan tasks --tag auth                # filter by tag (file OR task tag)
mdscan tasks --due-before 2026-06-01   # date filter
mdscan tasks --priority high           # !high tasks
mdscan tasks docs/auth/                # restrict scope to a subdir
mdscan tasks --json                    # JSON output: [{file, line, state, desc, owner, due, priority, tags, id}]
```

Default human output:

```
docs/roadmap.md:42  [ ]  Implement OAuth provider @alice due:2026-05-20 !high
docs/roadmap.md:43  [/]  Wire up JWT middleware    @bob   due:2026-05-15
docs/retro-q1.md:17 [?]  Decide on session store   @alice
```

### 5.2 `mdscan agenda [--week | --day | --overdue]`

Org-mode's killer feature, slimmed down. Cross-corpus query for time-bound tasks.

```bash
mdscan agenda --week               # all open tasks due this week
mdscan agenda --overdue            # open tasks past their due date
mdscan agenda --day 2026-05-20     # tasks due on a specific day
mdscan agenda --json
```

Output groups by date. Optional `--by-owner` regroups by `@owner`.

### 5.3 `mdscan board [--by state|owner|priority]`

A kanban-style read of the corpus. Reads-only — mdscan doesn't render a TUI board, it emits columns as JSON (or as a text grid for humans).

```bash
mdscan board                       # default: --by state
mdscan board --by owner --json
```

Human output (default = by state):

```
TODO         DOING        WAITING      DONE
─────        ─────        ───────      ────
…12 items    …3 items     …2 items     …47 items
```

`--json` emits `{ "TODO": [task...], "DOING": [...], ... }`.

### 5.4 `mdscan task add <file> "<description>" [--owner @x] [--due YYYY-MM-DD] [--priority high]`

The write-side counterpart to `set-description`. Appends a new GFM checkbox at the end of the file (or under a specified heading via `--section "## Inbox"`). Updates `last_updated`.

```bash
mdscan task add docs/roadmap.md "Implement OAuth provider" --owner @alice --due 2026-05-20 --priority high
```

### 5.5 `mdscan task done|cancel|wait|start <file:line>`

State-transition command. Targets a task by `file:line` (which is what `mdscan tasks` outputs).

```bash
mdscan task done docs/roadmap.md:42    # rewrites [ ] → [x] and stamps done:2026-05-14
mdscan task start docs/roadmap.md:43   # [ ] → [/]
mdscan task cancel docs/roadmap.md:44  # [ ] → [-]
mdscan task wait docs/roadmap.md:45    # [ ] → [?]
```

Updates `last_updated`. Optional `--note "<text>"` appends a body note for the transition (Org's `(w@)` semantics, optional).

### 5.6 Integration with the existing `mdscan --json`

`mdscan --json` already emits per-file metadata. It gains a `tasks` array per file:

```json
{
  "path": "docs/roadmap.md",
  "description": "OAuth roadmap",
  "kind": "reference",
  "tags": ["auth"],
  "last_updated": "2026-05-14",
  "links": [...],
  "tasks": [
    {"line": 42, "state": "open", "description": "Implement OAuth provider", "owner": ["@alice"], "due": "2026-05-20", "priority": "high", "tags": [], "id": null}
  ]
}
```

This means `mdscan --json | jq` covers every query the dedicated commands cover, plus arbitrary ad-hoc ones. `mdscan tasks` is sugar over `mdscan --json | jq '.[] | .tasks[] | select(.state == "open")'`. Same philosophy as the rest of the v0.4 spec.

---

## 6. Frontmatter additions

**Zero.** The four-field schema (`description`, `kind`, `tags`, `last_updated`) is sufficient.

Considered and rejected:

- `owner` (file-level) — implied by who creates tasks in the file, or by `@owner` on the items themselves. A file doesn't have one owner; tasks do.
- `project` — collapsed into `tags`. If a file is "about" project X, tag it `#proj-x`.
- `status` (file-level) — re-rejected, as in §4.3.
- `due` (file-level) — files don't have due dates. Tasks do.

**Principle preserved**: frontmatter holds what cannot be expressed as body content. Tasks are body content. Therefore no frontmatter fields for them.

---

## 7. The hybrid working in anger — examples

### 7.1 A roadmap file

```markdown
---
description: Q2 2026 roadmap for the auth subsystem.
kind: reference
tags: [auth, planning]
last_updated: 2026-05-14
---

# Auth Q2 Roadmap

The plan is to ship OAuth, retire the legacy session backend, and add SSO.
See [auth architecture](auth-arch.md) for context.

## OAuth provider

- [/] Implement Authorization Code flow @alice due:2026-05-20 !high
- [ ] Implement PKCE extension @alice due:2026-05-25
- [?] Decide on token storage strategy @alice due:2026-05-18 (blocked on infra)

## Retire legacy session backend

- [ ] Audit current callers @bob due:2026-06-01
- [ ] Migration playbook @bob

## SSO

- [ ] Spike SAML vs OIDC @alice !low
```

`kind: reference`. The body has 6 tasks. `mdscan tasks --tag auth` finds them all. `mdscan agenda --overdue` flags `[/]` on 2026-05-21. `mdscan board --by owner` shows alice has 4 open, bob has 2.

### 7.2 A retro file

```markdown
---
description: Q1 2026 retro for the platform team.
kind: decision
tags: [retro, platform]
last_updated: 2026-04-15
---

# Q1 Retro

## What worked
…

## What didn't
…

## Action items
- [x] Set up shared on-call rotation @alice done:2026-04-20
- [ ] Draft incident response playbook @bob due:2026-05-15
- [ ] Replace flaky CI runner @ops due:2026-05-01
```

`kind: decision` (it records the team's reflection and commitments). Action items are checkboxes. `mdscan tasks --owner @bob` finds bob's action item. The retro lives forever as the record of decisions; the items get checked off in place.

### 7.3 A spec file (the case for `tasks` was historically strongest here)

```markdown
---
description: Spec for the new OAuth provider.
kind: reference
tags: [auth, oauth, spec]
last_updated: 2026-05-14
---

# OAuth Provider Spec

## Functional requirements
1. Support Authorization Code + PKCE.
2. Issue JWT access tokens (RS256).
…

## Open questions
- [?] Token rotation interval? @alice
- [?] Refresh token storage — Redis or PG? @alice
```

Still `reference`. Specs are reference documents for what the system shall do. The open questions are tasks (state `[?]`). No `kind: spec` needed.

---

## 8. Two-axis decomposition: is one field enough?

Asked explicitly in the brief. Answer: **yes, one `kind` field is enough**, because the second axis (lifecycle/work) has been moved to a different level (per-item, in the body).

If we'd kept tasks at file-level, two axes would be required (`kind` + `status`). Moving tasks to item-level collapses the file-level work back to one axis (`kind` = content shape), with all the lifecycle stuff per-checkbox. Cleanest factoring available.

The third axis from the literature (`audience: human | agent | both`) remains deferred per the previous OPUS report. Not needed for the hybrid.

---

## 9. Trade-offs and risks

| Trade-off | What we give up | What we gain |
|---|---|---|
| Item-level tasks | Can't query "this whole doc is task-shaped" via frontmatter | All tasks queryable across the corpus uniformly; no awkward `kind: tasks` overlap |
| Five fixed states | Can't model "in review" or "ready for deploy" distinct states | Agent-predictable cross-project; can extend in config later |
| Single-line task syntax | Multi-line task descriptions impossible | `rg`/`awk`/`grep` work; parse is trivial; renders correctly in any GFM viewer |
| No emoji metadata | Loses Obsidian Tasks visual cuteness | Terminal-friendly; agent-friendly; no Unicode parsing risk |
| No dependencies field | Can't model `dependsOn:abc` in v1 | No reinventing Linear; body links cover 90% case |
| Drop `kind: tasks` | Existing roadmap/TODO files need re-classifying as `reference` | `kind` stays Diataxis-clean; cross-project agents trust the values |
| GFM checkboxes (not Org-style headings) | Tasks aren't full sections with body | Tasks are small; documents stay shallow; renders correctly everywhere |

The largest risk: **users may want the configurability Org-mode provides** (custom workflow states, logging on transitions). The mitigation: v1 ships fixed states, and if real users need more, `[tool.mdscan.tasks]` config can extend. Ship the opinionated default first.

---

## 10. What this changes in `spec-v0.4.md`

Summary of changes the hybrid proposal forces in the living spec:

1. **`kind` vocabulary**: drop `tasks`. Final values: `reference | guide | explanation | decision`. (Same as the previous OPUS conclusion — keep it.)
2. **New section: task syntax** documenting the GFM-checkbox + inline metadata convention (`@owner`, `due:`, `!priority`, `#tag`, optional `^id`).
3. **New section: five task states** (`[ ]`, `[/]`, `[x]`, `[-]`, `[?]`).
4. **CLI surface**: add `tasks`, `agenda`, `board`, `task add`, `task done|cancel|wait|start`.
5. **`mdscan --json` schema**: gains a `tasks` array per file.
6. **Phasing**: a new Phase 2.5 between "Graph and discovery" and "Human ergonomics" — "Task primitives".
7. **`Topics requiring deeper research` section**: "Knowledge organisation methodologies" now resolved; "tasks as item-level vs file-level" resolved (item-level).
8. **No new frontmatter fields.**

---

## Sources

- [Org-mode — Workflow states](https://orgmode.org/manual/Workflow-states.html)
- [Org-mode — TODO basics](https://orgmode.org/manual/TODO-Basics.html)
- [Org-mode — TODO extensions](https://orgmode.org/manual/TODO-Extensions.html)
- [Org-mode — Deadlines and scheduling](https://orgmode.org/manual/Deadlines-and-Scheduling.html)
- [Org-mode — Global TODO list / Agenda](https://orgmode.org/manual/Global-TODO-list.html)
- [Org-mode — Priorities](https://orgmode.org/manual/Priorities.html)
- [Org-mode — Agenda performance](https://orgmode.org/worg/agenda-optimization.html)
- [Org-mode — How many files?](https://orgmode.org/worg/topics/how-many-files.html)
- [Karl Voit — Current Org-mode files and heading structure](https://karl-voit.at/2020/05/03/current-org-files/)
- [Logseq — Task states discussion](https://discuss.logseq.com/t/todo-doing-how-to-use-this-where-are-other-statuses/25909)
- [Logseq — NOW/NEXT/LATER workflow](https://discuss.logseq.com/t/now-next-later-tasks-workflow/3703)
- [Jake Chanenson — Logseq for task management](https://jakec007.github.io/2025-12-01-logseq1/)
- [meain — Logseq task management](https://blog.meain.io/2023/logseq-task-management/)
- [Obsidian Tasks — About task formats](https://publish.obsidian.md/tasks/Reference/Task+Formats/About+Task+Formats)
- [Obsidian Tasks — Dataview format reference](https://publish.obsidian.md/tasks/Reference/Task+Formats/Dataview+Format)
- [Obsidian Tasks — Emoji format reference](https://publish.obsidian.md/tasks/Reference/Task+Formats/Tasks+Emoji+Format)
- [Obsidian Tasks — Filters](https://publish.obsidian.md/tasks/Queries/Filters)
- [Obsidian Tasks — Global filter](https://publish.obsidian.md/tasks/Getting+Started/Global+Filter)
- [Obsidian Dataview — Metadata on tasks and lists](https://blacksmithgu.github.io/obsidian-dataview/annotation/metadata-tasks/)
- [TaskPaper — Getting started](https://guide.taskpaper.com/getting-started/)
- [OmniFocus TaskPaper reference](https://support.omnigroup.com/omnifocus-taskpaper-reference/)
- [Plaintext GTD using TaskPaper syntax](https://katanist.com/2020/02/18/plaintext-gtd-using-taskpaper-syntax/)
- [todo.txt format specification](https://github.com/todotxt/todo.txt)
- [todo.txt — Plaintext productivity](https://plaintext-productivity.net/1-03-how-i-organize-my-todo-txt-file.html)
- [GitHub — About tasklists](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/about-tasklists)
- [GitHub — Task lists in GFM](https://github.blog/news-insights/product-news/task-lists-in-gfm-issues-pulls-comments/)
- [GitHub task_list repo](https://github.com/github/task_list)
- [GitHub Projects — Understanding fields](https://docs.github.com/en/issues/planning-and-tracking-with-projects/understanding-fields)
- [GitHub Projects — Customizing the board layout](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/customizing-the-board-layout)
- [Linear — Issue status (workflows)](https://linear.app/docs/configuring-workflows)
- [Linear — Conceptual model](https://linear.app/docs/conceptual-model)
- [Linear — Project status](https://linear.app/docs/project-status)
- [Notion — Getting started with projects and tasks](https://www.notion.com/help/guides/getting-started-with-projects-and-tasks)
- [Notion — Connected project management](https://www.notion.com/help/guides/accomplish-more-with-connected-project-management)
- [Notion — Task databases](https://www.notion.com/help/guides/give-your-to-dos-a-home-with-task-databases)
- [Things 3 — Using headings in projects](https://culturedcode.com/things/support/articles/2803577/)
- [Things 3 — TaskPaper export gist](https://gist.github.com/brokosz/4674002446b9dedf796feeedfbaf4a86)
- [Dendron — Tasks](https://wiki.dendron.so/notes/SEASewZSteDK7ry1AshNG/)
- [Dendron — Schemas](https://wiki.dendron.so/notes/c5e5adde-5459-409b-b34d-a0d75cbb1052/)
- [Foam — Documentation](https://docs.foamnotes.com/)
- [Foam — GitHub](https://github.com/foambubble/foam)
- [Markwhen — Introduction](https://docs.markwhen.com/)
- [Markwhen — GitHub](https://github.com/mark-when/markwhen)
- [Bullet Journal — Rapid logging](https://bulletjournal.com/blogs/faq/what-is-rapid-logging-understand-rapid-logging-bullets-and-signifiers)
- [Bullet Journal — Method overview](https://bulletjournal.com/blogs/faq/what-is-the-bullet-journal-method)
- [GTD — 15-minute pragmatic guide](https://hamberg.no/gtd)
- [GTD — Wikipedia](https://en.wikipedia.org/wiki/Getting_Things_Done)
- [PARA — Tiago Forte](https://fortelabs.com/blog/para/)
- [PARA — Todoist productivity methods](https://www.todoist.com/productivity-methods/para-method)
- [Kanban — Kanban University guide](https://kanban.university/kanban-guide/)
- [Kanban — Atlassian board](https://www.atlassian.com/agile/kanban/boards)
- [MADR — Markdown ADRs](https://adr.github.io/madr/)
- [Joel Parker Henderson — ADR collection](https://github.com/joelparkerhenderson/architecture-decision-record)
