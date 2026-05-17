---
description: Recensement des alternatives à Taskwarrior offrant stockage texte plat et synchronisation git, comparées sur leurs forces, limites et compatibilité agent.
---

# Alternatives à Taskwarrior : stockage texte + sync git

> **Statut** : document de recherche, daté du 2026-05-14. Cible : profil médecin + dev side-projects, multi-machines (perso/pro), workflow agent-first (Claude Code).
>
> Doc soeur : [mdscan + Taskwarrior — synergies](mdscan-taskwarrior-synergy.md) (philosophie générale et intégration mdscan ↔ TW).

---

## 1. Cadrage : pourquoi chercher une alternative ?

### 1.1 Le verrou Taskwarrior

Taskwarrior reste le PM/CLI le plus mature de l'écosystème Unix (≈2008-aujourd'hui, syntaxe `task add`/`task done`/UDA/contextes, agenda riche, hooks). Mais depuis la **v3.0 (mars 2024)**, le stockage est passé d'un format texte (`pending.data` / `completed.data` au format ligne-clé=valeur) à **SQLite** (`taskchampion.sqlite3`). Le rationnel officiel est la performance et la cohérence multi-process — légitime. Le coût pour un workflow git-natif :

- **Diff SQLite = bruit**. Un `git diff` après une opération `task done` ne montre pas "tâche X passée à done" mais une mutation binaire des pages SQLite. Code review d'un commit = impossible.
- **Merge SQLite = piège**. Deux machines qui modifient leur `.task/` puis tentent `git pull` produisent des conflits sur le binaire — non résolus par les merge-drivers usuels.
- **Sync officielle = TaskServer / TaskChampion-Sync**. TaskServer (taskd) est en Go, demande un serveur (auto-hébergé ou Inthe.am). TaskChampion-Sync (le nouveau, v3+) est plus simple mais reste un démon HTTP. Aucun n'est "git push/pull".
- **Format texte conservé en export uniquement** (`task export` → JSON). Lecture seule, ne ferme pas la boucle multi-device.

Pour un utilisateur qui :
1. vit déjà dans git (médecin + dev, repos `notes-perso`, `dossiers-patients-anonymisés`, `side-projects`),
2. switche machine perso ↔ pro plusieurs fois par jour,
3. veut que Claude Code puisse parser/éditer ses tâches via le système de fichiers,

…le format SQLite + le démon de sync est un frottement permanent. **Un fichier texte poussé/tiré par git** est le contrat le plus simple, le mieux compris, le plus diff-able, le plus agent-friendly.

### 1.2 Ce qu'on cherche concrètement

Un outil qui :

- garde la **richesse fonctionnelle** de Taskwarrior (priorités, tags, projets, dates, recurrence, statuts),
- stocke en **fichiers texte plats** (Markdown, YAML, JSON, JSONL, todo.txt, .org…),
- considère **git comme la couche de sync** native (push/pull suffit),
- expose une **CLI** que Claude Code peut piloter (idéalement sortie JSON),
- reste **activement maintenu** (commits 2025-2026, pas un projet mort de 2019).

Ce document recense ces outils, les compare honnêtement, et formule une recommandation finale.

---

## 2. Critères d'évaluation

Sept axes, chacun noté 0 / 0.5 / 1 dans le tableau §4.

| # | Critère | Question concrète |
|---|---|---|
| C1 | **Texte plat** | Le stockage est-il diff-able par git ? (pas SQLite, pas binaire, pas DB encryptée) |
| C2 | **Sync git native** | `git push` / `git pull` suffit-il ? Pas de serveur dédié ? |
| C3 | **CLI-first** | Toutes les opérations courantes sont-elles disponibles en CLI ? |
| C4 | **Agent-friendly** | Sortie machine-readable (JSON / TSV / JSONL) ? Parsing déterministe ? |
| C5 | **Modèle riche** | Tags, dates (due/scheduled/done), priorités (≥3 niveaux), projets, statuts (≥3 états) ? |
| C6 | **Multi-device sans serveur** | Pas de serveur tiers à héberger ? Pas de compte propriétaire ? |
| C7 | **Activement maintenu** | Commits ou release dans les 12 derniers mois (≥ 2025-05) ? |

Barème simple : **score sur 7**. Au-delà de l'addition brute, on regarde les **incompatibilités fatales** (e.g. C1=0 disqualifie d'office pour notre besoin).

---

## 3. Panorama des outils

Trois familles s'imposent :

1. **CLI task managers nativement git+texte** — dstask, Backlog.md, TaskLite, taskbook, omm, todo.txt+addons, eagle (peu courant). C'est le coeur de cible.
2. **PKM avec tâches first-class** — Org-mode, Logseq, SilverBullet, Foam, Dendron, Tasks.md, Obsidian (mention). Stockage texte, sync git artisanale.
3. **Issue trackers distribués / GitHub Issues** — git-bug, GitHub Issues + `gh` CLI. Sync git native par construction.

Chaque outil ci-dessous est analysé selon la même grille.

---

### 3.1 dstask

