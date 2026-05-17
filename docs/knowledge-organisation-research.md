---
description: Web-researched survey of knowledge-organisation methodologies (Diataxis, Zettelkasten, PARA, LATCH, ADRs, GitLab CTRT, etc.) used to validate and refine mdscan's `kind` frontmatter enum, with an opinionated recommendation.
---

# Knowledge-organisation methodologies and the `kind` frontmatter field

A survey of how the literature carves up documentation, followed by a concrete recommendation for mdscan's `kind` enum. Targeted at agent-readable project docs (not personal notes, not consumer-product help centres).

## 1. The methodologies, condensed

### 1.1 Diataxis (Procida)

The current de-facto standard for technical documentation. Four types, organised on two axes:

- **Tutorial** — learning-oriented; theoretical + acquisition. "Teach me by doing."
- **How-to guide** — task-oriented; practical + application. "Help me accomplish X."
- **Reference** — information-oriented; theoretical + application. "Tell me how X works."
- **Explanation** — understanding-oriented; practical + acquisition. "Help me understand why."

Classification criterion: **reader intent at moment of access** (am I learning? am I working? do I want skill or understanding?). Unit: a documentation *page*, not a folder. Scope: shared/team docs, public-facing or internal. The framework's loudest claim is that **mixing types in a single page is the principal cause of bad docs** — e.g. a tutorial that derails into reference, or a how-to that drifts into explanation ([Diataxis](https://diataxis.fr/), [Coderslingo summary](https://coderslingo.com/blog/diataxis-framework-documentation/)).

For `spec-v0.4.md`: Diataxis has nowhere clean to put it. A spec is partly reference (what the system shall do) and partly explanation (why), with embedded decisions. Diataxis would either force it into "explanation" or split it into multiple files.

### 1.2 GitLab CTRT

