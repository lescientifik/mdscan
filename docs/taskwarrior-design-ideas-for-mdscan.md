---
description: Patterns d'architecture et de design de Taskwarrior transposables à mdscan en tant qu'outil de discovery sur corpus markdown — sans changer son rôle, sans ajouter de couche tasks, en gardant le positionnement "madge for markdown".
---

# Idées de design Taskwarrior réutilisables pour mdscan

> **Statut** : recherche de design. Étudie Taskwarrior comme **source d'inspiration architecturale**, pas comme outil à coupler. Le couplage est l'objet de [mdscan-taskwarrior-synergy.md](mdscan-taskwarrior-synergy.md) ; ce document explore un angle orthogonal : quels **patterns** Taskwarrior (urgency, contextes, hooks, reports, DOM, command pattern, ...) sont transposables à un outil de discovery sur corpus markdown.

## TL;DR

- **À adopter sans hésiter** : (1) le pattern **Custom Reports** (vues nommées dans `[tool.mdscan]`, chacune = filter + sort + columns) — c'est exactement ce qu'il manque entre `mdscan --json | jq ...` et un DSL ; (2) le **DOM dotted-path** pour les colonnes et les flags (`--columns path,description,tags.count`) — pas de mini-DSL à designer ; (3) la **séparation `_get` / commandes principales** (helpers en sous-commandes `_xxx` réservées aux scripts).
- **À adopter prudemment** : (1) **Urgency score** transposé en **freshness score** (composable, configurable, jamais stocké, sortie d'une seule commande `mdscan rank`) — utile pour `stale` mais à valider contre over-engineering ; (2) un **équivalent `task info`** dédié au single-file profile (un `mdscan info <file>` qui résout L2 dans le modèle de progressive disclosure) ; (3) un **`mdscan context`** = filter nommé persistant (mais en mode read-only — pas de write commands à scoper).
- **À rejeter** : (1) les **hooks** mdscan-side (`on-read`, `on-touch`) — mdscan n'a pas la sémantique transactionnelle requise et l'invocation est mono-shot, pas long-running ; (2) un **command-line parser unifié à 4 segments** (filter / command / modifications / misc) — argparse + sous-commandes nominales sont suffisants pour un outil read-mostly ; (3) la **conversion vers SQLite** type Taskchampion — mdscan reste stateless (frontmatter dans le `.md`, état op dans `state.json` plat).
- **Idée clé** : Taskwarrior a réussi en **n'inventant pas de DSL** pour l'utilisateur — il a inventé un **vocabulaire dotted-path uniforme** (DOM) et des **reports configurables**. mdscan peut faire pareil sans renier sa promesse "pas de DSL, jq fait le filtre" : un report mdscan, c'est juste un préset `jq | column`, pas un moteur de requête.

---

## 1. Cadre méthodologique

### 1.1 Pourquoi cette comparaison est non-triviale

Taskwarrior est un outil **stateful**, **transactionnel**, **lecture/écriture intensive** sur des objets à cycle de vie court (tâches qui naissent, vivent, finissent). mdscan est un outil **stateless** (le frontmatter est porté par les fichiers eux-mêmes), **mono-shot** (un appel = une question), **lecture-dominant** sur des objets à cycle de vie long (notes qui survivent).

Beaucoup de patterns Taskwarrior sont **dictés par cet état mutable** : recurrence, dependencies, urgency calculée à la volée, hooks transactionnels, `undo`. La transposition à mdscan demande de **distinguer** :

1. **Patterns dépendants de l'état mutable** → souvent intransposables ou à transformer profondément.
2. **Patterns indépendants** (ergonomie CLI, vocabulaire de filtres, architecture du code) → directement transposables.
3. **Patterns intermédiaires** (reports, contexts, DOM) → transposables avec **adaptation au lecteur dominant** : on garde la forme, on supprime les parties write.

Le rapport est structuré selon cette grille, pas par feature Taskwarrior. La section "Idées rejetées" rend explicite ce qui rentre dans la catégorie (1).

### 1.2 La boussole mdscan

Les principes spec v0.4 ([spec-v0.4.md](spec-v0.4.md)) tracent les contraintes :

- **Standalone** (pas de couplage git/Claude/Obsidian).
- **Pas de DSL** (jq fait le filtre, rg fait le search body).
- **Frontmatter minimal** (description, kind, tags, last_updated).
- **JSON canonique** pour piping.
- **Stateless** sauf `state.json` d'opération (last_read, read_count).

Toute idée Taskwarrior doit respecter ces contraintes. Si l'idée nécessite d'ajouter un mini-langage de filtres dans mdscan, elle viole **pas de DSL** → rejetée. Si elle nécessite un démon long-running, elle viole **mono-shot** → rejetée. Si elle nécessite d'auto-écrire dans `state.json` à chaque lecture, on tolère parce que `state.json` est déjà la **soupape d'état op**.

---

## 2. Idée 1 — Custom Reports : vues nommées en config

### Le pattern Taskwarrior

Une commande comme `task next` n'est **pas un cas spécial dans le code** : c'est un **report** défini en config, comme tous les autres. Concrètement (source : [Reports](https://taskwarrior.org/docs/report/), [taskrc.5 man page](https://taskwarrior.org/docs/man/taskrc.5/)) :

```ini
report.next.description=Most urgent tasks
report.next.columns=id,start.age,entry.age,depends,priority,project,tags,recur,scheduled.countdown,due.relative,until.remaining,description,urgency
report.next.labels=ID,Active,Age,Deps,P,Project,Tags,Recur,S,Due,Until,Description,Urg
report.next.sort=urgency-
report.next.filter=status:pending limit:page
```

L'utilisateur peut **créer ses propres reports** :

```ini
report.simple.description=Simple list by project
report.simple.columns=id,project,description.count
report.simple.sort=project+/,entry+
report.simple.filter=status:pending
```

Cinq choses définissent un report : **description, columns, labels, sort, filter**. Le code commun (`CmdCustom.cpp`, 260 lignes) prend une définition de report en config et l'applique sur le set de tâches filtré. **Tous les reports built-in (`list`, `next`, `ready`, `waiting`, `recurring`, `overdue`) sont des instances de ce mécanisme** ([CmdCustom.cpp](https://github.com/GothenburgBitFactory/taskwarrior/blob/develop/src/commands/CmdCustom.cpp)).

**Pourquoi c'est puissant** : (a) zéro code à écrire pour créer une vue ; (b) tous les reports sont des données de config, donc partageables, versionnables, scriptables ; (c) l'utilisateur évolue son setup en raffinant des reports, pas en demandant des features au mainteneur.

### Transposition à mdscan

Aujourd'hui, l'utilisateur qui veut "tous les `decision` taggés `auth`, triés par `last_updated` desc, en TSV path + description" écrit :

```bash
mdscan --json | jq -r '
  .[] | select(.kind=="decision" and (.tags|index("auth")))
  | [.last_updated, .path, .description] | @tsv
' | sort -r
```

C'est correct mais (a) la commande est longue et impossible à mémoriser, (b) chaque utilisateur la réécrit, (c) elle vit dans un alias shell ou un README mais n'est pas **first-class** dans le projet.

Proposition : **`[tool.mdscan.report.<name>]`** dans `pyproject.toml`.

```toml
[tool.mdscan.report.decisions]
description = "All decisions, newest first"
filter = '.kind == "decision"'
sort = "-last_updated"
columns = ["last_updated", "path", "description"]

[tool.mdscan.report.auth-decisions]
description = "Auth decisions, newest first"
filter = '.kind == "decision" and (.tags | index("auth"))'
sort = "-last_updated"
columns = ["path", "description"]

[tool.mdscan.report.orphans]
description = "Files unreachable from entrypoint, no description"
filter = '.unreachable == true and .description == null'
columns = ["path"]
```

Usage :

```bash
mdscan report decisions
mdscan report auth-decisions
mdscan report auth-decisions --json     # bypass column formatting
mdscan reports                          # list defined reports
```

**Implémentation minimale** : `mdscan report <name>` = `mdscan --json | jq "[ .[] | select(<filter>) ] | sort_by(<sort>) | .[] | [<columns>] | @tsv"`. C'est **du jq généré**, pas un moteur de query.

**Une clarification importante** : le champ `filter` reste une **expression jq**, pas un mini-DSL inventé pour mdscan. La promesse "pas de DSL" est respectée — on **présète** un appel jq, on n'**invente** pas un langage. C'est la différence entre faire un `Makefile` et faire un `cmake`.

### Use case concret

Un repo de docs `mdscan/`. Le mainteneur définit dans `pyproject.toml` :

```toml
[tool.mdscan.report.stale-guides]
description = "Guides not updated in 6 months"
filter = '.kind == "guide" and (.last_updated < (now - 86400*180 | strftime("%Y-%m-%d")))'
sort = "last_updated+"
columns = ["last_updated", "path", "description"]
```

Un nouveau contributeur tape :

```bash
$ mdscan reports
decisions       All decisions, newest first
auth-decisions  Auth decisions, newest first
orphans         Files unreachable from entrypoint, no description
stale-guides    Guides not updated in 6 months

$ mdscan report stale-guides
2025-08-12  docs/guides/deployment.md   Step-by-step deploy guide for the staging env.
2025-09-03  docs/guides/local-setup.md  How to set up a local development environment.
```

Bénéfice net : la connaissance "ce repo se relit comme ça" est **encodée dans la config**, pas perdue dans un README ou un alias zsh privé. Une session Claude qui lit le `pyproject.toml` apprend les vues pertinentes en 30 secondes.

### Limites / pourquoi ce serait peut-être une mauvaise idée

- **Risque de glissement vers DSL** : si on accepte le champ `filter`, certains utilisateurs vont vouloir des opérateurs raccourcis (`tags has auth` plutôt que `(.tags | index("auth"))`). Tenir la ligne : c'est du jq brut, point.
- **Couche d'indirection** : `mdscan report X` est moins explicite qu'un alias shell. L'avantage est qu'il **vit avec le projet** (commité), pas dans `~/.zshrc`.
- **Sort syntax** : il faut convenir d'une mini-syntaxe (`-field` pour desc, `field` ou `+field` pour asc). C'est mince mais c'est une feature de plus.
- **Columns dotted-path** : pour `tags.count` ou `links.0.target` il faut un mini-resolver. Avantage : c'est le même que celui qu'on propose en Idée 3 (DOM), donc mutualisable.

Recommandation : **adopter**, en limitant strict `filter = "<expression jq>"` ; pas de champs syntactiques inventés.

---

## 3. Idée 2 — Le DOM dotted-path comme vocabulaire de colonnes

### Le pattern Taskwarrior

Taskwarrior expose **toutes** ses données via un **Domain Object Model** dotted-path uniforme (source : [DOM](https://taskwarrior.org/docs/dom/), [doc/devel/rfcs/dom.md](https://github.com/GothenburgBitFactory/taskwarrior/blob/develop/doc/devel/rfcs/dom.md)) :

```
1.description                    # task 1's description
1.due.year                       # year of task 1's due date
1.annotations.0.description      # first annotation's text
rc.urgency.next.coefficient      # config value
system.version                   # system info
context.width                    # terminal width
```

Le RFC DOM proposé étend cette idée pour qu'**un même path** serve à la fois pour `_get`, les colonnes de reports, et les expressions de filtre :

```
123.due.iso                      # comme valeur dans expression
report.x.columns=uuid.short,description.oneline
```

Le bénéfice : **un seul vocabulaire** à apprendre, qui marche partout — flags de colonnes, scripts `_get`, debugging. C'est la même mécanique que CSS selectors ou XPath dans leurs domaines.

### Transposition à mdscan

mdscan a déjà la matière première : la sortie JSON contient `path`, `description`, `kind`, `tags`, `last_updated`, `links` (array d'objets), `unreachable`, `word_count`, etc. Le problème : **aucun vocabulaire stable** pour ces champs en CLI. Un `--columns path,description` n'existe pas ; on est forcés de pipe vers `jq -r '.[] | [.path, .description] | @tsv'`.

Proposition : un flag `--columns <dot-path[,dot-path...]>` qui accepte les paths JSON standard.

```bash
mdscan --columns path,description                    # equivalent au défaut
mdscan --columns path,kind,tags.count,last_updated   # avec count sur array
mdscan --columns path,links.0.target                 # premier lien sortant
mdscan --columns path,description.words              # nombre de mots de la description (format hint)
```

`<attribute>.<format-hint>` permet une mini-syntaxe pour les transformations courantes :

- `.count` sur array → longueur
- `.0`, `.1`, ... sur array → indexation
- `.relative` sur date → "3 jours"
- `.iso` sur date → format ISO complet
- `.short` sur string → première ligne

**Implémentation** : un resolver `resolve(obj, "tags.count")` qui fait du dotted-access avec un mini-vocabulaire de fins. ~30 lignes Python. Pas de DSL — juste de la navigation d'arbre + 4-5 helpers de format.

Et — point critique — on **réutilise** ce resolver pour le champ `columns` des reports (Idée 1) et potentiellement pour un futur `--sort <dot-path>`. Une mécanique, trois usages.

### Use case concret

Un agent Claude veut une vue "minimaliste mais structurée" pour décider quels docs charger en L4 :

```bash
$ mdscan --columns path,kind,tags.count,last_updated --json
[
  {"path":"docs/spec-v0.4.md","kind":"reference","tags.count":3,"last_updated":"2026-05-14"},
  {"path":"docs/adr/003.md","kind":"decision","tags.count":2,"last_updated":"2026-04-22"},
  ...
]
```

ou en TSV :

```bash
$ mdscan --columns path,kind,tags.count,last_updated --plain
docs/spec-v0.4.md       reference  3   2026-05-14
docs/adr/003.md         decision   2   2026-04-22
```

Moins de friction que `jq '.[] | [.path, .kind, (.tags|length), .last_updated] | @tsv'`. Et **portable** : la même syntaxe marche dans `[tool.mdscan.report.x] columns = [...]`.

### Limites / pourquoi ce serait peut-être une mauvaise idée

- **C'est un mini-DSL déguisé** — précisément ce que la spec dit qu'on ne fait pas. Argument inverse : ce n'est pas un DSL de **query**, c'est un vocabulaire de **projection**. La query reste jq. La frontière est nette : on **sélectionne** des champs ; on ne **filtre** pas avec ce vocabulaire.
- **Le nombre de formats peut exploser** : `.count`, `.0`, `.relative`, `.iso`, `.short`, `.age`, `.julian`... Limiter au strict utile : `.count` sur array, `.N` sur array, `.relative` / `.iso` sur date, `.short` sur string. Cinq formats max.
- **Conflit avec jq** : `tags.count` n'est pas du jq valide (`(.tags | length)` l'est). Pas grave si on documente clairement que mdscan `--columns` parle son propre langage de projection.

Recommandation : **adopter avec un set de formats étroit et stable**.

---

## 4. Idée 3 — `mdscan info <file>` : profile single-doc à la `task info`

### Le pattern Taskwarrior

`task <id> info` produit un dump human-readable d'**une** tâche, avec **tous** ses champs **et l'urgency décomposée** (source : [info command](https://taskwarrior.org/docs/commands/info/)) :

```
ID              42
Description     Implementer mdscan backlinks --json
Status          Pending
Project         mdscan.v0.4.backlinks
Tags            feature next
Entered         2026-04-01 (3w)
Due             2026-05-25 (5d)
Urgency         8.20
    next        +15.00 * 1.0 = 15.00
    due         +12.00 * 0.6 = 7.20
    tag         +1.00 * 2 * 0.8 = 1.60
    ...
UUID            8a3e1c4b-...
```

Distinction critique : `task <id> info` ≠ `task <id> export`. Le premier est **conçu pour les humains** (formatage tabulaire, urgency décomposée, types affichés joliment) ; le second est **conçu pour les machines** (JSON brut, un seul objet sans contexte).

Dans le modèle de progressive disclosure de mdscan (cf. spec v0.4 section "Progressive disclosure layers"), ce serait le **L2 — Profile** : "qu'est-ce que c'est, où ça vit dans le graphe, qu'est-ce qui pointe ici, qu'est-ce que ça pointe."

### Transposition à mdscan

Ouvert dans la spec : "do we need a dedicated `mdscan profile <file>` command, or is `mdscan --json | jq '.[]|select(.path=="X")'` sufficient?". Taskwarrior tranche : **oui, dedicated command**, parce que la valeur ajoutée n'est pas dans les données mais dans la **forme humaine + cross-références calculées**.

Proposition :

```bash
$ mdscan info docs/adr/003-no-query-dsl.md

PATH            docs/adr/003-no-query-dsl.md
DESCRIPTION     Décision — pas de DSL de query dans mdscan ; on s'appuie sur jq pour les filtres.
KIND            decision
TAGS            adr, cli, design
LAST_UPDATED    2026-05-10 (4d ago)
WORD_COUNT      342

LINKS OUT       3
  → docs/spec-v0.4.md                "Spec v0.4 — living specification ..."
  → docs/cli-audit.md                "CLI audit of mdscan vs clig.dev"
  → docs/recipes.md                  (broken — file does not exist)

LINKS IN        2
  ← docs/spec-v0.4.md                line 142
  ← docs/plan-cli-v0.3.md            line 78

REACHABILITY    reachable from CLAUDE.md (depth 2)
```

Plusieurs propriétés intéressantes :

1. **Données enrichies** : `last_updated` annoté avec l'âge relatif (`4d ago`), liens validés (broken / OK), reachability calculée, backlinks listés. C'est la **valeur ajoutée** vs `mdscan --json | jq`.
2. **Composabilité** : `mdscan info --json` reste utile pour les agents qui veulent les données enrichies en JSON (pas pour les humains).
3. **Single-file invocation** : `info <file>` est explicitement à arity 1. Pas de filtre, pas de batch. Si tu veux batch : `xargs mdscan info`.

C'est aussi le **bon endroit** pour exposer L2 dans le modèle de progressive disclosure, sans surcharger le `mdscan --json` global (qui doit rester un export brut peu coûteux).

### Use case concret

Un agent reçoit une consigne "modifie l'ADR-003". Avant de toucher au fichier, il veut savoir : (a) qui pointe vers cet ADR, pour répercuter les changements ; (b) quand il a été mis à jour, pour estimer s'il est à jour ; (c) quels liens il contient, pour ne pas casser le contrat documentaire.

```bash
$ mdscan info docs/adr/003-no-query-dsl.md
[output complet ci-dessus]
```

En une commande, l'agent a le contexte complet. Sans `mdscan info`, il faut **3 commandes** :

```bash
mdscan --json | jq '.[] | select(.path == "docs/adr/003-no-query-dsl.md")'   # données
mdscan backlinks docs/adr/003-no-query-dsl.md                                 # qui pointe
# (et la reachability nécessite un parcours custom)
```

Et la reachability n'est trivialement pas exposée — il faut écrire un script. `mdscan info` rassemble cette logique en un endroit.

### Limites / pourquoi ce serait peut-être une mauvaise idée

- **Surface CLI qui grossit** : 6 sous-commandes (`scan`, `check-links`, `tree`, `coverage`, `set-description`, `info`) au lieu de 5. Cher.
- **Duplication avec `mdscan --json | jq '.[] | select(.path=="X")'`** : tout l'output peut être reconstitué en bash. Argument inverse : la reachability et les backlinks ne se reconstituent pas trivialement ; et la **forme humaine** lue d'un coup d'œil compte pour les humains qui browsent.
- **Risque de feature creep** : "tu pourrais ajouter aussi l'outline ?", "tu pourrais ajouter les commits git récents ?". Délimiter strictement : data du JSON + liens validés + reachability + backlinks. Stop.

Recommandation : **adopter** en Phase 2-3 ; c'est exactement la primitive L2 manquante.

---

## 5. Idée 4 — Helper commands `_xxx` réservées aux scripts

### Le pattern Taskwarrior

Taskwarrior expose une famille de **helper commands** préfixées `_` qui ne s'affichent pas dans le help principal et sont **stables, machine-friendly, mono-ligne** (source : `task --help`, [Commands](https://taskwarrior.org/docs/commands/)) :

```
task _commands    # lists all command names, one per line
task _columns     # list all column names available in reports
task _ids         # list IDs matching filter (machine-readable)
task _uuids       # list UUIDs matching filter
task _tags        # list distinct tags
task _projects    # list distinct projects
task _get 42.due  # get specific value via DOM path
```

Distinction nette : les commandes "publiques" (`list`, `next`, `info`) ont une sortie humaine (colonnes, couleurs, headers) ; les helpers `_xxx` ont une sortie **plate, parsable, scriptable**. Le naming convention `_xxx` signale "ce truc est conçu pour `xargs`, `comm`, `awk`, pas pour la lecture humaine".

Bénéfice : les **tools écosystème** (taskwarrior-tui, vit, taskopen, complétion shell) consomment les helpers sans risque de breaking change cosmétique. Si demain `task list` change ses colonnes par défaut, taskwarrior-tui ne casse pas parce qu'il utilise `task _ids`.

### Transposition à mdscan

mdscan a un seul mode pour ça aujourd'hui : `mdscan --json`. C'est puissant mais **lourd** quand tu veux juste une liste de paths.

Proposition : helpers `_xxx` qui produisent **une ligne par item** (newline-separated, no JSON, no formatting).

```bash
mdscan _files             # all paths matching default scan
mdscan _kinds             # distinct kind values
mdscan _tags              # distinct tags
mdscan _broken-links      # broken target paths
mdscan _orphans           # files unreachable from entrypoint
mdscan _get <file> <dot-path>   # single value, e.g. mdscan _get docs/x.md last_updated
```

Convention :
- **Une ligne par item**, pas de header, pas de couleur.
- **Pas d'effet de bord** (pas de touche `state.json`).
- **Stable** dans le temps — sémantique versionnée.

C'est presque ce que `mdscan --json | jq -r '.[].path'` produit déjà. La différence : **ergonomie** (`mdscan _files` est plus court, mémorable) et **stabilité contractuelle** (les helpers sont l'API pour les scripts, le JSON est l'API pour les pipelines lourds).

### Use case concret

Complétion shell pour `mdscan info <file>` :

```bash
# _mdscan completion zsh
_mdscan_files() {
  compadd -- $(mdscan _files 2>/dev/null)
}
```

Pas besoin de parser JSON. `mdscan _files` est instantané, prédictible, et ne casse jamais.

Autre use case : une intégration éditeur (vim plugin "open doc by description") :

```vim
" :MdScan
function! s:MdScanPick()
  let l:files = systemlist('mdscan _files')
  " ... use fzf or quickfix to pick
endfunction
```

Versus consommer `mdscan --json` : 5x plus court, 0 dépendance JSON.

### Limites / pourquoi ce serait peut-être une mauvaise idée

- **Duplication apparente** : `mdscan _files` ≈ `mdscan --json | jq -r '.[].path'`. Vrai, mais la duplication est **voulue** comme contrat API stable.
- **Naming bikeshed** : `_files` ou `_paths` ? `_tags` ou `_tag-list` ? Suivre Taskwarrior (plural, dash-separated, court). Documenter une fois pour toutes.
- **Risque de prolifération** : tentation d'ajouter `_descriptions`, `_kinds-with-counts`, etc. Limiter au strict utile (5-6 helpers max), guidés par les besoins de tooling externe.

Recommandation : **adopter**, 4-5 helpers max au début. C'est l'API "scripting" qui rend l'outil **outillable**, exactement comme Taskwarrior.

---

## 6. Idée 5 — Contexte (filter nommé persistant), version read-only

### Le pattern Taskwarrior

`task context define <name> <filter>` puis `task context <name>` active un **filtre global** appliqué à toutes les commandes de la session (source : [Contexts](https://taskwarrior.org/docs/context/)) :

```bash
task context define work "+work or +urgent"
task context work
task next          # implicitly filtered by +work or +urgent
task list          # same
task done 42       # ⚠️ writes ALSO affected by context — surprising in some cases
task context none  # back to all tasks
```

Le contexte vit dans `.taskrc`, est **persistant entre invocations**, et est partagé entre tous les reports. C'est un **state d'environnement** côté Taskwarrior.

### Transposition à mdscan

Possible mais avec adaptation forte. mdscan est mono-shot, donc "persistant entre invocations" demande un fichier d'état. Et mdscan a très peu de "write commands" affectables (seulement `set-description` et futurs `set-kind`, `set-tags`, `touch`).

Deux variantes :

#### Variante A — Contexte session via env var

```bash
export MDSCAN_FILTER='.kind == "decision"'
mdscan              # scope to decisions
mdscan info docs/x.md  # info still works (single file targeted)
```

Avantage : zéro fichier d'état. La "session" = le shell. Inspiré du `KUBECONFIG` / `kubectl config use-context` mais en plus léger.

#### Variante B — Contexte nommé dans `state.json`

```bash
mdscan context define decisions '.kind == "decision"'
mdscan context use decisions
mdscan               # filtered
mdscan context none  # clear
```

État écrit dans `.mdscan/state.json` à la clé `active_context`. Persiste entre invocations.

#### Recommandation

Si on adopte les **Reports** (Idée 1), le besoin de "contexte" diminue : `mdscan report decisions` couvre le 80%. Le contexte ajoute du sucre quand on veut **appliquer le filter sur plusieurs commandes** (`mdscan tags` filtré aux décisions ? `mdscan stale` filtré aux guides ?).

**Variante A (env var) gagne** parce que :
- Pas de fichier d'état nouveau à gérer.
- Pas de surprise read/write (mdscan n'a pratiquement pas de write commands de masse).
- Composable avec `direnv`, scripts shell, etc.

Restriction explicite : `MDSCAN_FILTER` **ne s'applique qu'aux commandes de listing** (`mdscan`, `mdscan tags`, `mdscan stale`, `mdscan coverage`). Pas à `mdscan info <file>` (cible explicite), pas à `mdscan set-description` (cible explicite). C'est la **leçon apprise** de Taskwarrior : un contexte global qui s'applique aux writes crée des surprises ("j'ai fait `task done 42` mais le contexte a transformé le filter et `42` ne s'est pas résolu").

### Use case concret

Onboarding d'un nouveau dev sur un repo dense. La doc indique :

```bash
# Focus on decisions only
export MDSCAN_FILTER='.kind == "decision"'

mdscan                          # only see decisions
mdscan tags                     # tags used in decisions
mdscan stale                    # decisions overdue for review
```

Pour revenir à la vue complète : `unset MDSCAN_FILTER`. Pour scoper un seul appel : `MDSCAN_FILTER='.kind=="guide"' mdscan`.

### Limites / pourquoi ce serait peut-être une mauvaise idée

- **Surface conceptuelle ajoutée** pour gain marginal si on a déjà Reports + jq. Vrai. Argument : c'est **une variable d'env**, pas du code mdscan ; coût de maintenance ≈ 5 lignes.
- **Risque de confusion utilisateur** : "pourquoi je vois pas le fichier X ? — ah, t'as MDSCAN_FILTER actif". Mitigation : `--verbose` affiche le filtre actif en stderr.
- **Doublon avec Reports** : presque. Le report est nommé et a des columns ; le contexte est juste un filter. Les deux coexistent dans Taskwarrior parce qu'ils servent des moments différents (un report = une réponse ponctuelle ; un contexte = un mode persistant).

Recommandation : **différer**. À ajouter si les Reports tout seuls s'avèrent insuffisants en usage réel.

---

## 7. Idée 6 — Urgency-like scoring : "freshness" / "centrality"

### Le pattern Taskwarrior

L'urgency est un **polynôme à coefficients configurables** ([Urgency doc](https://taskwarrior.org/docs/urgency/)) :

```
urgency =   15.0 * next
          + 12.0 * due_factor(due)
          +  8.0 * blocking_factor
          +  6.0 * (priority == "H")
          +  5.0 * scheduled_factor
          +  4.0 * active
          +  3.9 * (priority == "M")
          +  2.0 * age
          +  1.8 * (priority == "L")
          +  1.0 * has_annotations
          +  1.0 * tag_count_factor
          +  1.0 * has_project
          -  3.0 * waiting
          -  5.0 * blocked
```

Chaque coefficient est `urgency.xxx.coefficient` dans `.taskrc`. L'utilisateur peut **tuner** ("je veux moins d'importance à `next`, plus à `due`") sans changer le code. Et — détail critique — **l'urgency n'est jamais stockée** : elle est recalculée à chaque invocation. C'est une fonction pure des attributs et de la config.

`task next` trie par urgency décroissante, et c'est le rapport de référence : "qu'est-ce que je devrais bosser maintenant".

### Transposition à mdscan : freshness score

Une notion analogue pour mdscan : **freshness score** ou **decay score** — "quel est le degré d'attention que ce doc mérite ?". Composé de facteurs :

| Facteur | Coeff par défaut | Sémantique |
|---|---|---|
| Récemment lu (`last_read` < 7d) | +5.0 | actuellement chaud |
| Récemment mis à jour (`last_updated` < 7d) | +3.0 | content récent |
| Centralité (nb backlinks) | +0.5 par backlink, max +5 | "important" dans le graphe |
| Liens cassés | +2.0 | demande maintenance |
| Pas de description | +3.0 | doc incomplet |
| Tag `deprecated` | -10.0 | hors scope |
| Non reachable depuis entrypoint | +1.0 | orphelin candidat à supprimer/lier |
| Très ancien (`last_updated` > 6mo) ET pas lu (`last_read` > 3mo) | -2.0 | candidat staleness |

```bash
mdscan rank                              # all files, sorted by freshness desc
mdscan rank --limit 10                   # top 10
mdscan rank --explain docs/auth.md       # decomposition like `task info` urgency
```

Sortie de `--explain` :

```
docs/auth.md       freshness: 7.5
  last_updated (3d)       +3.00 * 1.0 = 3.00
  backlinks (8)           +0.50 * 8 * cap(5) = 4.00
  description present     0.00
  reachable               0.00
  -- no deprecated tag --
  TOTAL                                       7.00
```

Le but **n'est pas** de produire une killer feature comme Taskwarrior `task next`. C'est de **fournir un signal composite** que l'utilisateur peut tuner via `pyproject.toml` :

```toml
[tool.mdscan.freshness]
last_read_recent = 5.0
last_updated_recent = 3.0
backlink_per = 0.5
backlink_cap = 5.0
broken_links = 2.0
missing_description = 3.0
deprecated_penalty = -10.0
stale = -2.0
```

### Use case concret

L'agent Claude reçoit "trie-moi les docs par pertinence pour cette session". Plutôt qu'aller fouiller les `tags`, `last_updated`, `last_read` un par un :

```bash
$ mdscan rank --limit 20 --json
[
  {"path": "docs/spec-v0.4.md", "freshness": 8.5, ...},
  {"path": "docs/adr/003.md", "freshness": 6.2, ...},
  ...
]
```

L'agent charge les top-N en L4. Le score n'est pas magique — il est **composite et configurable** — mais il **trie le bruit** sans demander à l'agent de coder le tri à chaque session.

Use case alternatif : un humain qui revient sur un repo après 6 mois. `mdscan rank` lui donne en une commande les docs qui méritent une relecture (last_updated récent + backlinks nombreux) et ceux qui méritent un nettoyage (deprecated, orphelin, vieux et pas lu).

### Limites / pourquoi ce serait peut-être une mauvaise idée

- **Risque d'over-engineering caractéristique**. Taskwarrior justifie l'urgency par "je dois trier 200 tâches **chaque jour**". mdscan trie typiquement 30-100 docs **occasionnellement**. La marge de valeur est plus mince.
- **Tunabilité = invitation à fiddler**. Cf. workflow Cojean : "Paul: I found that I spent too much time fiddling with the values" sur Taskwarrior priorities. Idem ici : si l'utilisateur passe 20 minutes à tuner ses coefficients, on a perdu.
- **Une seule commande de plus, mais beaucoup de surface conceptuelle**. Un freshness score introduit la notion de "score" dans mdscan qui n'existait pas. Toute la doc, tous les exemples, tous les tests, doivent expliquer / couvrir / valider ça.
- **Couplage subtil au `state.json`** : `last_read_recent` lit `state.json`. Si le repo est nouvellement cloné sans `state.json`, tous les `last_read` sont à 0 et le score s'effondre. Comportement à documenter.

Recommandation : **prudent — phase 5 ou plus tard**. Adopter **uniquement** si l'usage prouve que `mdscan stale` (vue plus simple) ne suffit pas. Et **si on l'adopte**, garder les coefficients par défaut **conservateurs** (ne pas mettre 15.0 sur quoi que ce soit, pour éviter l'écrasement par un seul facteur — c'est le conseil "best practices" de Taskwarrior lui-même).

---

## 8. Idée 7 — Command pattern + un fichier par commande

### Le pattern Taskwarrior

Le code Taskwarrior organise chaque commande dans **deux fichiers** : `CmdXxx.h` (interface, ~40 lignes) et `CmdXxx.cpp` (implémentation, 50-500 lignes). Toutes héritent de `class Command` avec une méthode `execute(std::string&)`. Le dispatch dans `main` est trivial : trouver la `Cmd*` correspondante au mot-clé et appeler `execute`.

C'est le classique **Command Pattern** ([Wikipedia](https://en.wikipedia.org/wiki/Command_pattern)). 60+ commandes, chacune isolée. La complexité ne s'accumule pas en un God Object — elle reste **locale** à chaque commande. Exemple : `CmdAdd.cpp` (95 lignes), `CmdCustom.cpp` (260 lignes), `CmdContext.cpp` (433 lignes).

### Transposition à mdscan

mdscan a actuellement **tout dans `cli.py`** (712 lignes au moment d'écrire). C'est gérable mais commence à être dense — quand on ajoutera `info`, `report`, `tags`, `stale`, `audit`, `touch`, etc., le fichier va doubler.

Proposition : `src/mdscan/commands/cmd_<name>.py`, un par commande, exposant une fonction `run(args, config) -> int` (exit code). Le `cli.py` se réduit à du dispatch :

```python
# src/mdscan/cli.py
from mdscan.commands import (
    cmd_scan, cmd_check_links, cmd_tree, cmd_coverage,
    cmd_set_description, cmd_info, cmd_report, ...
)

COMMANDS = {
    "scan": cmd_scan,
    "check-links": cmd_check_links,
    "tree": cmd_tree,
    "info": cmd_info,
    "report": cmd_report,
    ...
}

def main(argv):
    args = parser.parse_args(argv)
    cmd = COMMANDS.get(args.command, cmd_scan)
    return cmd.run(args, config)
```

Chaque `cmd_xxx.py` :
- Contient sa fonction `register_parser(subparsers)` pour ses propres args.
- Contient sa fonction `run(args, config) -> int`.
- Importe seulement ce dont il a besoin.

**Bénéfice** : couplage faible, testabilité par commande, ajout d'une commande = un fichier nouveau + une entrée dans le dict. C'est l'organisation qu'utilisent click, typer, cleo dans l'écosystème Python, et c'est éprouvé.

### Use case concret

Aujourd'hui ajouter `mdscan info` demande de modifier `cli.py` à 3 endroits : (1) ajouter le subparser, (2) ajouter le dispatch, (3) ajouter la logique. Demain, ajouter `mdscan info` = créer `commands/cmd_info.py` + ajouter une ligne au dict `COMMANDS`. Le diff est plus propre, les tests sont plus localisés (`tests/commands/test_cmd_info.py`).

Quand un agent Claude code une nouvelle commande, sa boucle de feedback est : éditer **un seul nouveau fichier**, pas chirurgier dans un cli.py monolithique.

### Limites / pourquoi ce serait peut-être une mauvaise idée

- **Refactoring upfront** : 712 lignes à éclater. ~1 journée de travail.
- **Doublon avec frameworks existants** (click, typer) : si on adopte un framework, on a déjà cette organisation. Argument : mdscan a fait le choix `argparse` (stdlib), et c'est sain. Pas la peine d'ajouter une dépendance pour ça.
- **Sur-engineering pour 5 commandes** : oui. Mais on va en avoir 10-15 en v0.4 final (info, report, tags, stale, audit, touch, set-kind, set-tags, validate, edit, show, new, ...). À ce volume, le monolithe devient inconfortable.

Recommandation : **adopter quand le nombre de commandes dépasse ~8**. C'est-à-dire **bientôt**, vu la roadmap v0.4. Pas urgent, mais à anticiper avant la Phase 2-3 d'implémentation.

---

## 9. Idée 8 — Pseudo-attributs dérivés ("virtual tags")

### Le pattern Taskwarrior

Taskwarrior expose des **pseudo-attributs** calculés à la volée, utilisables dans les filtres comme des attributs réels (source : doc info command — virtual tags) :

```bash
task +OVERDUE                # tasks past their due date
task +READY                  # not blocked, not scheduled in future, not waiting
task +UDA                    # tasks with at least one UDA set
task +ORPHAN                 # tasks with an unknown UDA
task +ACTIVE                 # currently being tracked (start set)
task +CHILD                  # recurring task instance
task +PARENT                 # recurring task template
```

Ces "virtual tags" sont **calculés** depuis l'état brut. Bénéfice : l'utilisateur écrit `task +OVERDUE` sans avoir à exprimer `due.before:now` (qui marche aussi). Le pseudo-attribut **encapsule** une logique métier non-triviale.

### Transposition à mdscan

mdscan a déjà la mécanique latente — `unreachable` est exposé dans la sortie JSON. On peut généraliser : des **champs calculés** stables, présents dans la sortie JSON, utilisables comme filtre jq classique :

| Pseudo-attribut | Sémantique |
|---|---|
| `.unreachable` | Pas atteignable depuis entrypoint |
| `.orphan` | Aucun backlink |
| `.has_broken_links` | Au moins un lien sortant pointe vers fichier inexistant |
| `.has_description` | Frontmatter contient `description` non-vide |
| `.has_kind` | Frontmatter contient `kind` valide |
| `.is_stale` | `last_updated > 180d` AND `last_read > 90d` |
| `.is_leaf` | Aucun lien sortant vers `.md` interne |
| `.is_hub` | `backlink_count >= 5` (centralité élevée) |

Tous calculés à l'export. Coût : un passage supplémentaire après scan (build de l'index backlinks + index reachable), une vingtaine de lignes. **Pas de nouvelle commande à exposer** — c'est juste l'enrichissement de l'output JSON. La sélection se fait en jq :

```bash
mdscan --json | jq '.[] | select(.orphan)'
mdscan --json | jq '.[] | select(.is_hub and .has_description)'
```

Et avec les Reports (Idée 1), on a directement :

```toml
[tool.mdscan.report.orphans]
filter = '.orphan and (.has_description | not)'
columns = ["path"]
```

### Use case concret

Aujourd'hui, "donne-moi les fichiers à supprimer" demande un script :

```bash
mdscan --json > /tmp/all.json
# fichiers orphelins
mdscan check-links --json | jq -r '.unreachable[]' > /tmp/orphans.txt
# fichiers sans description
mdscan --json | jq -r '.[] | select(.description == null) | .path' > /tmp/no_desc.txt
# intersection
comm -12 <(sort /tmp/orphans.txt) <(sort /tmp/no_desc.txt)
```

Avec les pseudo-attrs, c'est :

```bash
mdscan --json | jq -r '.[] | select(.orphan and (.has_description | not)) | .path'
```

Lisible, atomique, pas de fichiers temporaires.

### Limites / pourquoi ce serait peut-être une mauvaise idée

- **Coût de calcul** : `backlink_count`, `is_hub`, `unreachable` requièrent de construire des index. Pour 1000 fichiers, c'est gratuit ; pour 100k, ça commence à coûter. Mais qui a 100k fichiers `.md` dans un repo ? mdscan vise les corpus moyens — 50-500 fichiers.
- **Risque de leaky abstraction** : `is_stale` encode une politique (180j / 90j). Soit on rend ça configurable (cf. Idée 6 — Freshness), soit on accepte que c'est un défaut éditorial. La règle Taskwarrior : virtual tags doivent être **non-controversés** (un OVERDUE est sans ambiguïté). `is_stale` est limite ; `is_hub` aussi (seuil 5 ?). À doser.
- **Pollue le JSON** : 8 pseudo-attrs en plus dans chaque entrée. ~10% de bytes. Mitigable par flag `--no-virtual` ou en n'incluant que les non-trivialement-dérivables (orphan, unreachable, has_broken_links → oui ; has_description, is_leaf → débat).

Recommandation : **adopter les non-controversés** (`orphan`, `unreachable`, `has_broken_links`, `has_description`, `has_kind`, `is_leaf`). **Différer** les controversés (`is_stale`, `is_hub`) jusqu'à ce que l'expérience justifie un seuil par défaut.

---

## 10. Idée 9 — Verbosity à grains fins

### Le pattern Taskwarrior

Le `.taskrc` a un setting `verbose` qui ne marche **pas** comme un booléen. C'est une liste de **catégories d'output** (source : [taskrc.5](https://taskwarrior.org/docs/man/taskrc.5/)) :

```ini
verbose=affected,blank,context,default,edit,footnote,header,label,new-id,override,project,recur,special,sync
```

Chaque catégorie contrôle un type de message. `verbose=` (vide) supprime tout ; `verbose=nothing` idem ; `verbose=affected,header` ne montre que ces deux types.

Bénéfice : **précision chirurgicale** pour les contextes de scripting. Tu peux scripter Taskwarrior sans suppression brutale (`--quiet`) ni flood (`--verbose`).

### Transposition à mdscan

mdscan a aujourd'hui `-q/--quiet` et `-v/--verbose` binaires. C'est correct mais pauvre. Quand un agent veut juste les paths sans le hint "run 'mdscan check-links' to verify link reachability", il doit (a) parser stderr séparément, (b) supprimer tout avec `2>/dev/null` au risque de masquer une vraie erreur.

Proposition (option modeste) : un setting `verbose` granulaire en config + override CLI.

```toml
[tool.mdscan]
verbose = ["hints", "header", "warnings"]   # default
```

```bash
mdscan --verbose=warnings              # only warnings
mdscan --verbose=                      # absolutely nothing extra
mdscan --no-hints                      # shortcut for removing the 'run mdscan check-links' hint
```

Catégories possibles :
- `hints` — suggestions de prochaine commande
- `header` — bannière d'en-tête (path scanné, count)
- `warnings` — fichiers sans description, sans kind, etc.
- `footnote` — résumé de fin
- `progress` — pour les longs scans (rare)

### Use case concret

Un script CI qui veut "mdscan en mode silencieux mais avec les warnings (manque de description)" :

```bash
mdscan --verbose=warnings --json | jq -r '.[].path' | wc -l
```

Aujourd'hui : `mdscan --json | ...` mais on perd les warnings et on doit re-implémenter la détection. Avec l'idée : on les a en stderr, en JSON pipable en stdout, en une commande.

### Limites / pourquoi ce serait peut-être une mauvaise idée

- **Surface CLI** : un flag `--verbose=cat1,cat2` n'est pas standard argparse. Demande un parser custom (5 lignes).
- **Gain marginal** : `-q` et `-v` couvrent 95% des cas. La granularité résoudra peut-être 5% d'usages.
- **Risque de over-config** : si on doit définir 12 catégories, plus personne ne s'y retrouve.

Recommandation : **différer**. À considérer si l'usage CI/scripting montre un besoin réel. Plus prioritaire : que `-q` et `-v` soient bien définis (qu'est-ce qui passe en stderr vs stdout, exactement).

---

## 11. Idée 10 — JSON-line export (vs JSON array)

### Le pattern Taskwarrior

`task export` produit un **JSON array** par défaut mais peut être configuré en mode **JSON Lines** (une ligne = un task) via `rc.json.array=off` ou simplement `task <filter> export rc.json.array=no`. Format pratique pour pipe vers `jq` line-by-line, `head`, `tail`, `awk`, sans charger en mémoire l'array entier.

Le format JSON Lines (NDJSON) est le **format d'échange standard** pour les pipelines de données streamés (logs, observability, ML training data, Airbyte/Singer).

### Transposition à mdscan

mdscan émet aujourd'hui un JSON array `[...]`. Pour des corpus de 100-500 fichiers c'est bon. Pour le futur — ou pour des recipes qui parsent ligne par ligne — JSON Lines est plus naturel :

```bash
mdscan --jsonl
{"path":"docs/spec-v0.4.md","description":"...","kind":"reference",...}
{"path":"docs/adr/001.md","description":"...","kind":"decision",...}
...
```

Bénéfices :
- `mdscan --jsonl | head -3` donne les 3 premiers fichiers, **immédiatement** (le array forçait à parser tout).
- `mdscan --jsonl | grep '"kind":"decision"'` est un filtre grossier mais ultra-rapide pour piloter `xargs`.
- Streaming-friendly : si demain mdscan scanne un repo géant, on peut émettre au fur et à mesure du parcours, pas en bloc.
- Plus simple à parser pour les agents en lecture séquentielle (Claude peut s'arrêter au N-ème ligne).

`gron` (mentionné en spec) ressemble à JSON Lines mais avec une projection key-by-key. NDJSON est plus brut et plus utile pour cet usage.

### Use case concret

```bash
# Top 10 fichiers les plus longs sans charger le reste en mémoire
mdscan --jsonl | jq -c 'select(.word_count > 1000)' | head -10

# Stream filter — détection précoce d'un fichier broken
mdscan --jsonl | jq -c 'select(.broken_links | length > 0)' | head -1
```

Versus l'équivalent array — où jq attend l'array complet avant de pouvoir émettre quoi que ce soit.

### Limites / pourquoi ce serait peut-être une mauvaise idée

- **Une option de plus** : `--json` vs `--jsonl`. Léger.
- **Compatibilité** : les scripts existants qui font `mdscan --json | jq '.[]'` ne sont pas cassés. Bien.
- **Sémantique de l'aggrégat** : `coverage` retourne **un seul objet** (stats globales). `--jsonl` n'a pas de sens là. Cas par cas selon les commandes.

Recommandation : **adopter**, comme flag complémentaire à `--json`. C'est presque gratuit en implémentation, hautement aligné avec la philosophie "JSON pour piping".

---

## 12. Idées rejetées

### 12.1 Hooks (`on-read`, `on-touch`, `on-exit`)

**Pourquoi rejeter** : Taskwarrior a des hooks parce qu'il a une **boucle transactionnelle** — chaque `task modify` est une transaction sur un store stateful, avec un avant/après. mdscan est **mono-shot read-mostly stateless**. Les seuls moments où un hook aurait du sens sont `set-description` et `touch`, qui sont déjà des appels CLI explicites — le user peut chaîner `mdscan set-description ... && do_other_thing`.

Plus profondément : la valeur des hooks Taskwarrior vient du fait que **toutes les opérations passent par `task`** ; aucune opération `Markdown.edit()` n'existe en dehors. Pour mdscan, **n'importe qui peut éditer un `.md`** via `vim`, `Edit`, `sed`, sans passer par mdscan. Un hook `on-edit` ne peut pas attraper ces écritures — c'est ce que `mdscan audit` (hash check) résout, pas un hook.

Si demain on construit un démon `mdscan serve` qui watch un dossier, il pourrait avoir des hooks. Mais c'est explicitement repoussé hors v0.4.

### 12.2 SQLite / Taskchampion store

**Pourquoi rejeter** : Taskwarrior 3 a migré vers SQLite parce qu'il avait des problèmes de concurrence, de sync, et d'intégrité sur ses fichiers `.data`. mdscan **n'a pas ces problèmes** :
- Le frontmatter est **dans le fichier `.md`** ; il est édité avec le fichier, versionné avec git. Pas de store séparé à corrompre.
- `state.json` est tout-petit (~quelques k pour 100 docs), monoticement écrit par mdscan, pas critique (`gitignore`'d).
- Pas de sync à gérer — git fait le sync.

Adopter SQLite pour mdscan **inverserait** une de ses valeurs centrales : plain-text-everything. C'est l'anti-pattern.

### 12.3 Parser CLI à 4 segments (filter / command / modifications / misc)

**Pourquoi rejeter** : Taskwarrior a un parser custom complexe ([CLI RFC](https://github.com/GothenburgBitFactory/taskwarrior/blob/develop/doc/devel/rfcs/cli.md)) parce qu'il accepte des filtres en préfixe **avant** la commande (`task +reading list`), des modifications en suffixe (`task 42 modify due:tomorrow`), des overrides config (`rc.xxx=yyy`) n'importe où, et des séparateurs `--`. La grammaire est non-trivial.

C'est **inutile** pour mdscan, qui (a) a des commandes nominales claires, (b) ne fait pas de write à filtres multiples ("done all tasks matching..."), (c) délègue les filtres à jq de toute façon. `argparse` + sous-commandes couvre 100% du besoin.

Adopter un parser custom = code à maintenir, surprise pour l'utilisateur (ce n'est pas le pattern unix standard), et **zéro gain** vu le périmètre.

### 12.4 Récurrence (`recur:monthly`)

**Pourquoi rejeter** : la récurrence Taskwarrior fait sens parce qu'une **tâche a un cycle de vie** (naît, est faite, est ré-instanciée). Un document `.md` **n'a pas de cycle** : il vit, il est mis à jour ou il est supprimé. Pas de "ré-instancier `docs/auth.md` chaque lundi".

Le besoin couvert par la recurrence ("relire ce doc chaque trimestre", "auditer cette section chaque mois") relève soit (a) de Taskwarrior (cf. doc synergy), (b) d'un externe (cal, cron). mdscan a au mieux un `mdscan stale` qui surface les docs à revisiter.

### 12.5 Annotations (timestamp + texte attaché)

**Pourquoi rejeter (mais y réfléchir)** : Taskwarrior `task 42 annotate "Voir Ulaner 2023"` ajoute un objet `{entry: timestamp, description: text}` à la liste `annotations[]`. C'est intéressant pour Taskwarrior parce qu'une tâche n'a pas de corps — l'annotation est **le seul moyen** d'attacher du texte additionnel.

Un `.md` a **un corps**. Les annotations Taskwarrior ≈ les **paragraphes du body**. Si tu veux annoter un doc, tu édites le doc.

**Cas limite** : un agent qui veut laisser un commentaire **machine-only** sur un doc sans toucher au body (par exemple "Claude a parcouru ce doc le 2026-05-14 et l'a jugé pertinent pour la tâche X"). C'est exactement `state.json` (last_read, read_count). Si on voulait aller plus loin (commentaires libres avec timestamp), on étendrait `state.json` :

```json
{
  "files": {
    "docs/auth.md": {
      "last_read": "...",
      "annotations": [
        {"entry": "2026-05-14T10:00", "text": "agent X a noté: pertinent pour OAuth", "agent": "claude-opus-4-7"}
      ]
    }
  }
}
```

Mais — convention forte mdscan v0.4 : **`state.json` est machine-only, jamais affiché à l'utilisateur**. Y mettre des annotations textuelles libres viole cette frontière. Donc rejeté pour l'instant.

### 12.6 Undo

**Pourquoi rejeter** : Taskwarrior a `task undo` qui rollback la dernière transaction. mdscan **n'a pas de transactions** — il a `set-description` qui édite un fichier `.md`, et git fait l'undo (`git checkout -- file.md`). Pas besoin d'inventer un undo custom.

### 12.7 Theme system (couleurs configurables)

**Pourquoi différer** : Taskwarrior a un système de thèmes (`include ~/themes/solarized-dark-256.theme`) parce que la commande `task list` produit énormément de tableaux colorés à lire. mdscan a aujourd'hui ~3 couleurs (path en cyan, description grise, warnings rouges). C'est suffisant. Si à terme on a 10+ colonnes colorisables, on reconsidérera.

---

## 13. Conclusion — la matrice de décision

| Idée | Coût impl | Valeur | Verdict |
|---|---|---|---|
| Reports nommés (`[tool.mdscan.report.X]`) | Moyen (~150 LoC) | **Très haute** | **Adopter** Phase 2 |
| Dotted-path columns (`--columns path,tags.count`) | Faible (~50 LoC) | Haute | **Adopter** Phase 2 |
| `mdscan info <file>` (L2 profile) | Moyen (~100 LoC) | Haute | **Adopter** Phase 2-3 |
| Helpers `_xxx` | Faible (~30 LoC) | Moyenne | **Adopter** Phase 2 |
| Pseudo-attributs (`orphan`, `unreachable`, etc.) | Faible (~80 LoC) | Haute | **Adopter** Phase 2 |
| JSON Lines (`--jsonl`) | Très faible (~10 LoC) | Moyenne | **Adopter** Phase 2 |
| Command pattern (1 fichier par cmd) | Refacto ~1j | Moyenne (qualité code) | **Adopter** avant Phase 2 |
| Context (env var `MDSCAN_FILTER`) | Faible | Faible (recouvert par Reports) | **Différer** |
| Verbosity granulaire | Faible | Faible | **Différer** |
| Freshness score (`mdscan rank`) | Moyen | Moyenne, **risquée** | **Phase 5+** si demande |
| Hooks (`on-*`) | Élevé | Faible | **Rejeter** |
| SQLite store | Très élevé | Négative | **Rejeter** |
| Parser CLI 4-segments | Élevé | Nulle | **Rejeter** |
| Récurrence | Hors scope | Nulle | **Rejeter** |
| Annotations machine-only | Faible | Faible | **Rejeter** |
| Undo custom | Moyen | Nulle (git fait l'undo) | **Rejeter** |

### Hiérarchie d'adoption

**Tier 1 — à inclure dans la spec v0.4 dès maintenant** :
- Pseudo-attributs (`orphan`, `unreachable`, `has_broken_links`) dans l'output JSON
- Helpers `_xxx` (`_files`, `_tags`, `_kinds`, `_get`)
- `--jsonl` en plus de `--json`
- Refacto vers `commands/cmd_*.py` (préalable, pas une feature visible)

**Tier 2 — à inclure en Phase 2-3 (CLI v0.5 ?)** :
- Reports nommés (`[tool.mdscan.report.X]`)
- `--columns dot.path,...` (avec resolver partagé)
- `mdscan info <file>` (L2 profile)

**Tier 3 — à reconsidérer après usage réel** :
- `MDSCAN_FILTER` env var (si Reports insuffisants)
- Freshness score (`mdscan rank`) (si `stale` insuffisant)
- Verbosity granulaire (si CI/scripting le demande)

### La grande leçon de fond

Taskwarrior a évité le piège du DSL **non pas en interdisant le filtrage avancé**, mais en concevant **un vocabulaire dotted-path uniforme** et **un mécanisme de reports configurables**. L'utilisateur a tout le pouvoir d'un DSL **sans en apprendre un**.

mdscan a déjà 80% de cette philosophie via "JSON + jq + rg". Les Reports + DOM colonnes + helpers `_xxx` complètent les 20% : ils donnent à l'utilisateur **des points d'attache nommés**, **versionnés dans le projet**, **stables dans le temps**, sans inventer de langage.

C'est la transposition la plus fidèle de l'esprit Taskwarrior dans un outil read-only sur corpus markdown.

---

## 14. Bibliographie

### Documentation officielle Taskwarrior

- [Taskwarrior — Reports](https://taskwarrior.org/docs/report/) — définition de reports en config, columns/labels/sort/filter
- [Taskwarrior — Urgency](https://taskwarrior.org/docs/urgency/) — polynôme, coefficients par défaut, configurabilité
- [Taskwarrior — Filter](https://taskwarrior.org/docs/filter/) — syntaxe `name:value`, `+tag`, opérateurs logiques, `/pattern/`
- [Taskwarrior — Context](https://taskwarrior.org/docs/context/) — filtre nommé persistant, activation/désactivation
- [Taskwarrior — Hooks](https://taskwarrior.org/docs/hooks/) — `on-launch`, `on-add`, `on-modify`, `on-exit`, JSON stdin/stdout
- [Taskwarrior — UDAs](https://taskwarrior.org/docs/udas/) — User Defined Attributes, types, déclaration
- [Taskwarrior — DOM](https://taskwarrior.org/docs/dom/) — dotted-path access (`1.due.year`, `rc.xxx`, `system.xxx`)
- [Taskwarrior — Commands](https://taskwarrior.org/docs/commands/) — liste exhaustive, catégories read/write/helpers
- [Taskwarrior — Syntax](https://taskwarrior.org/docs/syntax/) — structure command line à 4 parties
- [Taskwarrior — Recurrence](https://taskwarrior.org/docs/recurrence/) — template + mask, instances spawned
- [Taskwarrior — Configuration](https://taskwarrior.org/docs/configuration/) — `.taskrc`, hiérarchie, overrides, includes
- [Taskwarrior — taskrc.5 man page](https://taskwarrior.org/docs/man/taskrc.5/) — référence exhaustive des settings
- [Taskwarrior — Dates](https://taskwarrior.org/docs/dates/) — `eom`, `sow`, ISO, durations
- [Taskwarrior — Best Practices](https://taskwarrior.org/docs/best-practices/) — philosophie métadonnées, tuning urgency
- [Taskwarrior — 30-Second Tutorial](https://taskwarrior.org/docs/30second/) — onboarding minimaliste
- [Taskwarrior — info command](https://taskwarrior.org/docs/commands/info/) — profile single-task lisible humain
- [Taskwarrior — Workflow Examples](https://taskwarrior.org/docs/workflow/) — usages utilisateurs réels
- [Taskwarrior — 3rd-Party Application Guidelines](https://taskwarrior.org/docs/3rd-party/) — JSON export comme API stable
- [Taskwarrior — Upgrading to v3](https://taskwarrior.org/docs/upgrade-3/) — migration SQLite/Taskchampion

### RFCs et docs développeur Taskwarrior

- [Taskwarrior RFC — CLI Syntax Update](https://github.com/GothenburgBitFactory/taskwarrior/blob/develop/doc/devel/rfcs/cli.md) — règles parser nouveau modèle
- [Taskwarrior RFC — Full DOM Support](https://github.com/GothenburgBitFactory/taskwarrior/blob/develop/doc/devel/rfcs/dom.md) — extension DOM aux columns et filtres
- [Taskwarrior RFC — JSON Format](https://github.com/GothenburgBitFactory/taskwarrior/blob/develop/doc/devel/rfcs/task.md) — spec du format d'échange
- [Taskwarrior — Codebase 101: CLI Parsing](https://taskwarrior.wordpress.com/2013/08/18/codebase-101-command-line-parsing-part-1/) — architecture du parser (blog officiel)

### Articles et workflows utilisateurs

- [Dave Yarwood — Taskwarrior, where have you been all my life?](https://blog.djy.io/taskwarrior-where-have-you-been-all-my-life/) — urgency, scheduling, blocking dependencies vu par utilisateur
- [Kevin Cojean — My Taskwarrior Workflow](https://kevincojean.com/article/my-taskwarrior-workflow) — minimalisme tags/projects/contexts, anti-patterns
- [Brokenpip3 — Taskwarrior practical guide 2025](https://www.brokenpip3.com/posts/2025-02-09-taskwarrior-practical-guide-1/) — guide pratique récent
- [Random Geekery — Custom Reports](https://randomgeekery.org/post/2020/04/taskwarrior-custom-reports/) — création de reports personnalisés

### Code source Taskwarrior (consulté localement via sparse clone)

- `src/commands/CmdAdd.{h,cpp}` — pattern Command minimal (~95 LoC)
- `src/commands/CmdCustom.{h,cpp}` — moteur de reports (~260 LoC)
- `src/commands/CmdContext.{h,cpp}` — gestion contextes (~433 LoC)
- `src/commands/Cmd*.{h,cpp}` — 60+ commandes isolées, pattern Command pur
- `doc/devel/rfcs/` — RFCs structurés (cli, dom, task, recurrence, sync, ...)

### Écosystème (témoignage de la "toolabilité")

- [taskwarrior-tui](https://github.com/kdheepak/taskwarrior-tui) — TUI consommant `task` via export JSON
- [vit](https://github.com/scottkosty/vit) — UI vim-like
- [taskopen](https://github.com/jschlatow/taskopen) — ouvrir annotations comme liens
- [taskpirate (tw-hooks framework)](https://github.com/tbabej/taskpirate) — framework Python pour hooks
- [tw-hooks](https://github.com/bergercookie/tw-hooks) — autre framework hooks
- [Tools index](https://taskwarrior.org/tools/) — répertoire officiel

### Documents internes mdscan

- [CLAUDE.md](../CLAUDE.md) — agent instructions et vue d'ensemble projet
- [spec-v0.4.md](spec-v0.4.md) — spécification vivante v0.4
- [mdscan-taskwarrior-synergy.md](mdscan-taskwarrior-synergy.md) — couplage bicéphale (angle complémentaire — pas l'objet de ce doc)
- [kb-task-hybrid-research.md](kb-task-hybrid-research.md) — proposition checkboxes hybrides (alternative au couplage)
- [pkm-for-agents.md](pkm-for-agents.md) — features PKM traduites en primitives agent