**Repo** : [naggie/dstask](https://github.com/naggie/dstask)
**Langage** : Go (binaire statique single-file, multiplateforme)
**Statut** : v1.0 publié en novembre 2025, **v1.0.1 en janvier 2026** ; releases régulières (v0.28 en oct 2025 a introduit `due:`, v0.27 en déc 2024). Mainteneur Cal "naggie" Bryant. Le projet est déclaré « feature complete » mais reçoit toujours des patches.

#### Description
CLI todo manager **conçu autour de git**. Imite la surface Taskwarrior (`dstask add`, `dstask done`, contextes, tags, priorités) mais stocke chaque tâche dans un **fichier YAML séparé** dans un repo git dédié (`~/.dstask/` par défaut, configurable via `DSTASK_GIT_REPO`). Sync = `dstask sync` qui fait un `git pull --rebase && git push`.

#### Format de stockage
Un fichier YAML par tâche, nom de fichier = UUID4. Organisé par sous-dossier de statut (`pending/`, `resolved/`, `recurring/`…). En plus : chaque tâche peut avoir un **note Markdown** liée (`dstask note <id>` ouvre `$EDITOR`).

Exemple (reconstitué d'après le code Go `task.go` qui définit la struct `Task` avec tags YAML) :

```yaml
# ~/.dstask/pending/8c4f0e7a-1d23-4b69-9f12-3a8b7c6d2e44.yml
# Note: uuid n'est PAS dans le fichier, c'est le nom de fichier qui le porte
summary: "Rédiger compte rendu scinti osseuse Mme X"
notes: |
  Patiente vue ce matin. Fixation suspecte L3.
  Voir IRM du 2026-05-10 dans dossier partagé.
tags:
  - clinique
  - urgent
project: medecine-nucleaire
priority: P1
created: 2026-05-14T09:32:11Z
due: 2026-05-20T00:00:00Z
```

Le statut est dérivé du sous-dossier (`pending/`, `active/`, `resolved/`, `paused/`, `recurring/`, `templates/`). L'UUID est le nom de fichier. C'est élégant : le filesystem porte une partie de l'information, le YAML reste minimal.

Diff git après `dstask done 42` : le fichier passe de `pending/...yml` à `resolved/...yml` (un `git mv` logique). Très lisible humainement.

#### Sync
`dstask sync` = `git pull --rebase --autostash && git push`. Pas de serveur. Multi-device trivial : `dstask sync` au début et à la fin de chaque session.

Gestion conflits : git merge classique sur YAML, conflits rares (un fichier = une tâche, deux machines modifient rarement le même UUID). Les seules collisions concernent les **IDs séquentiels** (que dstask régénère, l'UUID restant la clé stable).

#### Interface
Pure CLI. Commandes principales :

```
dstask add Buy milk priority:P2 +grocery project:home due:2026-05-20
dstask                            # liste tâches "next" du contexte courant
dstask 42 done
dstask 42 start
dstask 42 note                    # ouvre l'éditeur sur la note Markdown
dstask sync                       # git pull/push
dstask context +work              # change le contexte
dstask show-projects
dstask next +urgent               # filtre par tag
dstask edit 42                    # ouvre le YAML brut
```

#### Couverture fonctionnelle

| Feature | Présence |
|---|---|
| Tags | ✓ (`+tag`) |
| Projets | ✓ (`project:name`) |
| Priorités | ✓ (P0–P3) |
| Due dates | ✓ (`due:`) |
| Statuts | ✓ (pending / active / paused / resolved / recurring / template) |
| Récurrence | ~ (via **templates** : `dstask template add ... ; dstask add template:N` recrée la tâche ; pas de cron-like natif) |
| Dépendances | ✓ (champ `Dependencies` dans la struct, par UUIDs) |
| Notes longues | ✓ (champ `notes` multiligne par tâche) |
| Contextes | ✓ (`dstask context +work`) |
| Import | ✓ (taskwarrior, GitHub issues — `dstask-import`) |

#### Compatibilité agent
**Bonne, plutôt sous-vendue dans la doc.** Plusieurs voies :

1. **Le code Go définit la struct `Task` avec à la fois des tags `yaml:` et `json:`.** Cela signifie que **la sérialisation JSON est nativement supportée** (il y a un flag `--json` ou équivalent sur plusieurs commandes `show-*` ; vérifier `dstask -h` au moment de l'adoption). Output structuré exploitable par `jq`.
2. **Lecture directe des fichiers YAML** : un agent peut bypasser la CLI et lire/écrire les `.yml` (un fichier = une tâche, UUID = nom de fichier). Format minimal et stable.
3. **Piloter la CLI** via Bash : `dstask add`, `dstask done`, etc. — interface ergonomique pour l'agent.

Avantage de l'option 2 : pas besoin d'apprendre la CLI surface, on travaille au niveau du modèle de données.

#### Forces
- **Vrai single-binary** (statique Go), zéro dépendance d'exécution.
- **Git-native** : pas d'apprendre un nouveau modèle de sync.
- **Un fichier = une tâche** = diff lisible, merge facile, agent peut éditer.
- **Notes Markdown** par tâche : pont naturel KB ↔ PM.
- **Feature-complete officiellement** (pas de churn de v2 imminent).

#### Faiblesses
- v1 = "feature complete", **rythme de dev ralenti** (avantage : stabilité ; risque : pas de nouvelles fonctions si besoin).
- Documentation parfois lacunaire sur les détails (le fichier `DATABASE_FORMAT.md` termine par "TODO elaborate with examples"). Il faut parfois aller lire le code Go.
- **Récurrence très basique** (templates manuels, pas de `rec:1w` style todo.txt).
- Sync = git, donc un repo `dstask` séparé à gérer (pas mêlé au repo de code).

#### Verdict partiel
**Le candidat le plus aligné** avec la cible "Taskwarrior - SQLite + git native". Léger, propre, agent-pilotable via FS et via la CLI. Note 7/7.

---

### 3.2 Backlog.md

**Repo** : [MrLesk/Backlog.md](https://github.com/MrLesk/Backlog.md)
**Langage** : TypeScript (binaire CLI distribué via npm/bun)
**Statut** : très actif (v1.45.1 en mai 2026, 888 commits, 5.5k stars). Mainteneur MrLesk, communauté qui grossit rapidement (positionné sur Hacker News mi-2025).

#### Description
**Markdown-native task manager + Kanban**, conçu pour **collaboration humain ↔ AI agents dans un repo git**. C'est l'outil le plus "moderne" du panel : MCP intégré, génération automatique d'instructions agent (`CLAUDE.md`, `AGENTS.md`), interfaces multiples (CLI, TUI Kanban, web browser local).

#### Format de stockage
Fichiers `.md` dans un dossier `backlog/` (ou `.backlog/`) à la **racine du repo de code**. Nom de fichier : `task-<id> - <titre>.md`.

Exemple (basé sur la structure documentée par le projet) :

```markdown
---
status: todo
assignees: [@alice]
labels: [backend, search]
priority: high
dependencies: [task-005]
---

# task-10 - Add core search functionality

## Description
Implement fuzzy search across task descriptions and tags.

## Acceptance Criteria
- [ ] Search returns matches within 100ms on 1000-task corpus
- [ ] Supports filter by status: `search "query" -s "In Progress"`
- [ ] CLI flag `--json` for agents

## Modified files
- src/search.ts
- tests/search.test.ts
```

Statuts livrés : **To Do, In Progress, Blocked, Done** (configurables). Priorités : **high / medium / low**.

Configuration projet : `backlog/config.yml` (autoCommit, gitHooks, etc.).

#### Sync
**Git natif** : le dossier `backlog/` vit dans le repo de code. `git commit` + `git push` synchronise. Option `autoCommit: true` pour committer automatiquement après chaque opération CLI.

C'est le modèle le plus intégré : **tâches versionnées AVEC le code qu'elles décrivent**. Un PR peut inclure et la feature et la tâche associée passée à `Done`.

#### Interface
Triple :
- **CLI** : `backlog task create/edit/list/...`
- **TUI Kanban** : `backlog board` (interactif terminal)
- **Web** : `backlog browser` (serveur local, UI moderne)
- **MCP** : `backlog mcp start` → Claude Code se branche dessus directement

#### Couverture fonctionnelle

| Feature | Présence |
|---|---|
| Tags / labels | ✓ |
| Priorités | ✓ (low/medium/high/critical configurable) |
| Statuts | ✓ (To Do / In Progress / Done par défaut, configurable) |
| Acceptance criteria | ✓ (first-class, checkboxes) |
| Assignee | ✓ |
| Dates | ✓ (created, due) |
| Récurrence | ✗ |
| Dépendances | ✓ (via `dependencies:` frontmatter) |
| Sous-tâches | ✓ |
| Documentation embarquée | ✓ (`backlog docs`, `backlog decisions` pour ADRs) |
| Notes Modified files | ✓ (champ dédié) |

#### Compatibilité agent
**Excellente, c'est le design central**. Trois angles :
1. **MCP** : Claude Code se connecte, manipule les tâches via outils MCP (création, mise à jour, listing).
2. **CLI** : `backlog task list -s "To Do"`, `backlog task create`, etc. Sortie texte exploitable.
3. **FS direct** : les `.md` sont des fichiers normaux, lisibles/éditables par tout outil.

Note : sortie JSON pure (`--json`) n'est pas explicitement documentée dans la doc principale (à vérifier au moment d'adopter ; le MCP est la voie préférée).

#### Forces
- **Le plus AI-native** du panel : conçu en 2024-2026 avec Claude Code en tête.
- **Acceptance criteria** comme citoyen de première classe (rare et précieux pour spec-driven dev).
- **Pas de repo séparé** : tâches dans le repo de code, versionées avec.
- **Trois UI** (CLI, TUI, Web) : ergonomie selon contexte.
- Très actif (5+ commits/jour mi-2026).
- Auto-génère `CLAUDE.md` / `AGENTS.md` au `backlog init`.

#### Faiblesses
- **Périmètre = un repo = un projet**. Pour des tâches *personnelles* transverses (médecine, vie perso, formation), il faudrait un repo dédié (e.g. `~/perso-backlog/`). Pas un problème en soi, mais ce n'est pas un "task manager global" à la Taskwarrior.
- **TypeScript + Bun** : dépendance Node/Bun à installer. Pas un single static binary (mais distribution via npm/bunx → presque trivial).
- Sortie JSON pas systématique (rely on MCP).
- Pas de récurrence native — mauvais pour les tâches répétitives (rendez-vous, contrôles patient).

#### Verdict partiel
**Le plus excitant pour le profil dev**. Pour la partie médecine (tâches perso transverses), moins idéal. Note 6/7. **Si Claude Code est l'interface principale, c'est probablement le meilleur choix.**

---

### 3.3 TaskLite

**Repo** : [ad-si/TaskLite](https://github.com/ad-si/TaskLite)
**Langage** : Haskell
**Statut** : actif (v0.5 publié, releases régulières), mainteneur Adrian Sieber.

#### Description
"Taskwarrior simplifié, écrit en Haskell". CLI + GraphQL server + webapp optionnel. Présenté comme une alternative plus simple et plus rapide à TW.

#### Format de stockage
**SQLite par défaut** (`tasklite.db`). C'est le point qui **disqualifie immédiatement TaskLite** pour notre cas d'usage : on remplace SQLite par SQLite, on ne résout rien.

Note : TaskLite expose un **export JSON/ndjson** (`tasklite ndjson`) qui pourrait être committé en git, mais ce n'est pas un round-trip natif (l'écriture passe toujours par SQLite).

#### Verdict
**Hors-sujet pour notre cible.** Stockage = SQLite, donc C1 = 0 → fatal. Si l'utilisateur préfère SQLite à fichiers plats, TaskLite est une alternative crédible à Taskwarrior, mais ce n'est pas notre besoin. Note 2/7.

---

### 3.4 taskbook (klaudiosinani)

**Repo** : [klaudiosinani/taskbook](https://github.com/klaudiosinani/taskbook)
**Langage** : Node.js
**Statut** : **dernier commit en 2021**, dernière release v0.3.0 il y a plusieurs années. **Projet en sommeil / non maintenu** depuis ~4 ans.

#### Description
CLI tasks + notes + boards, stockage JSON. UX agréable, output couleur, archive automatique.

#### Format de stockage
Un **fichier JSON unique** dans `~/.taskbook/storage/storage.json`. Configuration `~/.taskbook.json`.

```json
{
  "1": {
    "_id": 1,
    "_date": "Fri May 14 2026",
    "_timestamp": 1747300000000,
    "description": "Acheter du lait",
    "isStarred": false,
    "boards": ["@home"],
    "_isTask": true,
    "isComplete": false,
    "inProgress": false,
    "priority": 2
  }
}
```

#### Sync
Pas natif. On peut commiter `~/.taskbook/storage/storage.json` mais **un seul fichier JSON = merge git pénible** dès qu'il y a divergence (une tâche ajoutée sur chaque machine → conflit à résoudre à la main).

#### Verdict
**Mort / sans avenir.** Joli outil il y a 5 ans, mais aujourd'hui :
- non maintenu (C7 = 0),
- monolithe JSON peu friendly merge (C2 = 0.5),
- pas de récurrence, pas de dates due,
- modèle pauvre (priorité 1-3, boards = tags simples).

À éviter sauf nostalgie. Note 2/7.

---

### 3.5 todo.txt + extensions git

**Repos** : [todotxt/todo.txt-cli](https://github.com/todotxt/todo.txt-cli) (le shell script de référence), [topydo/topydo](https://github.com/topydo/topydo) (la version Python avancée).
**Statut** : todo.txt-cli est mature (créé par Gina Trapani, format stable), maintenance lente mais réelle. topydo : commits récents (2025).

#### Description
**Format texte 1-ligne-par-tâche**, défini par une [spec publique](https://github.com/todotxt/todo.txt). Lisible par n'importe quel éditeur, parseable par n'importe quel script.

Format ligne :
```
(A) 2026-05-14 Rédiger compte rendu scinti +radiologie @hopital due:2026-05-20
```

- `(A)` = priorité (A à Z)
- `2026-05-14` = date de création
- `+projet` = projet
- `@contexte` = contexte (lieu/personne)
- `key:value` = metadata libre (`due:`, `rec:`, `t:` pour threshold date…)
- Préfixe `x ` = terminé

#### Format de stockage
**Un seul fichier** `todo.txt` + optionnellement `done.txt`. Stockage : un dossier `~/.todo/` (`$TODO_DIR`).

#### Sync
**Pas natif, mais trivial à brancher** : il existe un **addon `git` officiel** ([Todo.sh add-on directory](https://github.com/todotxt/todo.txt-cli/wiki/Todo.sh-Add-on-Directory)) qui :
- `commit` après chaque modification,
- `push` vers origin,
- `pull --rebase` au démarrage.

Soit `todo.sh git push` / `pull`. Multi-device fonctionne, à condition d'accepter que **deux modifs simultanées sur deux machines = conflit ligne-à-ligne dans `todo.txt`**. Avec un seul utilisateur, c'est gérable (sync au début et fin de session).

#### Interface
- `todo.sh` (bash) : `add`, `do`, `pri`, `ls`, `lspri`, `report`…
- `topydo` (Python) : surcouche avec prompt interactif, mode colonnes, dépendances, recurrence (`rec:1w`).

#### Couverture fonctionnelle

| Feature | Présence |
|---|---|
| Priorités | ✓ (A–Z) |
| Projets | ✓ (`+name`) |
| Contextes | ✓ (`@name`) |
| Due dates | ✓ (`due:`) |
| Threshold | ✓ (`t:`) |
| Récurrence | ✓ (topydo : `rec:1w`) |
| Statuts | ✗ (binaire : ouvert / fait) |
| Dépendances | ✓ (topydo : `id:` + `p:`) |
| Notes longues | ✗ (1 ligne) |
| Tags | via `+` ou inline `#tag` |

#### Compatibilité agent
**Excellente**. Format ligne = parsable trivialement (`awk`, `grep`, `cut`, `python -c`). Spec publique stable. Un agent peut :
- lire `todo.txt` directement,
- `rg "@hopital"` pour filtrer,
- ajouter une ligne (`echo "..." >> todo.txt`),
- éditer une ligne (`sed -i` ou rewrite).

Mais **pas de JSON natif**. Topydo expose un mode JSON via `--config` mais c'est marginal.

#### Forces
- **Format le plus stable et portable** du panel. Spec publique 2006, lisible humainement, parseable trivialement.
- Énorme écosystème (apps mobiles, plugins Vim/Emacs, extensions Web).
- **Très simple, très robuste**.
- Sync git = un addon officiel.

#### Faiblesses
- **Un seul fichier** = source de conflits merge si édition simultanée multi-device. Mitigation : workflow strict "sync au début, sync à la fin".
- Modèle un peu **simpliste** : pas de statut intermédiaire (in-progress), pas de notes longues.
- Topydo apporte beaucoup mais **fragmente l'écosystème** (l'addon git officiel est pour todo.sh, pas topydo).

#### Verdict partiel
**Le standard "moindre dénominateur commun"**. Aucun système ne fait moins, beaucoup font plus. À choisir si la portabilité absolue prime sur la richesse. Note 5/7.

---

### 3.6 git-bug

**Repo** : [git-bug/git-bug](https://github.com/git-bug/git-bug)
**Langage** : Go
**Statut** : actif (dernière maj mai 2025), mainteneurs MichaelMure + nouvelle équipe.

#### Description
**Bug tracker distribué embarqué DANS git**. Les bugs sont stockés comme **objets git** (blobs/trees/commits) dans des refs spéciales (`refs/bugs/*`), pas comme fichiers de travail. Sync via `git-bug push` / `git-bug pull` qui font des `git push refs/bugs/*` sous le capot.

#### Format de stockage
**Ni texte ni fichier visible** — les bugs sont des objets git directement, accessibles via `git cat-file`. C'est un **format binaire indexé par git lui-même**.

```
$ git-bug ls
4c4f4c bug Foo bar [open] alice
...
$ git cat-file -p refs/bugs/4c4f4c...
tree ...
parent ...
author alice ...
committer alice ...

{"title": "Foo bar", "labels": [...], ...}
```

C'est un compromis : pas SQLite, mais pas non plus "fichier markdown lisible". Le contenu est du JSON sérialisé, stocké dans des blobs git. Diff humain = via `git-bug` CLI.

#### Sync
**Native git, mais via refs spéciales** : `git-bug pull` = `git fetch refs/bugs/*` + merge logique. Pas de conflit fichier car chaque opération est un commit immuable dans la timeline du bug — CRDT-like.

#### Interface
- CLI : `git-bug add`, `git-bug status`, `git-bug ls`, `git-bug comment`
- TUI : `git-bug termui`
- Web : `git-bug webui` (UI moderne)
- Bridges : import/sync avec GitHub Issues, GitLab, Jira
- GraphQL API : `git-bug api`

#### Couverture fonctionnelle

| Feature | Présence |
|---|---|
| Labels (tags) | ✓ |
| Statuts | ✓ (open / closed) |
| Assignee | ✓ |
| Commentaires | ✓ (CRDT, append-only) |
| Identités multiples | ✓ (PGP-signable) |
| Priorités | ✗ (par labels) |
| Due dates | ✗ |
| Sous-tâches | ✗ |
| Récurrence | ✗ |

#### Compatibilité agent
- CLI texte standard.
- GraphQL API (= JSON queryable) — c'est le **gros plus pour les agents**.
- Bridges GitHub → un agent peut synchroniser bugs local ↔ GitHub Issues.

#### Forces
- **Vraie sync git distribuée**, sans serveur, conçue offline-first (Linus-style).
- GraphQL API = agent peut interroger en SQL-like.
- Bridges GitHub Issues = pas d'enfermement.
- Identités cryptographiques (signature des commits bug).

#### Faiblesses
- **Pas un task manager, c'est un bug tracker**. Modèle binaire (open/closed), pas de priorité riche, pas de due date, pas de récurrence.
- Stockage = objets git dans `refs/bugs/*`. **Pas un fichier texte** que l'utilisateur peut grep facilement. `git-bug` est requis pour lire/écrire (sauf à parler git plumbing).
- Pour des tâches personnelles transverses (médecine), c'est *trop* projet-centré.

#### Verdict partiel
**Excellent pour un bug tracker per-repo distribué**, mais hors-cible comme remplaçant général de Taskwarrior. Note 4/7 (sur les 7 critères) — manque dates, priorités, récurrence, et "fichier texte plat lisible direct".

---

### 3.7 Tasks.md (BaldissaraMatheus)

**Repo** : [BaldissaraMatheus/Tasks.md](https://github.com/BaldissaraMatheus/Tasks.md)
**Langage** : SolidJS + Koa (Node.js backend)
**Statut** : actif (commits 2025), mainteneur seul, audience modeste.

#### Description
**Kanban board self-hosted** dont chaque colonne = un dossier, chaque carte = un fichier Markdown. Interface web, déploiement Docker.

#### Format de stockage
Hiérarchique sur disque :
```
tasks/
├── To Do/
│   ├── Implement OAuth.md
│   └── Migrate DB.md
├── In Progress/
│   └── Review PR 42.md
└── Done/
    └── Fix CSS.md
```

Chaque `.md` est un fichier libre (markdown + frontmatter possible).

#### Sync
**Pas natif**, mais le dossier `tasks/` est un dossier normal → on peut le mettre en repo git, commiter, pusher. **Caveat** : déplacer une carte entre colonnes = `git mv` (renommage), bien géré par git. Multi-device fonctionne tant que l'app n'est pas lancée sur deux machines simultanément.

#### Interface
- **Web uniquement** (PWA installable). Pas de CLI.
- Drag-and-drop kanban dans le navigateur.

#### Compatibilité agent
**Faible**. Pas de CLI. Un agent doit attaquer le filesystem directement (créer un `.md` dans `tasks/To Do/`, le déplacer pour changer de statut). Faisable, mais l'app web n'est pas faite pour ce pilotage.

#### Verdict partiel
Sympathique pour un **humain qui veut un kanban Markdown self-hosté**. **Mauvais profil agent-first** (pas de CLI, pas de JSON). À considérer si le besoin est un kanban web personnel ; à oublier si l'objectif est Claude Code. Note 3/7.

---

### 3.8 Org-mode + git (Emacs)

**Site** : [orgmode.org](https://orgmode.org/)
**Statut** : éternel. Embarqué dans Emacs, ~25 ans de maturité.

#### Description
**Le standard absolu** du PKM + task management texte. Un fichier `.org` est du texte plat structuré (headings, propriétés, tags, dates, états TODO). Emacs offre l'agenda, le clocking, l'export, etc.

#### Format de stockage
Un ou plusieurs fichiers `.org` (la doc recommande quelques gros fichiers thématiques). Chaque heading peut être une tâche :

```org
* TODO Rédiger compte rendu scinti osseuse Mme X
  SCHEDULED: <2026-05-15 jeu>
  DEADLINE: <2026-05-20 mar>
  :PROPERTIES:
  :PRIORITY: A
  :TAGS:     :clinique:urgent:
  :ID:       4c4f4c-...
  :END:

  Patiente vue ce matin. Fixation suspecte L3.
  Voir IRM du 2026-05-10.

** TODO Envoyer dossier au rhumatologue
** DONE Demander IRM complémentaire
   CLOSED: [2026-05-13 mar 14:32]
```

Format texte intégral, indentation par étoiles, propriétés en drawer `:PROPERTIES:`.

#### Sync
**Pas natif Emacs, mais Org-files sont du texte plat** → git fonctionne nativement. `git pull && git push`. Conflits possibles si un même heading est modifié sur deux machines (résolution texte standard).

Sur mobile : **Orgzly** (Android, sync filesystem → Syncthing) ou **organice** (PWA, sync Dropbox/GitLab/WebDAV).

#### Interface
- **Emacs** : éditeur natif. Tout l'agenda, capture, clocking, export.
- **Vim** : `vim-orgmode` (incomplet).
- **VS Code** : extensions limitées.
- **Web** : organice (PWA).
- **Mobile** : Orgzly, Beorg (iOS).
- **CLI dédiée** : pas vraiment. `pandoc` lit `.org`. Des projets comme `orgify`, `org-cli` existent mais marginaux.

#### Couverture fonctionnelle
**Maximale** dans le panel. Tags hiérarchiques, priorités A/B/C, états workflow configurables, SCHEDULED + DEADLINE + CLOSED, récurrence (`+1w`, `++1m`), clocking (temps passé), dépendances (`ORDERED` property), liens internes (`[[id:...]]`), agenda transversal.

#### Compatibilité agent
**Mitigée**. Le format `.org` est texte plat **mais syntaxiquement plus complexe que Markdown ou JSON**. Un agent peut :
- lire un `.org` (le texte est lisible),
- ajouter une tâche en append (`* TODO Foo`),
- ⚠️ mais éditer proprement (changer un état, ajouter une propriété, gérer le drawer) est non trivial sans parseur dédié.

Parseurs Python : `orgparse` (read-only, OK), `PyOrgMode` (R/W, vieux). Pas de canonique en 2026.

`pandoc --from org --to json` permet de récupérer un AST JSON, mais l'inverse (mutations) est laborieux.

#### Forces
- **Modèle de tâches le plus riche, sans concurrence**. Tout ce que Taskwarrior fait, et plus.
- Texte plat, git-friendly.
- 25 ans de stabilité.
- Mobile Orgzly est convaincant.

#### Faiblesses
- **Couplage Emacs**. Sans Emacs, on perd l'agenda riche, le clocking ergonomique, la capture rapide. Les outils non-Emacs sont des **lecteurs partiels**.
- **Syntaxe complexe pour un agent**. Le drawer `:PROPERTIES:`, les liens `[[id:...]]`, les blocs `:LOGBOOK:`, etc. demandent un parseur dédié.
- **Discoverability faible** pour qui n'est pas déjà Emacs.

#### Cas d'usage
Voir §6 pour un traitement détaillé. Pour le profil "médecin + dev, pas Emacs", **Org-mode est probablement overkill et culturellement décalé**. Si l'utilisateur acceptait d'apprendre Emacs (ou seulement Doom Emacs / Spacemacs), c'est sans concurrence. Sinon, c'est un format qu'on **subit plutôt qu'on apprécie**. Note 5/7 conditionnelle.

---

### 3.9 Logseq

**Site** : [logseq.com](https://logseq.com)
**Repo** : [logseq/logseq](https://github.com/logseq/logseq)
**Statut** : actif, communauté large, transition v1 → v2 (DB-version) en cours (mai 2026).

#### Description
**Outliner + PKM + task management**. Inspiré d'Org-mode et Roam, mais GUI graphique (desktop + mobile). Stockage **Markdown ou Org** au choix. Tâches first-class via `TODO`/`DOING`/`DONE` etc.

#### Format de stockage
Un dossier `pages/` (un fichier `.md` par page) + un dossier `journals/` (un fichier par jour). Chaque bullet est un "block" avec un ID UUID.

```markdown
# Patients du jour
- TODO Compte rendu scinti Mme X
  due:: 2026-05-20
  priority:: A
  tags:: [[clinique]] [[urgent]]
  - Fixation L3 suspecte, voir IRM
- DOING Préparer présentation staff
  - id:: 6634abcd-...
```

Format Markdown étendu (proprietés via `key:: value`, bullets imbriqués).

#### Sync
- **Logseq Sync officiel** : payant, propriétaire (E2E encrypted, mais cloud Logseq).
- **Git** : 100% supporté, beaucoup d'utilisateurs versionnent leur graphe en git et synchronisent ainsi. Fichiers `.md` = diff classique.
- **Syncthing** : alternative populaire (recommandée dans la communauté en 2025 pour cross-device fiable).

⚠️ **2025-2026 : Logseq DB version**. La nouvelle version v2 abandonne le stockage Markdown plat pour une DB SQLite, dans un objectif perf. Le mode "Markdown" reste maintenu en parallèle (rassurance utilisateurs). **À surveiller** avant adoption.

#### Interface
- Desktop app (Electron) : édition outliner + GUI.
- Mobile : iOS + Android.
- CLI : **non native**. Projet [`logseq-cli`](https://github.com/...) existe mais marginal.

#### Couverture fonctionnelle
- États tâches : TODO, DOING, DONE, LATER, NOW, WAITING, CANCELLED.
- Priorités : A / B / C.
- Due dates : `SCHEDULED:` / `DEADLINE:` style Org.
- Tags : `#tag` ou `[[page]]`.
- Récurrence : limitée, via propriétés.
- Queries Datalog : `{{query (and (task TODO) (priority A))}}`.
- Backlinks : automatiques (puissants).

#### Compatibilité agent
**Moyenne**. Fichiers Markdown = lisibles, mais format propriétaire (bullets, `id::`, `block-id`). Pas de CLI officielle. Un agent peut lire/écrire des fichiers `.md`, mais doit respecter la convention Logseq. **Pas conçu agent-first**.

#### Forces
- UX riche pour humain.
- Mobile inclus.
- Backlinks puissants.
- Queries Datalog.

#### Faiblesses
- **GUI-first, CLI ignorée**.
- **Transition v2 vers SQLite** crée incertitude sur le futur "fichier plat".
- Format de bloc avec `id::` peut polluer le diff git.
- Pas conçu pour un agent.

#### Verdict partiel
Bon outil pour un humain qui veut outliner + tâches sans Emacs. **Pas agent-first.** Note 4.5/7.

---

### 3.10 SilverBullet.md

**Site** : [silverbullet.md](https://silverbullet.md)
**Repo** : [silverbulletmd/silverbullet](https://github.com/silverbulletmd/silverbullet)
**Statut** : actif (commits 2025-2026), mainteneur principal Zef Hemel.

#### Description
**PKM self-hosted Markdown, scriptable en Lua**. Tâches first-class via GFM checkboxes + scripts query. UI web (PWA local-first), serveur Deno.

#### Format de stockage
Markdown plat dans un dossier de pages. Tâches = GFM checkboxes (`- [ ] foo`) avec metadata inline.

```markdown
# Tâches cette semaine

- [ ] Rédiger CR scinti Mme X #clinique due:2026-05-20
- [x] Envoyer mail Dr Y
- [/] Préparer staff lundi

## Queries

```query
task
where state = " "
order by due
```
```

#### Sync
**Git** (workflow naturel, le dossier de pages est un repo). PWA cache local + sync vers serveur. **Pas de sync git native intégrée** : on commit/push à la main ou via cron.

#### Interface
- Web (PWA, mobile-friendly).
- Pas de CLI native. Mais : éditeur Markdown sur fichiers plats → tout outil terminal marche en parallèle.

#### Couverture fonctionnelle
- Tâches GFM (5 états potentiels via Lua extensions).
- Queries Lua sur le corpus.
- Tags inline `#tag`.
- Backlinks automatiques.
- Templates Lua.

#### Compatibilité agent
**Moyenne**. Fichiers Markdown plats = ✓ pour lecture/écriture par agent. Pas de CLI dédiée mais les fichiers étant Markdown standard, n'importe quel outil (`rg`, `awk`, `python`) marche.

#### Forces
- **Markdown plat**, lisible direct.
- Local-first, PWA.
- Scriptable Lua = customisable à mort.
- Self-hosted simple (Deno).

#### Faiblesses
- Nécessite **serveur** (au moins local). Pas vraiment "pure CLI multi-machine".
- Queries Lua dans les fichiers = pollue le Markdown (mais reste lisible).
- Pas de CLI.

#### Verdict partiel
Excellent pour humain qui veut un Obsidian self-hosted + Markdown plat. Pour agent + git pur, **trop de surface d'app web**. Note 4/7.

---

### 3.11 Foam (VS Code) + tasks

**Repo** : [foambubble/foam](https://github.com/foambubble/foam)
**Statut** : maintenance lente. Dernier release notable courant 2024.

#### Description
PKM dans VS Code via extension, fichiers Markdown plats avec wikilinks `[[note]]`. Tâches = checkboxes GFM, gérables via extensions VS Code (Todo Tree, etc.).

#### Format / Sync
Markdown plat dans un dossier, git natif (VS Code = git natif).

#### Verdict partiel
Plus PKM que task manager. Tâches gérées via plugins VS Code, pas first-class. Note 3.5/7. **Pas un task manager dédié.**

---

### 3.12 Dendron

**Repo** : [dendronhq/dendron](https://github.com/dendronhq/dendron)
**Statut** : **archivé / projet arrêté en 2023**. Mainteneurs ont communiqué la fin du projet.

#### Verdict
**Mort.** Note 1/7. À oublier.

---

### 3.13 omm (CLI)

**Repo** : [jonas-grgt/omm](https://github.com/jonas-grgt/omm) (à vérifier — confusion possible avec d'autres projets `omm`)
**Statut** : marginal, peu d'activité.

#### Verdict partiel
Outil de niche, communauté trop petite pour recommandation. Pas creusé davantage. Note 2/7.

---

### 3.14 GitHub Issues + `gh` CLI

Voir traitement dédié en §5.

---

### 3.15 taskell

**Repo** : [smallhadroncollider/taskell](https://github.com/smallhadroncollider/taskell)
**Langage** : Haskell
**Statut** : **développement en pause** (le mainteneur a indiqué prendre une pause). PRs acceptés mais peu d'activité.

#### Description
**Kanban CLI en ncurses**, lit/écrit **un seul fichier Markdown** comme source de vérité. Imports Trello et GitHub Projects. Vi-style keybindings.

#### Format de stockage
Un fichier `taskell.md` par projet :

```markdown
## To Do

- Implémenter OAuth
    > Avec PKCE
    - [ ] Auth code flow
    - [ ] Token refresh

## In Progress

- Wire up JWT middleware

## Done

- Setup CI
```

Listes de second niveau = colonnes kanban. Très lisible, **diff git propre**.

#### Sync
Le `taskell.md` est un fichier Markdown normal → git commit + push. Multi-device si peu de conflits (un seul fichier monolithique = même problème que todo.txt).

#### Verdict partiel
**Bel objet, mais le mainteneur en pause = risque**. Pour un humain qui veut un kanban TUI ultra-simple lié à un projet en repo git, ça reste valide. Pas pour de l'investissement long terme à mon sens. Note 4/7 (C7 dégradé).

---

### 3.16 jrnl

**Repo** : [jrnl-org/jrnl](https://github.com/jrnl-org/jrnl)
**Statut** : actif (commits 2025).

#### Description
CLI journal, **pas un task manager**. Inclus ici pour mention car parfois proposé comme outil hybride. Stockage texte (encrypté optionnel), sync git OK.

#### Verdict
**Hors-sujet.** Ce n'est pas un task manager. Si l'utilisateur veut un journal en plus de ses tâches, jrnl est très bien — mais ne remplace pas Taskwarrior. Note non applicable.

---

### 3.17 markwhen

**Repo** : [mark-when/markwhen](https://github.com/mark-when/markwhen)
**Statut** : actif (2025), niche.

#### Description
**Timelines en Markdown**, pas tasks. Format `2026-05-14: title` ligne par événement.

#### Verdict
**Hors-sujet** comme task manager, mais utile en complément (roadmap visuelle d'un projet). Pas évalué sur les 7 critères.

---

### 3.18 Récap des outils écartés rapidement

| Outil | Raison du rejet |
|---|---|
| **TaskLite** | SQLite → contredit C1 |
| **taskbook (klaudiosinani)** | Non maintenu depuis 2021 |
| **ultralist** | Dernière release v1.7.0 en novembre 2020, projet endormi |
| **Dendron** | Projet arrêté en 2023 |
| **jrnl** | Journal, pas task manager |
| **markwhen** | Timelines, pas task manager |
| **eagle.md** | Pas trouvé de projet correspondant établi |
| **gtask-md / md-tasks** | Aucun projet sérieux à ce nom |
| **Tracks / GTDNext** | Web-app SaaS, hors cible |
| **Foam** | Tâches non first-class |
| **omm** | Trop niche / activité faible |
| **dnote** | Note-taking pur (pas de tâches structurées) |
| **vimwiki tasks** | Convention plutôt qu'outil ; checkboxes Markdown gérées via plugin éditeur, pas de modèle riche |

---

## 4. Tableau comparatif

Légende : ✓ = oui pleinement / ~ = partiel / ✗ = non / ⚠ = caveat important.

| Outil | C1 Texte | C2 Sync git native | C3 CLI | C4 Agent-friendly | C5 Modèle riche | C6 Multi-device sans serveur | C7 Maintenu | Score |
|---|---|---|---|---|---|---|---|---|
| **dstask** | ✓ | ✓ | ✓ | ✓ (JSON tags, FS direct) | ✓ | ✓ | ✓ | **7/7** |
| **Backlog.md** | ✓ | ✓ | ✓ | ✓ (MCP) | ~ (pas récurrence) | ✓ | ✓ | **6/7** |
| **todo.txt + git addon** | ✓ | ~ (addon) | ✓ | ~ (pas JSON) | ~ | ✓ | ✓ | **5/7** |
| **Org-mode + git** | ✓ | ✓ | ✗ (Emacs) | ~ (syntaxe complexe) | ✓✓ | ✓ | ✓ | **5/7** |
| **Logseq** | ✓ ⚠ (v2 SQLite) | ✓ | ✗ | ~ | ✓ | ✓ | ✓ | **4.5/7** |
| **GitHub Issues + gh** | ✗ (SaaS) | ✓ (natif !) | ✓✓ | ✓✓ (gh --json) | ~ (labels only) | ✓ (GitHub) | ✓ | **5.5/7** mais C1 fatal |
| **SilverBullet** | ✓ | ~ (manuel) | ✗ | ~ | ~ | ✗ (serveur) | ✓ | **4/7** |
| **git-bug** | ~ (refs git) | ✓✓ | ✓ | ✓ (GraphQL) | ✗ (pauvre) | ✓ | ✓ | **4/7** |
| **Tasks.md** | ✓ | ~ (manuel) | ✗ | ✗ | ~ | ✗ (Docker) | ✓ | **3/7** |
| **Foam** | ✓ | ✓ | ✗ | ~ | ✗ | ✓ | ~ | **3.5/7** |
| **taskell** | ✓ | ✓ | ~ (TUI) | ✗ | ~ | ✓ | ✗ (en pause) | **3.5/7** |
| **TaskLite** | ✗ (SQLite) | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | 2/7 |
| **taskbook** | ✓ (JSON unique) | ~ | ✓ | ~ | ~ | ✓ | ✗ | 2/7 |
| **Dendron** | — | — | — | — | — | — | ✗ | mort |

**Lecture rapide** : trois finalistes émergent — **dstask**, **Backlog.md**, **todo.txt+git**. Org-mode est l'outsider technique (riche mais Emacs-bound). GitHub Issues+gh est traité à part car son stockage n'est pas un fichier texte sur la machine de l'utilisateur (donc C1 ne s'applique pas comme pour les autres).

---

## 5. Cas particulier : GitHub Issues + `gh` CLI comme task manager

### 5.1 Le pitch

Utiliser GitHub Issues comme task manager personnel via la CLI `gh`. Sync git native (par définition : GitHub *est* le miroir), UI web et mobile gratuites, intégration parfaite avec le code, le tout pilotable à 100% en CLI.

### 5.2 Forces

- **Sync native, zéro effort**. GitHub stocke tout côté serveur, accessible partout (web, iOS app, Android app, CLI). Pas de git push/pull à penser.
- **UI multi-supports gratuites**. L'app mobile GitHub est honorable pour gérer des issues à la volée. Idéal pour ajouter une tâche entre deux patients.
- **CLI `gh` mature** :
  ```bash
  gh issue create --title "..." --body "..." --label urgent --milestone "v1.0"
  gh issue list --state open --label urgent --json number,title,labels,assignees
  gh issue view 42 --json body,comments
  gh issue close 42 --comment "Done in PR #99"
  gh issue edit 42 --add-label in-progress --remove-label todo
  ```
- **Sortie `--json` sur quasi toutes les commandes** = agent-friendly de classe mondiale.
- **Projects v2** : kanban, fields custom (priority single-select, due date date-field, story-points number-field), saved views. Pilotable via `gh project`.
- **Intégration code** : `Fixes #42` dans un commit ferme l'issue.
- **Recherche puissante** : GitHub search syntax (`is:open label:urgent assignee:@me`).

### 5.3 Limites

- **Stockage côté GitHub**. Ce n'est pas un fichier texte sur ta machine. Si GitHub disparaît / change ses TOS / on perd l'accès au compte → pas de fallback offline. **C1 fail.**
- **Un repo = un projet**. Pour gérer "tâches médecine" + "side-projects dev" + "vie perso", il faut un repo dédié à chaque dimension (e.g. `~/tasks-perso`, `~/tasks-medecine`, repos privés). Workable mais éclaté.
- **Pas de récurrence native**. Workaround : GitHub Actions cron qui recrée une issue tous les lundis. Faisable mais lourd.
- **Pas de priorité riche native**. Projects v2 permet un champ "Priority" custom, mais pas dans les issues nues.
- **Vie privée / confidentialité médicale**. Pour des tâches liées à des patients (même anonymisées), **GitHub n'est PAS l'endroit**. Tout repo privé reste hébergé chez Microsoft. À limiter aux side-projects dev et tâches non-cliniques.
- **Pas offline-first**. `gh` requiert le réseau pour la plupart des commandes.

### 5.4 Workflows utiles

#### Labels comme tags
```bash
# Setup initial : créer les labels
gh label create urgent --color FF0000
gh label create clinique --color 0066CC
gh label create dev --color 00AA00

# Filtrer
gh issue list --label urgent --json number,title
```

#### Milestones comme deadlines
```bash
gh issue create --milestone "Semaine 20" --title "..."
gh issue list --milestone "Semaine 20" --state open
```

#### Projects v2 pour kanban + champs custom
```bash
gh project create --owner @me --title "Tableau perso"
gh project field-create 1 --owner @me --name "Priority" --data-type SINGLE_SELECT --single-select-options "P0,P1,P2,P3"
gh project item-add 1 --owner @me --url <issue-url>
```

#### Recherche cross-repo
```bash
gh api graphql -f query='query { search(query: "is:issue is:open assignee:@me", type: ISSUE, first: 50) { nodes { ... on Issue { title url labels(first:10){nodes{name}} } } } }'
```

### 5.5 Claude Code via `gh`

Excellent pilotage : Claude Code peut, sans aucune configuration spéciale :
```bash
gh issue list --state open --json number,title,labels,body --jq '.[] | select(.labels[].name == "urgent")'
gh issue create --title "Implémenter OAuth" --body "$(cat spec.md)" --label backend
gh issue comment 42 --body "Progress: 3/5 acceptance criteria validated"
gh issue close 42
```

Sortie JSON pure, idiomatique pipeline `jq`. **C'est probablement l'interface agent la plus mature de tout le panel** — mais le stockage n'est pas chez l'utilisateur.

### 5.6 Verdict

**Excellent pour les side-projects dev**, en tant que task tracker per-repo. **Inadapté pour les tâches personnelles / médicales / transverses** à cause du stockage centralisé GitHub.

Recommandation : **combiner**. GitHub Issues + `gh` pour les tâches liées au code (in-repo). Un autre outil (dstask ou Backlog.md global) pour les tâches transverses perso/médecine.

---

## 6. Cas particulier : Org-mode + git

### 6.1 Pourquoi un traitement à part

Org-mode mérite sa propre section parce que :
- Son **modèle de tâches est le plus riche** de tout l'écosystème texte (rien d'autre ne match).
- Son **format `.org` est texte plat git-friendly** par construction.
- Son **couplage Emacs est culturellement clivant** : pour qui n'est pas déjà dans Emacs, c'est un mur d'apprentissage. Pour qui y est, c'est sans concurrence.

### 6.2 Le coeur du dilemme

L'utilisateur (médecin + dev side-projects, **pas Emacs**) doit décider :

- **Option A** : investir 1-2 semaines pour devenir fluide Doom Emacs ou Spacemacs (config pré-mâchée), puis profiter d'Org-mode sans frottement. Une fois adopté, c'est durable (Emacs est éternel).
- **Option B** : utiliser Org-mode comme format de stockage **sans Emacs**, via organice (PWA web) ou éditeurs Markdown qui parsent Org. Perd l'agenda, le clocking, la capture rapide. Devient un format texte parmi d'autres, sans la magie associée.

Option B est **un mauvais compromis** : on hérite de la complexité syntaxique d'Org sans son outillage. Mieux vaut alors choisir un format conçu pour fonctionner sans IDE (Markdown checkboxes, todo.txt, YAML dstask).

### 6.3 Outils non-Emacs pour `.org`

- **organice** ([200ok-ch/organice](https://github.com/200ok-ch/organice)) : implémentation web (PWA) d'Org-mode. Sync Dropbox / GitLab / WebDAV. Activement maintenu. Mobile-friendly. **Pas de sync git pure** native (mais GitLab marche).
- **Orgzly** (Android) : app mobile dédiée. Sync via WebDAV ou filesystem (donc combinable avec Syncthing). **Pas de git natif** (mais sync filesystem → git côté serveur ok).
- **Beorg** (iOS) : équivalent iOS d'Orgzly.
- **vim-orgmode** / **nvim-orgmode** : ports vers (Neo)vim. Couvre l'édition + agenda partiel. **Pas tout Org**, mais souvent suffisant pour task management quotidien. **Combinable avec un workflow git pur**.
- **VS Code extensions** : "Org Mode" et "vscode-org-mode". Partielles, parfois buggy.

### 6.4 Verdict

Pour le profil utilisateur, **Org-mode n'est pas recommandé** sauf engagement explicite à apprendre Emacs (ou nvim-orgmode pour les vimmers). C'est l'outil le plus puissant techniquement mais aussi le plus coûteux culturellement.

**Si l'utilisateur veut vraiment** la richesse Org sans Emacs : **nvim-orgmode** ([nvim-orgmode/orgmode](https://github.com/nvim-orgmode/orgmode)) est l'option la plus rationnelle aujourd'hui (2026). Plugin actif, couvre l'agenda, propre dans un workflow git pur. À tester sur 2-3 semaines avant adoption pérenne.

---

## 7. Recommandations selon profil d'usage

Chaque profil correspond à un trade-off différent. Le profil utilisateur peut tomber dans plusieurs cases (et alors combiner les outils).

### 7.1 "Je veux le plus simple possible, juste pour moi"

→ **todo.txt + addon git officiel**

Un fichier, un format universel, n'importe quel éditeur marche, sync trivial. Pas de DB, pas de serveur, pas de Node, pas de Bun. Limites : pas de statuts intermédiaires, modèle un peu pauvre. Suffit pour 80% des besoins personnels.

Setup en 10 minutes :
```bash
git clone https://github.com/todotxt/todo.txt-cli ~/todo
mkdir ~/.todo && cd ~/.todo
git init
touch todo.txt done.txt
# Installer l'addon git :
mkdir -p .todo.actions.d
curl -o .todo.actions.d/git <url-addon>
# Lier le repo distant
git remote add origin git@github.com:user/todo-perso.git
todo.sh git push
```

### 7.2 "Je veux que Claude Code puisse facilement piloter"

→ **Backlog.md** (pour tâches par repo) **+ dstask** (pour tâches transverses)

Backlog.md a un MCP intégré, génère le `CLAUDE.md`/`AGENTS.md` au `backlog init`, pas mieux pour qu'un agent prenne la main sur un projet. Pour les tâches qui ne sont pas liées à un repo précis (rendez-vous, courses, vie médicale), dstask en repo global (`~/.dstask/`) reste l'outil.

### 7.3 "Je veux multi-device sans friction"

→ **dstask** ou **GitHub Issues**

dstask : `dstask sync` au début et fin de session, fini. Repo git séparé, push/pull rapide. Marche partout où il y a git + le binaire dstask.

GitHub Issues : pas de sync à penser, l'app mobile officielle fonctionne (limite : confidentialité, et un repo par dimension).

### 7.4 "Je suis prêt à investir 1 semaine d'apprentissage pour la solution ultime"

→ **Org-mode via nvim-orgmode** (si vimmer) **ou Doom Emacs + Org** (si neutre/curieux Emacs)

Modèle de données le plus riche, écosystème mature, durable 30 ans. Coût d'entrée réel (1-2 semaines), bénéfice durable. **Conseillé seulement si l'utilisateur a réellement envie** : sinon, frustration garantie.

### 7.5 "Je veux un kanban visuel"

→ **Backlog.md** (`backlog board` TUI ou `backlog browser` web)

Le seul du panel à offrir un kanban TUI + Web propre. Tasks.md fait du kanban Web mais sans CLI.

### 7.6 "Je veux que mes tâches voyagent avec mon code"

→ **Backlog.md** (dossier `backlog/` dans le repo de code, sync git automatique)
→ **GitHub Issues** (pas de dossier mais tied au repo)
→ **git-bug** (refs git, pas de fichier dans le worktree)

Backlog.md est le plus orthogonal et le plus lisible (les `.md` sont des fichiers normaux, visibles dans GitHub UI aussi).

---

## 8. Combinaison avec mdscan

mdscan évolue en v0.4 vers une approche "checkboxes GFM avec metadata inline" pour ses tâches item-level (cf. [kb-task-hybrid-research.md](kb-task-hybrid-research.md)). Cette philosophie est compatible avec **plusieurs des outils ci-dessus**.

### 8.1 mdscan + dstask

**Complémentarité naturelle**. dstask gère les tâches actionnables courtes (un repo git séparé `~/.dstask/`). mdscan scanne les notes Markdown longues (KB) et expose la knowledge base au format JSON.

Pont : un agent Claude Code peut faire `mdscan --json` pour trouver une doc, puis `dstask add "Read [doc-id]" project:reading` pour planifier la lecture. Ou inversement : `dstask 42 note` ouvre un Markdown qui peut être un lien vers une note du KB scanné par mdscan.

Pas de couplage, juste un workflow parallèle. C'est probablement la combinaison la plus simple et la plus durable.

### 8.2 mdscan + Backlog.md

**Recouvrement partiel**. Backlog.md gère un `backlog/` plein de `.md` task files. mdscan scanne les `docs/` de la KB.

Si on étend mdscan v0.4 pour parser les checkboxes GFM dans les corps de fichiers (comme spécifié dans kb-task-hybrid-research.md), on tombe sur la même surface que Backlog.md pour les tâches item-level dans la doc — sans toutefois le Kanban TUI ni le MCP.

Possible workflow : Backlog.md pour les "issues" de projet (tâches file-level, dossier `backlog/`), mdscan pour les checkboxes inline dans le KB (`docs/roadmap.md` avec sa liste de TODOs). Les deux outils respectent le même format Markdown sous-jacent.

### 8.3 mdscan + todo.txt

**Faible couplage utile**. todo.txt pour les tâches actionnables one-liner, mdscan pour la KB documentée. Un agent peut générer une todo.txt depuis les checkboxes GFM scannées par mdscan (`mdscan tasks --json | jq -r ... > todo.txt`). Round-trip simple.

### 8.4 mdscan + GitHub Issues

mdscan v0.4 pourrait gagner une commande `mdscan tasks --sync-github` qui :
1. Parse les `- [ ] foo` du corpus,
2. Crée des GitHub Issues correspondantes via `gh issue create`,
3. Stocke le mapping `task-line:issue-number` dans `.mdscan/state.json`,
4. Permet de fermer une checkbox local → ferme l'issue, et inversement.

Bridge intéressant, **à reporter en v0.5 ou v0.6** (cf. spec-v0.4 §"deferred").

### 8.5 mdscan + Org-mode

Format Org est trop éloigné de Markdown — mdscan reste Markdown-first (cf. spec-v0.4). Pas de synergie directe envisagée. Si l'utilisateur va Org, il abandonne probablement mdscan en pratique (Org Agenda fait déjà tout).

### 8.6 Renvoi à la doc soeur

Pour la philosophie générale "mdscan comme couche KB en complément d'un task manager texte", se reporter à [mdscan-taskwarrior-synergy.md](mdscan-taskwarrior-synergy.md). Les principes y exposés s'appliquent à dstask, Backlog.md, todo.txt avec très peu d'adaptations.

---

## 9. Verdict final

Pour le profil cible — **médecin (médecine nucléaire) + dev side-projects, multi-machines perso/pro, workflow agent-first Claude Code, allergie au SQLite caché** :

### Recommandation primaire : **dstask**

**Pourquoi** :
- C1 (texte plat) : ✓ YAML par tâche, lisible humainement, diff git propre.
- C2 (sync git native) : ✓ `dstask sync` = git pull/push. Pas de serveur.
- C3 (CLI-first) : ✓ pure CLI, single binary statique Go.
- C4 (agent-friendly) : ✓ struct Go avec tags JSON, plus accès filesystem direct aux YAML.
- C5 (modèle riche) : ✓ priorités P0-P3, due dates, projets, contextes, états, notes Markdown par tâche, dépendances.
- C6 (multi-device sans serveur) : ✓ git remote suffit.
- C7 (maintenu) : ✓ v1.0.1 en janvier 2026, "feature complete" = stable.

**Configuration recommandée** :
- Un repo git privé `~/.dstask-perso/` (tâches vie perso + médecine, non confidentielles).
- Pour les tâches confidentielles (patients) : repo git local **non synchronisé** ou chiffré (git-crypt si vraiment besoin de sync chiffrée).

### Recommandation secondaire : **Backlog.md** pour les side-projects dev

Quand un projet dev gagne en complexité (>20 tâches), basculer ce projet sur Backlog.md (dossier `backlog/` dans le repo de code). Bénéfices :
- Kanban TUI / Web pour visualisation,
- MCP pour Claude Code (intégration native),
- Tâches versionnées avec le code dans le PR,
- Acceptance criteria first-class.

Workflow : `dstask` pour la vie globale (haut niveau, GTD personnel), `Backlog.md` pour les projets dev structurés.

### Recommandation complémentaire : **GitHub Issues via `gh`** pour les repos open source

Si l'utilisateur publie des projets open source ou collabore en équipe sur un repo public, **utiliser les issues GitHub natives** est plus simple que de maintenir un autre système. La CLI `gh --json` est excellente pour les agents.

### Ce qu'on n'adopte PAS

- **Taskwarrior 3+** : SQLite, sync via démon dédié. Trop de frottement.
- **TaskLite** : SQLite aussi, même problème.
- **Org-mode** : trop d'investissement Emacs pour le profil.
- **Logseq v2** : transition SQLite incertaine.
- **GUI-only outils** (Tasks.md, SilverBullet pour le primaire) : pas agent-first.
- **Outils morts** : taskbook, Dendron.

### Plan d'action concret

1. **Cette semaine** : installer dstask (`brew install dstask` ou téléchargement binaire), initialiser le repo `~/.dstask/`, créer 5-10 tâches test, lancer `dstask sync` vers un repo privé GitHub. Vérifier le workflow sur 3-4 jours.
2. **Semaine 2** : sur un side-project dev en cours, tester Backlog.md (`bunx backlog init`). Activer le MCP avec Claude Code, voir si l'ergonomie tient la promesse.
3. **Mois 1** : décider de la frontière dstask ↔ Backlog.md (vie perso ↔ projets structurés) et stabiliser le workflow.
4. **Mois 3** : évaluer si mdscan v0.4 (tâches item-level via checkboxes GFM) est complémentaire ou redondant avec les choix précédents.

---

## Sources

### Outils principaux

- [dstask — GitHub](https://github.com/naggie/dstask)
- [dstask — Database format](https://github.com/naggie/dstask/blob/master/etc/DATABASE_FORMAT.md)
- [Backlog.md — GitHub](https://github.com/MrLesk/Backlog.md)
- [Backlog.md — site / HT-X review](https://ht-x.com/en/posts/2025/09/backlog-md-markdown-native-task-manager-and-kanban/)
- [Backlog.md — HN discussion](https://news.ycombinator.com/item?id=44483530)
- [TaskLite — site](https://tasklite.org/)
- [TaskLite — GitHub](https://github.com/ad-si/TaskLite)
- [taskbook (klaudiosinani) — GitHub](https://github.com/klaudiosinani/taskbook)
- [todo.txt-cli — GitHub](https://github.com/todotxt/todo.txt-cli)
- [todo.txt spec — todo.txt repo](https://github.com/todotxt/todo.txt)
- [todo.txt Add-on Directory (git addon)](https://github.com/todotxt/todo.txt-cli/wiki/Todo.sh-Add-on-Directory)
- [topydo — GitHub](https://github.com/topydo/topydo)
- [git-bug — GitHub](https://github.com/git-bug/git-bug)
- [Tasks.md (BaldissaraMatheus) — GitHub](https://github.com/BaldissaraMatheus/Tasks.md)
- [Org-mode — orgmode.org](https://orgmode.org/)
- [organice — GitHub](https://github.com/200ok-ch/organice)
- [nvim-orgmode — GitHub](https://github.com/nvim-orgmode/orgmode)
- [Orgzly — site](http://www.orgzly.com/)
- [Logseq — site](https://logseq.com/)
- [Logseq — discussion git sync 2025](https://discuss.logseq.com/t/discussion-is-git-the-only-truly-reliable-self-hosted-sync-for-multiple-devices-in-2025/33502)
- [SilverBullet — site](https://silverbullet.md/)
- [SilverBullet — GitHub](https://github.com/silverbulletmd/silverbullet)
- [SilverBullet — task management workflows](https://community.silverbullet.md/t/task-management-workflows/3343)
- [Foam — GitHub](https://github.com/foambubble/foam)
- [Dendron — GitHub (archived)](https://github.com/dendronhq/dendron)
- [jrnl — GitHub](https://github.com/jrnl-org/jrnl)
- [markwhen — GitHub](https://github.com/mark-when/markwhen)

### GitHub Issues / gh CLI

- [GitHub CLI manual](https://cli.github.com/manual/)
- [gh issue command reference](https://cli.github.com/manual/gh_issue)
- [GitHub Projects v2 docs](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
- [GitHub Tasks Output Style for Claude Code (gist)](https://gist.github.com/johnlindquist/333aae98681b7cb7d6137abf72a2a218)

### Articles et retours d'expérience

- [Cal Bryant — dstask, a terminal based git powered task manager](https://calbryant.uk/blog/dstask-a-terminal-based-git-powered-task-manager/)
- [Pankaj Pipada — Streamlined Markdown/Git-Based Task Management System for Solo Developers](https://pankajpipada.com/posts/2024-08-13-taskmgmt-2/)
- [Markdown Task Manager (ioniks) — GitHub](https://github.com/ioniks/MarkdownTaskManager)
- [BrightCoding — git-bug](https://www.blog.brightcoding.dev/2025/06/01/git-bug-a-distributed-offline-first-bug-tracker-embedded-in-git/)
- [David P. Adams — Keeping a Local, Searchable Journal with jrnl, Syncthing, and Obsidian](https://dadams.io/technology/journaling/productivity/2025/06/26/journaling/)

### Documents internes

- [spec-v0.4.md](spec-v0.4.md) — Spécification mdscan v0.4
- [pkm-for-agents.md](pkm-for-agents.md) — PKM pour agents (recherche)
- [kb-task-hybrid-research.md](kb-task-hybrid-research.md) — Réconciliation knowledge + tasks
- [mdscan-taskwarrior-synergy.md](mdscan-taskwarrior-synergy.md) — Doc soeur sur la synergie mdscan ↔ TW (en cours)

---

## Annexe : vérification mdscan

À exécuter depuis `/home/thenry/Projects/mdscan/` :

```bash
$ uv run mdscan scan docs/
hint: run 'mdscan check-links' to verify link reachability
cli-audit.md                        Audit of mdscan CLI against clig.dev and agent-focused CLI design principles.
git-text-task-managers.md           Recensement des alternatives à Taskwarrior offrant stockage texte plat et synchronisation git, comparées sur leurs forces, limites et compatibilité agent.
kb-task-hybrid-research.md          Reconciles mdscan's dual mandate as knowledge base + task tracker by separating doc-kind (content shape) from item-level tasks (GFM checkboxes with inline metadata), surveys hybrid plaintext PKM/PM tools, and proposes a concrete kind enum, syntax, and command surface.
knowledge-organisation-research.md  Web-researched survey of knowledge-organisation methodologies (Diataxis, Zettelkasten, PARA, LATCH, ADRs, GitLab CTRT, etc.) used to validate and refine mdscan's `kind` frontmatter enum, with an opinionated recommendation.
mdscan-taskwarrior-synergy.md       Etude du couplage mdscan + Taskwarrior comme architecture bicéphale connaissance/tâches, avec trois cas d'usage concrets (dev mdscan, literature review TEP FES, vie perso) et implications pour la spec v0.4/v0.5.
obsidian-query-survey.md            Deep survey of Obsidian's query surfaces (Search, Dataview DQL, Dataview JS, Bases) with side-by-side use-case examples and concrete mdscan CLI adaptations.
pkm-for-agents.md                   Analysis of Obsidian PKM features translated into agent-facing primitives for an AI-native knowledge system built on top of mdscan.
plan-cli-v0.3.md                    Implementation plan for mdscan v0.3 CLI improvements based on clig.dev and agent CLI audit.
plan-v0.2.md                        Implementation plan for mdscan v0.2 features (config, tree, coverage, all-links).
spec-v0.4.md                        Living specification for mdscan v0.4 — evolution toward "madge for markdown" with minimal frontmatter, graph primitives, and standalone CLI design. Updated as decisions are taken in discussion.
```

Le document `git-text-task-managers.md` est correctement scanné et sa description est exposée par `mdscan scan` — donc lisible par un agent à coût L1 minimal (cf. spec-v0.4 §"Progressive disclosure layers").