Concept / Task / Reference / Troubleshooting ([GitLab topic types](https://docs.gitlab.com/development/documentation/topic_types/)). A pragmatic re-spelling of Diataxis: "concept" = explanation, "task" = how-to, "reference" = reference, "troubleshooting" is the extra. Tutorial is treated as a *page-level* type, not a topic type, because GitLab found that most readers don't actually want tutorials in product docs — they want tasks. This is a meaningful divergence.

### 1.3 Good Docs / Microsoft / Google / Write the Docs

The Good Docs Project ships templates (tutorial, how-to, reference, concept, README, release notes, troubleshooting, glossary). Microsoft and Google style guides ([Google dev docs style](https://developers.google.com/style/)) prescribe *style* but stop short of mandating a taxonomy — they recognise reference, tutorial, conceptual overviews, release notes as practical genres. Write the Docs ([style guides page](https://www.writethedocs.org/guide/writing/style-guides/)) is explicitly pluralist: no consensus taxonomy. The de-facto industry consensus, where one exists, is **Diataxis ± troubleshooting ± release notes ± README**.

### 1.4 Zettelkasten / Ahrens / Atomic notes / MOCs

Ahrens' modern Zettelkasten distinguishes ([zettelkasten.de](https://zettelkasten.de/posts/concepts-sohnke-ahrens-explained/), [Bob Doto](https://writing.bobdoto.computer/what-is-a-permanent-note-correcting-some-common-misunderstandings/)):

- **Fleeting** — discarded within ~48h.
- **Literature** — your words on someone else's work.
- **Permanent** — atomic, linked, in your voice; the long-term store.
- **Project** — scoped to a current output.
- **Index / Structure / MOC** — pure navigation, no first-hand content ([Nick Milo / LYT](https://notes.linkingyourthinking.com/Cards/MOCs+Overview)).

Classification criterion: **note lifecycle and authorship provenance**, not reader intent. Unit: one atomic note (≪ a page). Scope: personal PKM. Andy Matuschak's Evergreen notes ([notes.andymatuschak.org](https://notes.andymatuschak.org/Evergreen_notes)) is a *quality standard* layered on top (atomic, concept-oriented, densely linked), not a category.

The relevant insight for mdscan: Zettelkasten's categories are **not interchangeable with Diataxis's**. They classify a different question. "Permanent" is not "reference"; it is "I have invested in this and link to it from elsewhere".

### 1.5 PARA (Forte)

Projects / Areas / Resources / Archives ([fortelabs.com](https://fortelabs.com/blog/para/)). The criterion is explicitly **actionability/lifecycle**, not content type:

- **Project** — bounded, has a finish.
- **Area** — ongoing responsibility, no finish.
- **Resource** — topic-of-interest, may feed projects/areas.
- **Archive** — inactive items from the other three.

Unit: a folder of items. Scope: personal but trivially extends to teams. PARA explicitly **competes with subject-based organisation** — it argues you should organise by what you're going to *do* with material, not by what the material *is*.

For `spec-v0.4.md`: PARA labels it a Project (it has a v0.4 deliverable). Once shipped, it becomes an Area document.

### 1.6 LATCH (Wurman)

Location / Alphabet / Time / Category / Hierarchy ([thevisualcommunicationguy.com](https://thevisualcommunicationguy.com/2013/07/20/the-five-and-only-five-ways-to-orgaize-information/)). Five orthogonal sorting *lenses*, not a content typology. LATCH is what you reach for when designing the *index* over your docs (sort by date? alphabetic? by category?). Relevant to mdscan's `scan` and `tree` commands, irrelevant to `kind`.

### 1.7 CODE / Building a Second Brain

Capture / Organise / Distill / Express ([fortelabs.com](https://fortelabs.com/blog/basboverview/)). A *workflow*, not a taxonomy. Not a candidate for `kind`.

### 1.8 Johnny.Decimal

A folder-numbering addressing scheme (`15.22`, [johnnydecimal.com](https://johnnydecimal.com/)). Hierarchical category encoding, capped at 10×10. It tells you *where* a file lives, not *what kind* it is. Orthogonal to `kind`; can coexist.

### 1.9 ADRs and cousins

[Joel Parker Henderson's ADR collection](https://github.com/joelparkerhenderson/architecture-decision-record) confirms ADRs are an established, separately-named genre. The wider family ([Pragmatic Engineer on RFCs/Design docs/ADRs](https://newsletter.pragmaticengineer.com/p/rfcs-and-design-docs), [Candost](https://candost.blog/adrs-rfcs-differences-when-which/)):

- **RFC** — proposes; collects feedback; pre-decision.
- **Design doc** — describes how a feature will be implemented; pre/peri-decision.
- **ADR** — records an architectural decision after the fact; post-decision, immutable.

All three are absent from Diataxis. They sit awkwardly between explanation (why) and reference (what was decided). The industry treats "decision" as a real, distinct genre.

### 1.10 Runbooks vs playbooks vs post-mortems

[Cortex](https://www.cortex.io/post/runbooks-vs-playbooks), [TechTarget](https://www.techtarget.com/searchitoperations/tip/Compare-runbooks-vs-playbooks-for-IT-process-documentation): runbook = "how" (step-by-step technical procedure for a single task); playbook = "what and why" (strategic, multi-task, decision-bearing). Post-mortem ([PagerDuty](https://www.pagerduty.com/blog/postmortems-vs-retrospectives/)) is incident-triggered root-cause analysis; retrospective is cadence-driven team improvement. They overlap but aren't aliases. In Diataxis, runbooks are how-tos; playbooks are how-to + explanation; post-mortems are a mix of reference (timeline) + explanation (cause).

## 2. Comparison matrix

Rows = example documents; columns = how each framework classifies them. "—" = the framework has no obvious slot.

| Example doc | Diataxis | GitLab CTRT | Zettelkasten | PARA | Industry |
|---|---|---|---|---|---|
| ADR ("we chose Postgres") | Explanation (forced) | Reference (forced) | Permanent | Resource | ADR |
| Setup guide ("install in 5 min") | Tutorial | Task (page=tutorial) | — | Resource | Tutorial |
| API reference | Reference | Reference | — | Resource | Reference |
| Roadmap v0.4 | — | — | Project note | Project | Roadmap |
| Sprint retrospective | Explanation (forced) | — | Project note | Project→Archive | Retro |
| Glossary | Reference | Reference | Index / MOC | Resource | Glossary |
| "Hello world" tutorial | Tutorial | Tutorial (page) | — | Resource | Tutorial |
| Incident runbook | How-to | Task | — | Area | Runbook |
| Post-mortem | Explanation (forced) | Troubleshooting (forced) | Permanent | Archive | Post-mortem |
| `spec-v0.4.md` (living spec) | Reference + Explanation (mix!) | Reference + Concept (mix!) | Project | Project | Design doc |
| README | Reference + Tutorial (mix) | Top-level page | Index | Resource | README |

**Convergence:** Reference/API doc, tutorial, and how-to/task are recognised by *every* framework that classifies content. These are the bedrock.

**Divergence — and what each divergence reveals:**

- **Decisions** (ADR/RFC) only appear in the industry-pattern column. Diataxis and GitLab CTRT have no native slot. This is a real gap — confirmed by the fact that the industry invented a new genre.
- **Roadmaps/retros/post-mortems/specs** only appear in PARA (lifecycle) and industry. Diataxis has nothing because Diataxis is about content shape, not workflow position. **This reveals a second axis the literature implicitly acknowledges: lifecycle/temporality.**
- **READMEs and specs** are mixtures by nature. Diataxis says "split them"; reality says "keep them" because the unit of distribution (a repo, a feature) demands a single entry point.

## 3. The `kind` question

### 3.1 Is `reference | guide | decision | tasks` defensible?

Yes, partly, and the mismatches are instructive.

- **`reference`** — full overlap with Diataxis "reference" and GitLab "reference". Bedrock. Keep.
- **`guide`** — conflates Diataxis "tutorial" + "how-to" + "explanation". This is the **biggest divergence from the literature**, and it's a deliberate choice mdscan must justify. The merge is defensible for an agent audience: an agent doesn't need a tutorial-vs-how-to distinction because it isn't learning, it's executing. But Diataxis's central warning — that mixing causes confusion — still applies if a `guide` simultaneously teaches concepts, prescribes steps, and explains rationale. For a *human* reader of an agent-written guide, the same anti-pattern hurts.
- **`decision`** — has no Diataxis slot, but is universally recognised in industry (ADR/RFC/design doc). Keep. This is where mdscan's enum is **better than Diataxis** for software-project docs.
- **`tasks`** — closest to PARA's "Project", not to Diataxis at all. It classifies by *lifecycle*, not by content shape. This is the second axis showing up uninvited inside a one-axis enum, and that's a smell.

### 3.2 Should we adopt Diataxis instead?

Tempting (industry standard, well-thought-out), but no. Two reasons:

1. **Diataxis has no `decision`.** Folding ADRs into "explanation" loses the most important property of a decision doc: it is a *commitment*, not a description. Industry split it out for a reason.
2. **Diataxis classifies user need, not document.** Diataxis is about reader-moment ("am I learning now?"). For *agent* consumers picking docs to load into context, the more useful classification is content-shape ("is this an authoritative spec, a procedure, a recorded choice, or an in-flight plan?"). These overlap but are not the same.

### 3.3 Hybrid options

The least-bad enum is **Diataxis-extended with `decision`, with `tutorial`/`how-to`/`explanation` collapsed where the agent audience doesn't need the distinction**:

`reference | guide | explanation | decision`

— where `guide` covers tutorial + how-to (action-oriented, "you do X"), `explanation` covers conceptual/rationale (atemporal "why"), and `decision` covers ADR/RFC/design-doc (a recorded commitment).

`tasks` is the problem. It is a *lifecycle marker*, not a content kind. Mixing it into `kind` is a category error. See §4.

### 3.4 The PARA / lifecycle angle

PARA reveals that `tasks` is a lifecycle label. mdscan currently smuggles lifecycle into `kind`, which means a roadmap and a spec — both Project-stage Reference-shape docs — must pick *one* `kind`. That forces a false choice. The cleaner factoring is two fields:

- `kind` = content shape (reference / guide / explanation / decision)
- `status` = lifecycle (draft / active / shipped / archived) — or PARA-style (project / area / resource / archive)

A roadmap is then `kind: reference, status: project`. A shipped spec is `kind: reference, status: archived`. An ADR is `kind: decision, status: active`. This collapses cleanly when needed (an agent that only cares about `kind` ignores `status`).

## 4. Multi-axis classification

Diataxis is openly two-axis but **collapses to four named cells**. LATCH is five orthogonal lenses but is about *sorting*, not classifying. PARA is one axis (actionability). The literature splits roughly 50/50.

For mdscan, **one-axis `kind` is too thin** — the matrix in §2 demonstrates this: roadmaps and specs evade any one-axis taxonomy. The honest answer is two-axis minimum:

- **`kind`** (content shape; required) — what the doc *is*.
- **`status`** (lifecycle; optional, defaults `active`) — where the doc is in its life.

A third optional axis (`audience: human | agent | both`) is plausible but probably premature. Don't ship it until a use case demands it. YAGNI for the third axis; ship the second.

## 5. The atomicity question

Zettelkasten and Evergreen notes assume **one idea per file** (≪ a page). Diataxis assumes a *page* (≥ one screen, ≤ one feature). ADRs assume *one decision per file*. There is no universal answer.

`kind` makes sense at Diataxis granularity (a page covers one shape) and at ADR granularity (one decision per file). It **breaks down at Zettelkasten granularity**: a single atomic note is too small to be classified usefully — most atomic notes would just be `kind: explanation`. It also breaks down at *monolith* granularity (a single 4000-line `docs.md` covering everything): no single `kind` fits.

mdscan should **document its granularity assumption explicitly**: one `kind` per file, and files are expected to be page-sized, single-purpose. This is implicitly a Diataxis-compatible stance. It also implies a quality rule: if you can't pick one `kind` for a file, split the file. (This is Diataxis's central rule, restated.)

## 6. Recommendation

### 6.1 Revise the enum

Drop `tasks` from `kind`. Replace with explicit two-field metadata:

```yaml
kind: reference   # required: reference | guide | explanation | decision
status: active    # optional: draft | active | shipped | archived (default: active)
```

Rationale:

- `reference | guide | explanation | decision` is **Diataxis-aligned** (industry-recognisable) with two pragmatic adaptations: tutorial+how-to merged into `guide` (agent audience), and `decision` added (ADR/RFC/design-doc — a universally-recognised genre Diataxis omits).
- Removing `tasks` from `kind` fixes a category error: `tasks` was a lifecycle marker masquerading as content shape. A roadmap is still a roadmap — it's `kind: reference, status: draft` (or `status: project` if you adopt PARA terminology).
- The four-value enum stays small enough that an agent can memorise it.

### 6.2 Configurable or opinionated?

**Ship an opinionated default, allow extension, forbid redefinition.** Specifically:

- The four canonical `kind` values are fixed and documented in mdscan itself.
- `pyproject.toml` `[tool.mdscan]` may add *extra* project-specific kinds (e.g. `tutorial` if a project genuinely wants Diataxis's full four; `runbook` for an SRE-heavy project) but cannot remove or redefine the four canonical ones.
- This keeps cross-project agents predictable while permitting local nuance.

### 6.3 Companion fields worth considering

- **`status`** — strongly recommended (see §3.4). Solves the lifecycle conflation that motivated `tasks`.
- **`audience`** — defer until needed. Most agent docs are dual-audience and the field would be noise.
- **`maturity`** — overlaps with `status`. Don't add both.
- **`description`** — already required by mdscan. Keep central.

### 6.4 Guidance mdscan should ship

A short, opinionated chooser, embedded in `mdscan --help` and the README:

1. Does the file record **a commitment** (we chose X, we will do Y)? → `decision`.
2. Does the file primarily tell the reader **how to do something** (commands, steps)? → `guide`.
3. Does the file primarily tell the reader **what something is** (API, config keys, glossary)? → `reference`.
4. Does the file primarily tell the reader **why something is the way it is** (concepts, rationale, background)? → `explanation`.
5. **Can't pick one?** The file is mixing concerns. Split it. (Diataxis's central rule.)
6. Is the file in-flight (a roadmap, a draft spec)? Pick the *eventual* `kind` and set `status: draft`.

### 6.5 What this is not

This is not a claim that `kind` should be dropped in favour of free-form tags. Tags are good for *facets* (topic, component, version), terrible for *primary genre*, because the agent needs to know "is this authoritative or aspirational?" before it reads the body. `kind` answers that question in 1 token. Keep it.

## Sources

- [Diataxis framework](https://diataxis.fr/) — Procida.
- [Diataxis: Start here](https://diataxis.fr/start-here/).
- [Diataxis Framework Explained — Coderslingo](https://coderslingo.com/blog/diataxis-framework-documentation/).
- [I'd Rather Be Writing on Diataxis](https://idratherbewriting.com/blog/what-is-diataxis-documentation-framework).
- [GitLab CTRT topic types](https://docs.gitlab.com/development/documentation/topic_types/).
- [GitLab tutorial page type](https://docs.gitlab.com/development/documentation/topic_types/tutorial/).
- [Good Docs Project](https://www.thegooddocsproject.dev/).
- [Google developer documentation style guide](https://developers.google.com/style/).
- [Write the Docs — Style guides](https://www.writethedocs.org/guide/writing/style-guides/).
- [Zettelkasten Method overview](https://zettelkasten.de/posts/overview/).
- [Ahrens' note types explained — zettelkasten.de](https://zettelkasten.de/posts/concepts-sohnke-ahrens-explained/).
- [Bob Doto on permanent notes](https://writing.bobdoto.computer/what-is-a-permanent-note-correcting-some-common-misunderstandings/).
- [Andy Matuschak — Evergreen notes](https://notes.andymatuschak.org/Evergreen_notes).
- [Nick Milo / LYT — MOCs](https://notes.linkingyourthinking.com/Cards/MOCs+Overview).
- [PARA — Forte](https://fortelabs.com/blog/para/).
- [Building a Second Brain / CODE — Forte](https://fortelabs.com/blog/basboverview/).
- [LATCH — Visual Communication Guy](https://thevisualcommunicationguy.com/2013/07/20/the-five-and-only-five-ways-to-orgaize-information/).
- [Johnny.Decimal](https://johnnydecimal.com/).
- [Joel Parker Henderson — ADR collection](https://github.com/joelparkerhenderson/architecture-decision-record).
- [Pragmatic Engineer — RFCs, design docs, ADRs](https://newsletter.pragmaticengineer.com/p/rfcs-and-design-docs).
- [Candost — ADRs vs RFCs](https://candost.blog/adrs-rfcs-differences-when-which/).
- [Cortex — Runbooks vs playbooks](https://www.cortex.io/post/runbooks-vs-playbooks).
- [TechTarget — Runbooks vs playbooks](https://www.techtarget.com/searchitoperations/tip/Compare-runbooks-vs-playbooks-for-IT-process-documentation).
- [PagerDuty — Postmortems vs retrospectives](https://www.pagerduty.com/blog/postmortems-vs-retrospectives/).
