---
description: Deep survey of Obsidian's query surfaces (Search, Dataview DQL, Dataview JS, Bases) with side-by-side use-case examples and concrete mdscan CLI adaptations.
---

# Obsidian Query Survey — For mdscan Query CLI Design

**Date**: 2026-05-14
**Purpose**: Ground the mdscan query CLI design in Obsidian's proven patterns. Every claim is backed by fetched docs.

---

## 1. Built-in Search — Operator Syntax

Obsidian's search panel is the baseline: no installation, no config, always available. Its operator set is richer than most users realise.

**Scoping operators** (restrict the field being searched):

```
file:auth                  # filename contains "auth"
path:decisions/auth        # file path contains the string
tag:#auth                  # has this tag (# prefix required)
section:"background"       # text appears inside a heading section
line:"jwt token"           # text appears on a single line
block:"see also"           # text appears in a block (paragraph / list item)
```

**Task operators** (useful for task-oriented vaults):

```
task:auth          # any task mentioning auth
task-todo:auth     # unchecked task only
task-done:auth     # checked task only
```

**Case and regex:**

```
match-case:Auth       # case-sensitive literal
ignore-case:AUTH      # force case-insensitive (default for plain terms)
/^auth.*/             # regex (delimited by slashes)
```

**Boolean precedence** — space = AND, `OR` is explicit, `NOT` or `-` negates:

```
auth jwt                  # AND (implicit)
auth OR jwt               # OR
auth NOT deprecated        # AND NOT
-deprecated auth           # same, minus prefix
"jwt token"               # exact phrase
(auth OR jwt) deprecated  # parentheses for grouping
```

**What it can't do**: no structured frontmatter field queries. `tag:` only matches Obsidian's `#tag` syntax, not arbitrary frontmatter list fields like `kind: decision`. There is no `field:value` operator for arbitrary properties. This is the fundamental gap that drove Dataview's adoption.

---

## 2. Quick Switcher and Quick Switcher++

The built-in Quick Switcher (Ctrl+O) does fuzzy filename matching with alias resolution. If a note has `aliases: [API gateway]`, typing "api gateway" finds it. No field-level filtering.

Quick Switcher++ (community plugin) adds mode triggers — single characters that switch the search model:

| Character | Mode |
|-----------|------|
| `#` | Heading search across all files |
| `@` | Symbols (headings, links) within highlighted file |
| `>` | Command palette |
| `'` | Bookmarks |
| `~` | Related items (by link graph) |
| `+` | Workspace layouts |

There is **no tag-prefix operator** for filtering by arbitrary frontmatter in either switcher. The `#` trigger searches *headings*, not tags. This is a design choice: switchers are navigation tools, not query tools — they return one file to open, not a set.

**CLI translation note**: the switcher model is irrelevant for mdscan. A CLI `mdscan query` command is already a "full corpus" query, not a navigation action.

---

## 3. Dataview (DQL — Dataview Query Language)

Dataview is the community-built SQL-for-markdown layer that became effectively mandatory in power vaults. It embeds in notes as fenced code blocks tagged `dataview`.

### Query anatomy

```
TABLE field1, field2, field3
FROM <source>
WHERE <condition>
SORT <field> [ASC|DESC]
GROUP BY <field>
LIMIT <n>
FLATTEN <list-field>
```

Only the output type (`TABLE`, `LIST`, `TASK`, `CALENDAR`) is mandatory. Every other clause is optional.

### FROM sources

```dataview
FROM #auth                        -- tag and all subtags
FROM "decisions"                  -- folder (quoted, subfolders included)
FROM "decisions/auth-flow.md"     -- single file
FROM [[some-moc]]                 -- pages that link TO this note (inlinks)
FROM outgoing([[some-moc]])       -- pages that this note links TO (outlinks)
FROM #auth AND "decisions"        -- AND composition
FROM #auth OR #jwt                -- OR composition
FROM #auth AND -"archive"         -- AND NOT (dash negation)
```

### Implicit fields (always available, no frontmatter needed)

```
file.name        -- filename without extension
file.path        -- vault-relative path
file.folder      -- containing folder path
file.tags        -- all tags including frontmatter and inline
file.etags       -- tags without subtags expanded
file.outlinks    -- all wikilinks in the file
file.inlinks     -- all pages that link to this page
file.ctime       -- creation time
file.mtime       -- modification time
file.size        -- bytes
```

### WHERE expressions

```dataview
WHERE kind = "decision"
WHERE contains(tags, "#auth")
WHERE contains(tags, "#auth") AND contains(tags, "#jwt")
WHERE kind = "guide" AND !contains(tags, "#deprecated")
WHERE kind = "decision" OR kind = "spec"
WHERE contains(tags, "#auth") OR contains(tags, "#jwt")
```

The `contains(list, value)` function is the workhorse for list-typed fields. `icontains()` is case-insensitive. `all()` and `any()` handle predicate aggregation over lists:

```dataview
WHERE all(tags, (t) => t != "#deprecated")
WHERE any(tags, (t) => t = "#auth" OR t = "#jwt")
```

### FLATTEN for list expansion

When a frontmatter field like `tags` is a list, `FLATTEN` unnests it so each tag gets its own row — useful for GROUP BY:

```dataview
TABLE file.name
FROM "decisions"
FLATTEN tags AS tag
GROUP BY tag
```

### Inline fields (non-YAML alternative)

Inline fields use `::` and can appear anywhere in the document body:

```markdown
Status:: In Progress
Priority:: [high:: true]
```

These are queryable alongside frontmatter fields. Useful for adding metadata mid-paragraph without touching YAML.

---

## 4. Dataview Inline JS (`dataviewjs`)

When DQL hits its ceiling, `dataviewjs` blocks give you the full JavaScript runtime against the vault index.

```javascript
// dataviewjs block
const pages = dv.pages("#auth")
  .where(p => p.kind === "decision")
  .sort(p => p.file.mtime, "desc");

dv.table(["File", "Kind", "Tags"], 
  pages.map(p => [p.file.link, p.kind, p.file.tags]));
```

**When DQL is insufficient and JS is needed:**

1. **Set intersection with custom logic** — checking that `tags` contains *both* `#auth` AND `#jwt` is possible in DQL with nested `contains()`, but complex multi-field intersections become unwieldy.
2. **Dynamic self-referential queries** — e.g. "all notes similar to the current note" using `dv.current()` and comparing field values programmatically.
3. **Custom rendering** — generating HTML tables, collapsible sections, progress bars; DQL's output is fixed.
4. **File I/O** — reading file contents, not just metadata; DQL only sees the index.
5. **External data integration** — fetch an API, merge with vault data.

**Tradeoffs**: JS blocks are harder to read for non-programmers, cannot be statically analysed or cached as easily, and break if Dataview's API changes. DQL is declarative and portable; JS is imperative and fragile. The existence of a large `dataviewjs` community is a signal that DQL has meaningful expressiveness gaps.

---

## 5. Bases — Obsidian's First-Party Answer to Dataview

Bases (shipped in Obsidian 1.8+, syntax updated breaking in 1.9.2) are `.base` files — a YAML-based filter-and-view format that Obsidian renders as a spreadsheet-like table with multiple named views over the same corpus.

### Key design differences from Dataview

| Aspect | Dataview (DQL) | Bases |
|--------|---------------|-------|
| Format | Fenced code block in `.md` | Dedicated `.base` file type |
| Syntax | SQL-ish text DSL | YAML filter objects + formula strings |
| Logic operators | `AND`, `OR`, `NOT` keywords | `&&`, `\|\|`, `!` (JS-style operators) |
| UI | Read-only rendered output | Editable spreadsheet, inline property editing |
| Multiple views | One query = one view | Multiple named views over one corpus |
| Scope | Whole vault or filtered | Always whole vault, filtered per view |

### Filter syntax (post-1.9.2)

Filters are formula strings evaluating to boolean:

```yaml
# .base file structure
filter: 'file.hasTag("auth")'
```

```yaml
# AND
filter: 'file.hasTag("auth") && kind == "decision"'

# OR
filter: 'file.hasTag("auth") || file.hasTag("jwt")'

# NOT
filter: '!file.hasTag("deprecated")'

# Folder scoping
filter: 'file.inFolder("decisions")'

# List-field contains (property-level method)
filter: 'related.contains(this)'   # self-referential: "links to current file"
```

### Built-in file functions (post-1.9.2 naming)

```
file.hasTag("name")        -- tag membership
file.inFolder("path")      -- folder scope
file.hasLink("target")     -- links to target
file.ctime, file.mtime     -- timestamps
```

**What Bases is good at**: live-editable property spreadsheets where the user wants to bulk-edit frontmatter across many files — e.g. updating `status` fields on a project board. It is a *data entry* UX as much as a *query* UX.

**What Bases doesn't have**: `GROUP BY`, `FLATTEN`, `SORT` with complex expressions, or anything resembling relational joins. The mental model is "filtered table of files with computed columns," not "relational query."

**Why it was introduced**: Dataview is read-only by design (it queries, doesn't write). Bases closes the write-back loop. It also avoids the plugin dependency — Dataview requires a third-party install; Bases is core.

---

## 6. Community Plugins — Semantic and Fuzzy Alternatives

**Omnisearch** — full-text search with fuzzy matching and BM25 ranking. No structured operators. The model is: "find files where any content resembles this query." Useful for semantic proximity, not field-level filtering. Not useful for our use cases.

**Smart Connections** — vector-embedding similarity search. Returns the N most semantically similar notes. Zero structured query capability. Entirely orthogonal to what we need.

**Another Quick Switcher** — alternative to Quick Switcher++ with finer-grained mode triggers and tag/path filtering baked in. Adds `tag:` and `folder:` prefix operators to the fuzzy search box. Still navigation-oriented (returns one file), not corpus-query-oriented.

**Verdict for mdscan**: none of these community plugins offer a pattern worth stealing for a CLI query language. The structured query patterns all live in Dataview/Bases.

---

## 7. Frontmatter Properties — Typed Fields

Obsidian's Properties feature (added in 2023, mature by 2024) renders frontmatter YAML as a typed form in the editor. The types are: `text`, `list`, `number`, `date`, `datetime`, `checkbox`.

```yaml
---
kind: decision          # text
tags:                   # list
  - auth
  - jwt
priority: 3             # number
due: 2024-06-01         # date
done: false             # checkbox
related:                # list of wikilinks
  - "[[auth-flow]]"
  - "[[token-refresh]]"
---
```

**How queries interact with types:**

- Dataview reads the YAML type as-is. Dates in ISO format become `date` objects, numbers are numeric, lists become arrays.
- `WHERE due < date(today)` works because Dataview coerces ISO dates.
- `WHERE priority > 2` works because the value is numeric.
- `WHERE contains(tags, "#auth")` works because `tags` is a list.
- Bases uses `.date()` method calls on string values for date coercion.

**The type system is implicit in Dataview, explicit in Bases.** Dataview infers types from YAML values; Bases has a typed schema per base. For mdscan, our corpus is simpler: all list fields are string lists, no date coercion needed initially.

---

## 8. Use Cases — Side-by-Side Comparison

| Use case | Built-in Search | Dataview DQL | Dataview JS | Bases |
|----------|----------------|-------------|-------------|-------|
| **(a) All decisions tagged auth** | `tag:#auth` (no `kind` field filtering possible) | `FROM #auth WHERE kind = "decision"` | `dv.pages("#auth").where(p => p.kind === "decision")` | `filter: 'file.hasTag("auth") && kind == "decision"'` |
| **(b) All guides except deprecated** | No `kind` field operator; approximate: `tag:#guide -tag:#deprecated` | `WHERE kind = "guide" AND !contains(file.tags, "#deprecated")` | `.where(p => p.kind === "guide" && !p.file.tags.includes("#deprecated"))` | `filter: 'kind == "guide" && !file.hasTag("deprecated")'` |
| **(c) All docs tagged auth OR jwt** | `tag:#auth OR tag:#jwt` | `FROM #auth OR #jwt` | `dv.pages("#auth OR #jwt")` | `filter: 'file.hasTag("auth") \|\| file.hasTag("jwt")'` |
| **(d) All decisions OR specs tagged auth** | `tag:#auth` (no kind filter) — **cannot express** | `FROM #auth WHERE kind = "decision" OR kind = "spec"` | `.where(p => ["decision","spec"].includes(p.kind) && p.file.tags.includes("#auth"))` | `filter: 'file.hasTag("auth") && (kind == "decision" \|\| kind == "spec")'` |
| **(e) Children of a specific MOC** | **Cannot express** (no frontmatter field traversal) | `WHERE contains(file.outlinks, [[my-moc]])` or `FROM outgoing([[my-moc]])` | `dv.page("my-moc").children.map(c => dv.page(c))` | `filter: 'related.contains("my-moc")'` (approximate) |
| **(f) Files that link to X** | **Cannot express** (no backlink query) | `FROM [[X]]` | `dv.pages("[[X]]")` | `filter: 'file.hasLink("X")'` |
| **(g) Tags include both auth AND jwt** | `tag:#auth tag:#jwt` (AND is implicit — **works!**) | `WHERE contains(file.tags, "#auth") AND contains(file.tags, "#jwt")` | `.where(p => p.file.tags.includes("#auth") && p.file.tags.includes("#jwt"))` | `filter: 'file.hasTag("auth") && file.hasTag("jwt")'` |

**Key findings from the table:**

- Built-in Search handles tag queries and set intersection (g) but is **blind to arbitrary frontmatter fields** (kind, children, related). Cases (d), (e), (f) are simply impossible.
- Dataview DQL handles all 7 cases cleanly. It is the unambiguous winner for structured queries.
- Dataview JS adds no expressive power for these 7 cases — it is a verbosity cost with no benefit here.
- Bases handles all 7 cases, but with a different syntax and the relational case (e) requires workarounds.

---

## 9. What Works Well in Obsidian's Design

**FROM as the corpus gate.** Separating "which files are in scope" (`FROM`) from "which of those match" (`WHERE`) is the right cut. It maps to how agents think: "give me the decision files, then filter them." mdscan should steal this two-layer model.

**Implicit file fields.** `file.name`, `file.path`, `file.tags`, `file.inlinks`, `file.outlinks` — these are always available with no schema declaration. Zero-ceremony introspection. Any agent can query these without knowing the vault schema.

**contains() as the canonical list predicate.** A single function handles all "does this list-field include X" queries. The pattern `WHERE contains(field, value)` is instantly readable and composable with AND/OR.

**FROM [[note]] for backlinks.** Expressing "all pages that link to X" as a source rather than a WHERE predicate is elegant — it puts the relational traversal in the right place.

**Operator precedence that matches natural language.** Space = AND, `OR` explicit, parentheses for grouping. Matches how a developer would write `grep -l auth . | grep -l jwt` intuitively.

---

## 10. What Doesn't Work Well

**Built-in Search's field blindness.** The most-used query surface can't filter on `kind`, `status`, or any custom frontmatter property. This drove the entire Dataview ecosystem. The lesson: a query tool for structured markdown *must* treat frontmatter fields as first-class query targets.

**Dataview's read-only nature.** You can query but not write. Every "I want to bulk-update status to done" workflow falls outside Dataview. This is why Bases exists. For mdscan the corollary is that `mdscan set-description` filling in frontmatter is a distinct and necessary primitive alongside the query command.

**The escape to `dataviewjs`.** The fact that a large percentage of Dataview vaults contain `dataviewjs` blocks is a smell. It means DQL has expressiveness gaps. The primary gap is **complex multi-step computation** (e.g. "find all notes whose similarity score to the current note exceeds a threshold"). For mdscan's use cases, DQL-level expressiveness is sufficient — we should not import this complexity.

**Bases' breaking API changes.** The 1.9.2 rename (`taggedWith` → `file.hasTag`, `linksTo` → `file.hasLink`) broke every existing Bases file. Lesson: a CLI's query syntax must be stable — semver-guard the query language as part of the public API.

**Embedded live queries are a GUI concept.** Dataview and Bases embed queries *in* notes and re-evaluate on every view. This is a killer feature in a GUI: you open your MOC note and its table is always fresh. In a CLI, it is irrelevant — the agent runs `mdscan query` on demand and captures stdout. Do not try to emulate embedded queries.

---

## 11. What's Specific to Obsidian's GUI (Don't Translate)

- **Live re-evaluation** of queries embedded in notes on every file open.
- **Spreadsheet editing** in Bases — clicking a cell to edit `status` directly in the query result.
- **Graph view** — the 2-D force-directed vault topology is purely visual.
- **Properties form** — Obsidian renders frontmatter as a typed input form; irrelevant for CLI consumers.
- **Calendar view** (`CALENDAR` query type in Dataview) — date-based dot visualisation.
- **Quick Switcher** — navigation to *open* a file; our CLI agent does not "open" files.

---

## 12. Concrete Adaptations for mdscan

### Adaptation 1 — Two-layer query: `--from` + `--where`

Steal Dataview's FROM/WHERE split directly. `--from` defines the corpus; `--where` filters it.

```bash
# Equivalent to: FROM #auth WHERE kind = "decision"
mdscan query --from 'tags:auth' --where 'kind=decision'

# Equivalent to: FROM "decisions" WHERE contains(tags, "#auth")
mdscan query --from 'path:decisions' --where 'tags:auth'
```

`--from` accepts: `path:<glob>`, `tags:<name>`, `links:<file>` (backlinks), `children:<file>` (outlinks of a specific file's `children` field). `--where` accepts field-equality and `contains` predicates. This makes corpus scoping explicit and separate from row filtering — identical cognitive model to DQL, but shell-native.

### Adaptation 2 — `field:value` as the universal predicate syntax

Borrow Obsidian's search panel's `operator:value` style but extend it to arbitrary frontmatter fields. Every frontmatter key becomes a valid filter prefix:

```bash
mdscan query kind:decision tags:auth
# AND is implicit (space-separated)

mdscan query kind:decision,spec tags:auth
# comma = OR within a field (kind is decision OR spec)

mdscan query tags:auth,jwt
# comma = OR: tagged auth OR jwt

mdscan query tags:auth tags:jwt
# space = AND: tagged auth AND jwt
```

This syntax is unambiguous, shell-safe (no quoting needed for simple cases), and directly readable. Comma-within-field means OR; space-between-predicates means AND. This resolves use cases (a), (b), (c), (d), (g) without any special syntax.

### Adaptation 3 — Relational traversal via `--from children:<file>` and `--from links:<file>`

Steal Dataview's `FROM [[note]]` (backlinks) and `FROM outgoing([[note]])` (outlinks) as named `--from` modes:

```bash
# (e) Children of a specific MOC
mdscan query --from 'children:docs/auth-moc.md'
# Reads the "children" frontmatter list of auth-moc.md, returns those files

# (f) All files that link to X
mdscan query --from 'links:docs/auth-flow.md'
# Scans all files for wikilinks or "related" references pointing to auth-flow.md
```

`children:<file>` reads the named file's `children` frontmatter field and returns those files. `links:<file>` inverts the index — finds all files that mention the target. These two operations cover the relational use cases without requiring a general join syntax.

### Adaptation 4 — Stable, semver-guarded syntax; no embedded queries

The lesson from Bases' 1.9.2 breaking changes: **treat the query syntax as a public API surface**. Any change to predicate syntax is a minor version bump at minimum. Document the grammar formally in `docs/`. Agents bake mdscan queries into prompts and scripts — silent syntax changes destroy them.

Also: do **not** support embedded queries in `.md` files (Dataview/Bases style). The mdscan agent pattern is `mdscan query ... | jq` or `mdscan query ... --format json`. Output is consumed by the agent process, not re-rendered in a note. Keep the tool stateless and stdout-first.

---

## Summary Judgement

Dataview DQL is the right reference point for mdscan's query language, not Obsidian's built-in search (too weak on frontmatter) and not Bases (too GUI-oriented). The three Dataview patterns to steal: FROM/WHERE separation, `contains()` for list fields, and `FROM [[note]]` for relational traversal. The one pattern to invert: DQL lives inside notes; mdscan query lives on the command line, which means shell-native syntax, stable semver, and stdout as the output channel.

---

*Sources consulted: [Dataview query structure](https://blacksmithgu.github.io/obsidian-dataview/queries/structure/), [Dataview data commands](https://blacksmithgu.github.io/obsidian-dataview/queries/data-commands/), [Dataview functions](https://blacksmithgu.github.io/obsidian-dataview/reference/functions/), [Dataview metadata](https://blacksmithgu.github.io/obsidian-dataview/annotation/add-metadata/), [Dataview JS API](https://blacksmithgu.github.io/obsidian-dataview/api/code-reference/), [Obsidian Bases intro](https://obsidian.md/help/bases), [Bases syntax](https://obsidian.md/help/bases/syntax), [Bases migration guide](https://forum.obsidian.md/t/bases-migration-quick-start-guide/101571), [Quick Switcher++](https://github.com/darlal/obsidian-switcher-plus)*
