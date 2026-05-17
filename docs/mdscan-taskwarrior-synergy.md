---
description: Etude du couplage mdscan + Taskwarrior comme architecture bicéphale connaissance/tâches, avec trois cas d'usage concrets (dev mdscan, literature review TEP FES, vie perso) et implications pour la spec v0.4/v0.5.
---

# mdscan + Taskwarrior — l'architecture bicéphale

> **Statut** : recherche de design. Explore l'hypothèse "et si on laissait Taskwarrior gérer les tâches plutôt que de réinventer une couche tasks dans mdscan ?" — en complément/contraste avec [kb-task-hybrid-research.md](kb-task-hybrid-research.md).

## TL;DR

- **Hypothèse centrale** : mdscan reste un outil de **discovery sur corpus Markdown** (frontmatter, liens, graphe). Taskwarrior reste un outil de **gestion de tâches** (état, urgence, échéances, récurrences). Les deux se rencontrent à un seul endroit : **un lien explicite** (UUID Taskwarrior dans le frontmatter d'une note, lien Markdown dans l'annotation d'une tâche).
- **Découpage de responsabilité** : une **tâche** a un état (pending/done/waiting), un cycle de vie court, un urgency score, une date. Une **note** a un contenu, une description, des liens entrants/sortants, une durée de vie longue. Ne pas mélanger.
- **Pont** : une convention frontmatter `tasks: [uuid1, uuid2]` (ou un dossier `notes/` adressé par UUID), plus `task annotate <uuid> "note:docs/papers/liu-2024.md"` côté Taskwarrior. mdscan apprend à **résoudre** ce lien (commande `mdscan tasks` qui dépile l'export JSON Taskwarrior et l'agrège par note/tag/projet).
- **Trois cas d'usage** détaillés dans le doc : (1) auto-meta — reconstruire mdscan from scratch ; (2) literature review TEP FES dans le cancer du sein lobulaire ; (3) vie perso (impôts, nounou, courses).
- **Limites honnêtes** : Taskwarrior 3 stocke en SQLite (depuis 2024), donc plus aussi "plain text" qu'avant — le diff git est mort. La synchronisation passe par Taskchampion. L'agent IA doit invoquer `task export` pour lire l'état des tâches. Frictions documentées en §9.

Le pari de fond : **deux outils petits, focalisés, qui se parlent par un protocole minimal (JSON export + UUID en frontmatter)** battent **un outil monolithique qui ferait les deux moyennement**. C'est exactement la philosophie Unix que mdscan v0.4 revendique déjà ([spec-v0.4.md](spec-v0.4.md)).

---

## 1. Pourquoi se poser la question

[kb-task-hybrid-research.md](kb-task-hybrid-research.md) a tranché : les tâches mdscan vivront comme **GFM checkboxes au niveau item** (`- [ ] foo @owner due:2026-05-20 !high`), dans le corps des `.md`. C'est la voie "Org-mode-shaped" : tout dans le même corpus plain text.

Cette voie a un coût caché : **mdscan se met à faire le boulot d'un task manager**. Commandes `mdscan tasks`, `mdscan agenda`, `mdscan board`, `mdscan task add|done|cancel`. Chaque commande est légitime, mais cumulées elles font de mdscan une réimplémentation partielle de Taskwarrior — sans les 15 ans de raffinement de l'urgency, des récurrences, des dépendances, des hooks, des contextes, de la synchronisation chiffrée, etc.

L'alternative : **garder mdscan dans son couloir (graphe Markdown headless) et laisser Taskwarrior faire son boulot**. Le présent document explore cette alternative à fond, sur trois cas d'usage représentatifs.

Ce n'est **pas** une critique de la proposition hybride (item-level checkboxes). C'est l'exploration d'un autre point dans l'espace de design. Les deux approches sont défendables ; ce doc fournit les éléments pour trancher.

---

## 2. Taskwarrior à fond — modèle, syntaxe, points d'extension

### 2.1 Le modèle de données

Une tâche Taskwarrior est un **document JSON** stocké (depuis v3, début 2024) dans une base SQLite locale (`~/.task/taskchampion.sqlite3`). Les attributs principaux :

| Attribut | Type | Rôle |
|---|---|---|
| `uuid` | UUID v4 | Identifiant permanent, immuable. La clé universelle. |
| `id` | int | Numéro de ligne dans le working set (pending). Volatile — change à chaque rebuild. |
| `description` | string | Une ligne. Le résumé. |
| `status` | enum | `pending` / `completed` / `deleted` / `waiting` / `recurring` |
| `project` | string | Hiérarchique par dot-notation : `medecine.literature.tep-fes`. |
| `tags` | list[string] | Free-form. Convention GTD : `+@phone`, `+@drive`, `+next`, `+waiting`. |
| `priority` | enum | `H` / `M` / `L` (rarement utilisé par les utilisateurs expérimentés). |
| `entry` | timestamp | Date de création. Auto. |
| `modified` | timestamp | Date dernière modification. Auto. |
| `due` | timestamp | Échéance dure. |
| `scheduled` | timestamp | Date à partir de laquelle la tâche entre dans `next`. |
| `wait` | timestamp | Date avant laquelle la tâche est masquée. |
| `start` | timestamp | Tâche active (entre `task start` et `task stop`). |
| `end` | timestamp | Date de complétion ou suppression. |
| `until` | timestamp | Date butoir (au-delà, la tâche est supprimée). |
| `depends` | list[uuid] | Dépendances (tâches qui bloquent). Donne +8.0 à l'urgency du bloquant, -5.0 au bloqué. |
| `recur` | duration | Période de récurrence : `weekly`, `monthly`, `3wks`, `1y`. |
| `annotations` | list[{entry, description}] | **Le slot Markdown-friendly**. Multi-ligne, timestampé. |
| `urgency` | float | Calculé, jamais stocké. Polynôme sur les attributs. |
| `uda.<name>` | typé | User Defined Attributes — `string`, `numeric`, `date`, `duration`. |

L'**urgency** est un polynôme à coefficients configurables ([doc officielle](https://taskwarrior.org/docs/urgency/)). Les plus gros poids par défaut :

- `+next` tag : **+15.0** (le booster manuel)
- `due` (proche / dépassée) : **+12.0**
- Bloque d'autres tâches : **+8.0**
- Priorité H : **+6.0**
- `scheduled` atteinte : **+5.0**
- `start` (active) : **+4.0**
- Tags / annotations / project : **+1.0** chacun
- `waiting` : **-3.0**
- Bloquée par dépendance : **-5.0**

Le but : `task next` (le rapport par défaut) trie par urgency décroissant — pas besoin de bricoler des filtres, le système propose toujours "ce qui devrait être travaillé maintenant". C'est la **killer feature** que mdscan ne peut pas reproduire en quelques mois.

### 2.2 La syntaxe CLI

```bash
# Créer
task add "Lire Liu 2024 FES vs FDG" project:medecine.literature.tep-fes +reading due:2026-05-20

# Lister
task                            # working set (pending)
task next                       # top par urgency
task project:medecine.literature # filtre projet (préfixe accepté)
task +reading and due.before:2026-06-01
task long                       # rapport verbeux (entry, modified, etc.)

# Modifier
task 42 modify +urgent due:tomorrow priority:H
task 42 annotate "Voir aussi docs/papers/ulaner-2023.md"
task 42 start
task 42 done

# Récurrence
task add "Payer la nounou" due:eom recur:monthly project:perso.admin

# Dépendances
task add "Soumettre review" depends:42,43 project:medecine.literature.tep-fes

# Contextes (filtre nommé, persistant)
task context define perso project:perso
task context perso              # active
task context none               # désactive

# Export
task export                                    # tout en JSON
task export project:medecine.literature       # filtré
task project:medecine export                  # idem (filtre avant le verbe)
```

Détail crucial : **toutes les commandes acceptent un filtre en préfixe**. `task +reading list` = liste les tâches avec tag `reading`. `task project:perso done` (avec un id) marque toutes les tâches du projet comme done. C'est puissant et **scriptable**.

### 2.3 Les hooks — le vrai point d'extension

Quatre événements ([doc hooks](https://taskwarrior.org/docs/hooks/)) :

| Hook | stdin | stdout | Sémantique |
|---|---|---|---|
| `on-launch` | rien | feedback optionnel | Avant toute commande. Peut tout bloquer (exit ≠ 0). |
| `on-add` | 1 ligne JSON (nouvelle tâche) | JSON modifié + feedback | Avant écriture en base. Peut rejeter ou enrichir. |
| `on-modify` | 2 lignes JSON (avant, après) | JSON modifié + feedback | Sur tout `modify`/`done`/`start`/etc. |
| `on-exit` | n lignes JSON (toutes les modifs de la session) | feedback uniquement | Après écriture. **Le bon endroit pour synchroniser un état externe** (Markdown, git, etc.). |

Les hooks vivent dans `~/.task/hooks/`, sont exécutables (`chmod +x`), suivent la convention de nom `<event>[.<ordering>]` : `on-add.01-tag-default`, `on-add.02-link-note`, etc. Exit 0 = OK, exit ≠ 0 = rejet (et le feedback devient un message d'erreur).

**Implication concrète pour mdscan** : un hook `on-add` peut **créer automatiquement une note Markdown** dans `docs/tasks/<uuid>.md` avec un frontmatter pré-rempli, et stamper l'UUID en annotation. Un hook `on-modify` peut mettre à jour `last_updated`. Un hook `on-exit` peut régénérer un index `docs/_tasks-index.md` listant les tâches courantes. C'est exactement le pont qu'on cherche.

### 2.4 Les User Defined Attributes (UDAs)

Déclarés dans `~/.taskrc` :

```ini
uda.note.type=string
uda.note.label=Note
uda.doi.type=string
uda.doi.label=DOI
uda.estimate.type=numeric
uda.estimate.label=Est
```

Une fois déclaré, `task add "Lire Liu 2024" doi:10.1007/s11307-025-02015-2 note:docs/papers/liu-2024.md` stocke et indexe ces champs. Ils sont exportés en JSON, filtrables (`task doi.any:`, `task note.is:docs/papers/liu-2024.md`).

Pour notre architecture : **un UDA `note` de type string contenant le chemin Markdown** est le pont minimal côté Taskwarrior. Trois caractères de configuration, et chaque tâche peut pointer une note.

### 2.5 Le format JSON d'export

```json
{
  "id": 42,
  "uuid": "8a3e1c4b-...",
  "description": "Lire Liu 2024 FES vs FDG",
  "status": "pending",
  "project": "medecine.literature.tep-fes",
  "tags": ["reading", "@desk"],
  "entry": "20260514T103000Z",
  "modified": "20260514T103000Z",
  "due": "20260520T000000Z",
  "urgency": 8.2,
  "note": "docs/papers/liu-2024.md",
  "annotations": [
    {"entry": "20260514T104500Z", "description": "Voir aussi Ulaner 2023"}
  ]
}
```

Une ligne par tâche, JSON pur. `task export | jq` fonctionne immédiatement. C'est la **surface API** sur laquelle on construit l'intégration mdscan.

### 2.6 Taskwarrior 3 — le passage à SQLite

Depuis avril 2024, Taskwarrior 3 stocke en SQLite local (TaskChampion) au lieu du fichier `pending.data` / `completed.data` en texte. Conséquences :

- **Plus de diff git lisible** sur la base : c'est un blob binaire.
- **Sync chiffrée** via Taskchampion-sync-server ou GCS/AWS — pas via git.
- **Mais** : `task export > tasks.json` reste plain text, commitable, et **le format d'échange canonique** (la base SQLite reste un cache local).

Pour notre couplage : on s'appuie **uniquement sur `task export` / `task import`**, pas sur le fichier base. Cela rend l'intégration robuste à toute évolution du backend (et préserve la portabilité git via export).

---

## 3. Le découpage de responsabilités

### 3.1 La règle du clivage

Question : **est-ce que c'est une connaissance ou un état actionnable ?**

- A un cycle de vie de quelques jours/semaines, change d'état (open → doing → done), a une échéance → **Taskwarrior**
- A un contenu (idée, référence, draft, décision, runbook), survit dans le corpus, est cité par d'autres docs → **Markdown + mdscan**

Cas-tests pour calibrer l'intuition :

| Item | Verdict | Pourquoi |
|---|---|---|
| "Lire Liu 2024" | Tâche | A un état (pas lu / en cours / lu) et finira |
| Notes de lecture de Liu 2024 | Note `.md` | Contenu durable, citable, structurable |
| "Décider du stockage des tokens OAuth" | Tâche | Décision en attente, finira |
| ADR-007 (décision actée sur OAuth) | Note `.md` | Trace permanente |
| "Payer la nounou en mai" | Tâche récurrente | Action mensuelle, status |
| "Liste mensuelle des nounous candidates" | Note `.md` | Référence consultée |
| Checklist impôts | Note `.md` | Référence + checkboxes éventuelles (sub-tasks) |
| "Préparer la déclaration d'impôts 2026" | Tâche annuelle | Bornée, due au 15 mai |
| Idée d'un nouveau papier | Note `.md` *ou* tâche `+someday` | Cf. §3.5 |
| Roadmap v0.4 | Note `.md` (`kind: reference`) | Document structurant, vivant |
| Items individuels de la roadmap | Tâches Taskwarrior, `project:mdscan.v0.4` | Chacun finira |

Le piège classique : **mélanger les deux dans un même fichier**. Une roadmap Markdown qui contient `- [ ] foo` avec date/owner inline finit par dériver — soit la roadmap devient un task tracker bricolé, soit les checkboxes deviennent du contenu mort que personne ne met à jour. Le clivage tranche : la roadmap **mentionne** des tâches, mais leur état vit dans Taskwarrior, accédé par UUID.

### 3.2 Trois patterns de liaison

#### Pattern A — UUID dans le frontmatter (note → tâche)

```yaml
---
description: Notes de lecture de Liu et al. 2024 (FES-PET vs FDG-PET dans ILC métastatique).
kind: reference
tags: [tep-fes, lobulaire, literature]
last_updated: 2026-05-14
tasks: [8a3e1c4b-..., f1d2e7a0-...]
---
```

La note **déclare** les tâches associées (lire, synthétiser, citer dans intro). mdscan peut suivre ces UUIDs et joindre l'état Taskwarrior via `task export`.

**Avantages** : explicite, agent-readable, agent peut savoir "quelles tâches concernent ce papier ?".
**Inconvénients** : nouveau champ frontmatter ; risque de désync (tâche supprimée → UUID orphelin) ; ajout au schema v0.4.

#### Pattern B — Chemin Markdown dans une annotation Taskwarrior (tâche → note)

```bash
task add "Lire Liu 2024 FES vs FDG" project:medecine.literature.tep-fes +reading
task 42 annotate "note:docs/papers/liu-2024.md"
```

ou via UDA `note` :

```bash
task add "Lire Liu 2024 FES vs FDG" \
  project:medecine.literature.tep-fes +reading \
  note:docs/papers/liu-2024.md
```

La tâche **pointe** la note. mdscan n'a rien à savoir ; un `task export` suffit à un agent pour parcourir les notes liées.

**Avantages** : zéro impact sur le schema frontmatter ; cohérent avec la conv. Taskwarrior (UDA + annotations) ; bidirectionnel facile.
**Inconvénients** : annotation est multi-ligne et désordonnée ; UDA `note` plus propre mais nouveau ; mdscan doit lire `task export` pour découvrir le lien — il n'a pas la connaissance localement.

#### Pattern C — Convention de chemin (UUID-as-filename)

```
docs/tasks/8a3e1c4b-...-md
```

Chaque tâche qui mérite une note de contexte a une note dont le nom **est** son UUID. Un hook `on-add` crée le fichier vide avec frontmatter pré-rempli.

**Avantages** : pas de champ frontmatter, pas de convention manuelle, déterministe.
**Inconvénients** : noms de fichiers illisibles ; ne convient pas aux notes thématiques transverses (un papier scientifique a une "vie" propre, plusieurs tâches en parlent — UUID-as-filename force 1:1).

#### Recommandation

**Pattern B en priorité** (UDA `note` sur la tâche), **Pattern A en complément** pour les cas N:M (une note pointe plusieurs tâches). Ne pas adopter Pattern C — viole le principe "le nom de fichier doit être humainement parlant".

Concrètement, ça veut dire :

- Le frontmatter mdscan **reste à 4 champs** (cf. spec v0.4) — sauf si l'usage prouve qu'on a besoin du Pattern A à grande échelle, auquel cas on ajoute un champ optionnel `tasks: [UUID, ...]`.
- Côté Taskwarrior, on ajoute un seul UDA :
  ```ini
  uda.note.type=string
  uda.note.label=Note
  ```
- mdscan apprend (v0.5) une commande `mdscan tasks` qui `task export | jq` et agrège par `project:` / `note:`.

### 3.3 Le rôle de mdscan dans cet écosystème

mdscan **ne devient pas un task manager**. Il garde son couloir : graphe Markdown headless. Il **gagne** une commande de discovery cross-outil :

```bash
mdscan tasks                                # toutes tâches pending, regroupées par note pointée
mdscan tasks --for docs/papers/liu-2024.md  # tâches pointant cette note
mdscan tasks --project medecine.literature  # tâches d'un projet TW + notes associées
```

Implémentation triviale : sub-process `task export <filter>`, parser le JSON, joindre avec `mdscan --json`. Pas de DSL, pas de stockage, pas de récriture. Du **glue code** au sens Unix.

### 3.4 Quand utiliser quel outil — décision à 3 questions

```
1. Est-ce que ça va FINIR (a une date de fin, un état done) ?
   → Oui : Taskwarrior
   → Non : suite

2. Est-ce que ça a du CONTENU (au-delà d'une description d'une ligne) ?
   → Oui : Markdown
   → Non : Taskwarrior (description suffit, optional annotations)

3. Est-ce qu'il sera CITÉ / RÉFÉRENCÉ par d'autres choses durables ?
   → Oui : Markdown (pour bénéficier des backlinks mdscan)
   → Non : Taskwarrior si ça finit, Markdown sinon
```

Les zones grises :

- **Décision en cours** (RFC, ADR-draft) : Markdown (`kind: decision`), avec une tâche Taskwarrior "Trancher l'ADR sur X" qui pointe le doc.
- **Idée à creuser** : si éphémère → tâche `+someday`. Si l'idée mérite quelques paragraphes → note Markdown `kind: explanation`.
- **Checklist** : si standalone (impôts) → note Markdown avec checkboxes Markdown ; si éclatée dans le temps → tâches Taskwarrior groupées par projet.

### 3.5 Quid des checkboxes Markdown alors ?

[kb-task-hybrid-research.md](kb-task-hybrid-research.md) propose un syntax `- [ ] @owner due:` parsé par mdscan. Dans l'architecture bicéphale, on n'en a **plus besoin pour le tracking** — mais ils restent utiles comme **outline d'une checklist statique** dans un document (par exemple checklist impôts), parce qu'ils rendent visuellement bien en GFM.

Position recommandée :

- **Checkboxes Markdown standard** (`- [ ]` / `- [x]`) : utilisables librement, mdscan les ignore (ni indexation ni état). Elles servent de listing visuel, pas de tracking.
- **Tâches actionnables** : Taskwarrior. Chaque ligne `task add ...` au lieu de chaque ligne `- [ ]`.
- **Pas de syntaxe étendue** `[/]`, `[?]` etc. dans mdscan, **pas de parseur dédié**. La complexité reste dans Taskwarrior, qui sait déjà gérer 5 statuts depuis 15 ans.

Conséquence : la proposition §5 du [kb-task-hybrid-research](kb-task-hybrid-research.md) (5 commandes `mdscan tasks/agenda/board/task add/task done`) **disparaît**. Elle est remplacée par **une** commande de discovery `mdscan tasks` qui interroge Taskwarrior, et zéro commande d'écriture (Taskwarrior fait ça mieux).

---

## 4. Cas 1 — Redémarrer mdscan from scratch

Hypothèse : on est à J0 du projet mdscan, on a Taskwarrior installé et mdscan v0.3 en outil compagnon (oui, c'est récursif).

### 4.1 Setup initial

```bash
# ~/.taskrc — bootstrap
task config uda.note.type string
task config uda.note.label Note

# Contexte projet
task context define mdscan project:mdscan
task context mdscan

# Tags conventionnels
# +bug +feature +refacto +docs +next +waiting
# Contextes GTD : +@desk +@deep (focus profond) +@quick (10min)
```

`pyproject.toml` :

```toml
[tool.mdscan]
ignore = ["target/", ".venv/", "build/"]
entrypoint = "CLAUDE.md"

[tool.mdscan.schema]
kinds = ["reference", "guide", "explanation", "decision"]
```

### 4.2 Structure `docs/` initiale

```
mdscan/
├── CLAUDE.md                          # entrypoint agent (kind: reference)
├── README.md                          # entrypoint humain (kind: reference)
├── docs/
│   ├── adr/
│   │   ├── 001-headless.md            # kind: decision
│   │   ├── 002-frontmatter-schema.md  # kind: decision
│   │   └── 003-no-query-dsl.md        # kind: decision
│   ├── design/
│   │   ├── architecture.md            # kind: reference
│   │   └── graph-model.md             # kind: explanation
│   ├── plans/
│   │   ├── roadmap.md                 # kind: reference (mention de tâches Taskwarrior)
│   │   └── milestones.md              # kind: reference
│   ├── guides/
│   │   ├── dev-setup.md               # kind: guide
│   │   └── release-process.md         # kind: guide
│   └── research/
│       ├── pkm-for-agents.md          # kind: explanation
│       └── obsidian-query-survey.md   # kind: explanation
└── src/, tests/, pyproject.toml, ...
```

### 4.3 Capture d'idées — l'inbox

GTD-style. On a une "inbox" Taskwarrior. Pendant une session de travail, on capture sans triager :

```bash
task add +in "Faut un mdscan backlinks JSON"
task add +in "Le check-links rate les liens dans les blocs de code"
task add +in "Ajouter un favicon"  # contre-exemple — sera trié à la sortie
task add +in "Idée : mdscan touch après chaque Edit"
```

Le tag `+in` (inbox) est la convention GTD. À la fin de la journée :

```bash
task +in list
```

Pour chaque item, on décide :

1. **Actionnable et < 2min** : on le fait, `task <id> done`.
2. **Actionnable et plus long** : on triage — projet, tags, due, priority — puis on retire `+in`.
3. **Pas actionnable, mais utile** : devient une note `.md`.
4. **Inutile** : `task <id> delete`.

Exemple de processing :

```bash
# 1: backlinks JSON → c'est une feature, projet mdscan.v0.4, milestone Phase 2
task 1 modify project:mdscan.v0.4.backlinks +feature -in
task 1 annotate "Voir docs/plans/roadmap.md#phase-2"

# 2: check-links bug → projet mdscan.bugs, +bug, priorité H car bloque users
task 2 modify project:mdscan.bugs +bug priority:H -in

# 3: favicon → delete (out of scope CLI tool)
task 3 delete

# 4: mdscan touch → c'est une décision design ouverte, devient note
mdscan new docs/adr/004-touch-on-edit.md --kind decision \
  --description "Doit-on auto-toucher last_updated après chaque Edit ?"
task 4 modify -in project:mdscan.v0.4.design +decision-needed \
  note:docs/adr/004-touch-on-edit.md \
  description:"Trancher : auto-touch ou manuel sur Edit (cf. ADR-004)"
```

Le pattern clé : **la tâche pointe la note de contexte via `note:`**. L'agent qui voit la tâche peut récupérer la note. L'humain qui ouvre la note peut chercher les tâches associées via `task note:docs/adr/004-touch-on-edit.md`.

### 4.4 Découpage en projets Taskwarrior

Hiérarchie en dot-notation :

```
mdscan.v0.4.schema      # phase 1 spec v0.4
mdscan.v0.4.backlinks   # phase 2
mdscan.v0.4.discovery   # phase 2 — show/stale/tags
mdscan.v0.4.recipes     # phase 4 docs
mdscan.v0.5             # phase 5 (Claude integration)
mdscan.bugs             # tracker de bugs cross-version
mdscan.refacto          # refactoring opportunities
mdscan.docs             # documentation hors code
```

Un sub-project peut s'utiliser comme filtre : `task project:mdscan.v0.4` matche tout v0.4 et sous-projets.

### 4.5 Tracking des bugs, refactos, features

Pas de Jira. Une tâche Taskwarrior par item :

```bash
# Bug
task add "check-links rate les liens dans blocs ```" \
  project:mdscan.bugs +bug priority:H \
  due:2026-05-25 \
  note:docs/bugs/check-links-codeblocks.md
# Une note .md est créée si l'investigation est non triviale
# Sinon : pas de note, juste la tâche

# Feature
task add "Implémenter mdscan backlinks --json" \
  project:mdscan.v0.4.backlinks +feature \
  depends:42 \  # 42 = "Trancher format JSON backlinks" (ADR)
  note:docs/design/backlinks.md

# Refacto
task add "Extraire le parser frontmatter dans un module dédié" \
  project:mdscan.refacto +refacto \
  scheduled:2026-06-01  # pas avant juin
```

Vue par projet :

```bash
task project:mdscan.v0.4.backlinks
# ID Pro                              Tags         Due        Urg
# 87 mdscan.v0.4.backlinks  Implémenter --json     feature    2026-05-25  8.2
# 88 mdscan.v0.4.backlinks  Tests sur ref-links    feature                3.1
# ...
```

### 4.6 Lier une décision architecturale à la tâche qui l'implémente

ADR `docs/adr/003-no-query-dsl.md` :

```markdown
---
description: Décision — pas de DSL de query dans mdscan ; on s'appuie sur jq pour les filtres.
kind: decision
tags: [adr, cli, design]
last_updated: 2026-05-10
---

# ADR-003 : pas de DSL de query

## Contexte
[...]

## Décision
On émet JSON et on s'appuie sur jq.

## Conséquences
- Phase 2 de v0.4 supprime la commande `mdscan query` (cf. tâches associées).
- Les recettes doivent être documentées (cf. tâches associées).

## Tâches associées
Côté Taskwarrior : `task project:mdscan.v0.4 note:docs/adr/003-no-query-dsl.md`
```

Côté tâches :

```bash
task add "Supprimer mdscan query du code" \
  project:mdscan.v0.4.discovery +refacto \
  note:docs/adr/003-no-query-dsl.md

task add "Écrire docs/recipes.md avec exemples jq" \
  project:mdscan.v0.4.recipes +docs \
  note:docs/adr/003-no-query-dsl.md \
  depends:123
```

Maintenant l'agent qui lit ADR-003 peut, en une commande, savoir où en est l'implémentation :

```bash
task note:docs/adr/003-no-query-dsl.md export | jq -r '.[] | "\(.status)\t\(.description)"'
# pending  Supprimer mdscan query du code
# pending  Écrire docs/recipes.md avec exemples jq
```

### 4.7 Comment Claude Code retrouve le contexte au début d'une session

Workflow type, à l'ouverture d'une nouvelle session :

```bash
# 1. L1 inventory — qu'est-ce qu'il existe ?
mdscan --json | jq '.[] | {path, description, kind}'

# 2. Quelles tâches sont actives sur mdscan ?
task context mdscan
task next limit:10

# 3. Quelle tâche je dois aborder maintenant ? (urgency max)
task +next                       # boost manuel
# ou simplement
task next limit:1

# 4. Cette tâche pointe-t-elle une note ?
task 87 export | jq -r '.[].note'
# docs/design/backlinks.md

# 5. Lire la note (L4)
mdscan show docs/design/backlinks.md

# 6. Lire les liens sortants de cette note (L1+L2 sur le voisinage)
mdscan --json | jq '.[] | select(.path=="docs/design/backlinks.md") | .links'
```

Six commandes, l'agent a localisé le travail prioritaire, le contexte documentaire, et les références transverses. **Aucun parsing custom**, **aucun DSL**, **aucun stockage propre à mdscan** — tout est `mdscan --json` + `task export` + `jq`.

### 4.8 Une journée type — transcript

```bash
# Matin — ouvre le shell, première chose : qu'est-ce qui urge ?
$ task next limit:5

ID Project              Description                              Tags          Due      Urg
87 mdscan.v0.4.backlin  Implémenter mdscan backlinks --json      +feature      5d       8.2
12 mdscan.bugs          check-links rate les liens dans blocs    +bug          7d       7.4
03 perso.admin          Régler facture EDF                       +@admin       3d       6.1
55 medecine.lit.tep-fes Lire Liu 2024 FES vs FDG                 +reading      10d      4.8
60 mdscan.refacto       Extraire parser frontmatter              +refacto                3.0

# Je décide de bosser 87. Je lance le timer.
$ task 87 start
Started 1 task.

# Je lis la note de contexte
$ mdscan show docs/design/backlinks.md

# Je commence à coder. Découvre un sous-problème : faut décider du format des ref-style
# Je capture sans triager :
$ task add +in "Format JSON pour ref-style links — array ou objet imbriqué ?"
Created task 91.

# Je continue. Je découvre que la libairie X gère ça mieux.
$ task add +in "Évaluer markdown-it-py pour parsing links"
Created task 92.

# Pause déj. Stop le timer.
$ task 87 stop

# Après-midi — reprise.
$ task 87 start

# Fini le gros morceau, commit, marque done.
$ task 87 done
Completed task 87 'Implémenter mdscan backlinks --json'.

# Triage inbox accumulée
$ task +in list
ID Description                                              Tags
91 Format JSON pour ref-style links — array ou objet imbri  in
92 Évaluer markdown-it-py pour parsing links                in

# 91 → décision, mérite ADR
$ mdscan new docs/adr/005-backlinks-json-shape.md \
    --kind decision \
    --description "Schema JSON des résultats de backlinks — array plat vs imbriqué."
$ task 91 modify -in project:mdscan.v0.4.backlinks +decision-needed \
    note:docs/adr/005-backlinks-json-shape.md \
    description:"Trancher ADR-005 (schema JSON backlinks)"

# 92 → spike technique
$ task 92 modify -in project:mdscan.v0.4.backlinks +spike scheduled:2026-05-20

# Fin de journée — review rapide
$ task end.after:today completed
ID UUID     Description                                              Done
87 8a3e1c4  Implémenter mdscan backlinks --json                      2026-05-14
```

C'est fluide. **Aucun outil de chat / TODO maintenu à la main**. Le système se reconstitue depuis `task export` et `mdscan --json`. Une autre session Claude demain peut reprendre à zéro sans contexte transmis manuellement.

### 4.9 Hook utile : auto-link note ↔ tâche

Hook `~/.task/hooks/on-add.10-mdscan-link`, en Python :

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""On-add hook: if a task has a `note:` UDA pointing to an existing .md file,
log a backlink confirmation. If the file doesn't exist, suggest `mdscan new`.
"""
import json
import os
import sys
from pathlib import Path

line = sys.stdin.readline()
task = json.loads(line)

note = task.get("note")
if note:
    path = Path(note)
    if path.exists():
        print(f"linked to existing note: {note}")
    else:
        print(f"note path does not exist: {note}")
        print(f"hint: run `mdscan new {note} --kind reference`")

print(json.dumps(task))
sys.exit(0)
```

Léger, optionnel, ne casse rien si le fichier n'existe pas. C'est le **niveau de couplage qu'on vise** : informatif, pas prescriptif.

---

## 5. Cas 2 — Literature review TEP FES dans le cancer du sein lobulaire

Sujet : la TEP au 18F-fluoroestradiol (FES-PET) cible les récepteurs aux œstrogènes. Particulièrement utile dans le carcinome lobulaire invasif (ILC), qui capte mal le FDG. Sujet chaud — les guidelines NCCN 2025 viennent de recommander FES-PET pour le staging des ILC métastatiques. Articles clés récents : Liu 2025 (Springer), Ulaner 2023 (AJR), umbrella review PMC 2025.

Objectif : structurer une literature review qui peut déboucher sur un papier de synthèse ou un chapitre de thèse.

### 5.1 Structure dossier

```
~/recherche/tep-fes-lobulaire/
├── CLAUDE.md                          # entrypoint agent
├── README.md                          # entrypoint humain
├── docs/
│   ├── _index.md                      # MOC manuel (kind: reference)
│   ├── papers/                        # une note par article (kind: reference)
│   │   ├── liu-2025-fes-fdg-ilc.md
│   │   ├── ulaner-2023-prospective.md
│   │   ├── nccn-2025-guidelines.md
│   │   └── ...
│   ├── concepts/                      # notes conceptuelles (kind: explanation)
│   │   ├── er-biology-ilc.md
│   │   ├── fes-radiopharm.md
│   │   └── fdg-pitfalls-lobular.md
│   ├── synthesis/                     # drafts en cours (kind: reference)
│   │   ├── intro-v1.md
│   │   ├── methods-comparison.md
│   │   └── outline.md
│   ├── meetings/                      # comptes-rendus (kind: decision)
│   │   ├── 2026-05-10-co-auteurs.md
│   │   └── ...
│   └── refs/                          # exports Zotero/PubMed (kind: reference)
│       └── search-strategy.md
└── manuscript/
    ├── tep-fes-review.md              # le draft du papier
    └── figures/
```

### 5.2 Frontmatter d'une note d'article

`docs/papers/liu-2025-fes-fdg-ilc.md` :

```yaml
---
description: Liu et al. 2025 — FES-PET et FDG-PET pour la gestion thérapeutique des ILC métastatiques ; 38 patients ; 82% des sites FDG vus en FES ; majorité high-FES/low-FDG.
kind: reference
tags: [paper, tep-fes, ilc, metastatic, retrospective]
last_updated: 2026-05-14
---

# Liu et al. 2025 — FES-PET dans la prise en charge des ILC métastatiques

**Source** : Mol Imaging Biol, 2025. DOI : 10.1007/s11307-025-02015-2
**Type** : étude rétrospective monocentrique, n=38
**Statut lecture** : lu en profondeur 2026-05-14
**Liens** : [umbrella review PMC 2025](pmc-2025-umbrella.md), [Ulaner 2023](ulaner-2023-prospective.md)

## Question clinique
La FES-PET apporte-t-elle quelque chose au-dessus du FDG-PET dans le staging et la
prise en charge des ILC métastatiques ER+ ?

## Méthodes
[...]

## Résultats clés
- 38 patientes ILC métastatiques ER+
- 82% des sites FDG-avides vus en FES
- Majorité des lésions : FES haut / FDG faible — pattern lobulaire indolent
- Impact thérapeutique : 8/38 → changement de prise en charge

## Limites
- Rétrospectif, monocentrique
- Pas de gold standard histologique sur toutes les lésions
- Sélection : ILC connus ER+, biais d'enrichissement

## Pertinence pour notre review
- ✅ Renforce le rationale "FES > FDG dans ILC"
- ✅ À citer dans la section "impact thérapeutique"
- ⚠️ Pas comparable à Ulaner 2023 (prospectif, n=25, staging initial vs metastatic)

## See also
- [ulaner-2023-prospective.md](ulaner-2023-prospective.md)
- [nccn-2025-guidelines.md](nccn-2025-guidelines.md) — référence cette étude pour reco
```

mdscan indexe : `description` (le résumé d'une ligne — *exactement* ce que l'agent veut pour trier les articles), `kind: reference`, `tags`. Les **liens markdown** dans le corps (`[ulaner-2023-prospective.md](ulaner-2023-prospective.md)`) sont extraits — backlinks gratuits.

### 5.3 Capture des articles à lire

```bash
# Contexte
task context define tep-fes project:medecine.literature.tep-fes
task context tep-fes

# Capture rapide depuis PubMed/Zotero — sans note encore
task add "Lire Liu 2025 FES-PET ILC métastatique" +reading +@desk
task add "Lire Ulaner 2023 prospective FES ILC" +reading +@desk
task add "Lire umbrella review PMC 2025" +reading +@desk
task add "Lire NCCN 2025 guidelines maj ILC" +reading +@desk +urgent
task add "Lire AJR expert panel 2024 FES status" +reading +@desk
```

Cinq commandes, cinq tâches sur la pile, urgency triée. Pas encore de notes — on lira, on capturera la note **après** lecture si l'article mérite (ce qui évite le "j'ai 30 notes vides et 0 lus").

### 5.4 Pipeline lecture → note → synthèse

Lecture de Liu 2025 :

```bash
task 55 start                           # je commence à lire
# … 90 min plus tard, lecture finie, mérite une note
mdscan new docs/papers/liu-2025-fes-fdg-ilc.md \
    --kind reference \
    --description "Liu et al. 2025 — FES-PET et FDG-PET pour les ILC métastatiques ; 38 patients ; 82% sites FDG vus en FES."
# (j'édite ensuite la note avec mes prises de notes)

task 55 modify note:docs/papers/liu-2025-fes-fdg-ilc.md
task 55 done
```

Le `task export` actuel :

```bash
$ task project:medecine.literature.tep-fes completed limit:5
ID  UUID      Description                                          End         Note
55  3a7f...   Lire Liu 2025 FES-PET ILC métastatique               2026-05-14  docs/papers/liu-2025-fes-fdg-ilc.md
```

L'**audit trail** est gratuit : l'historique des tâches Taskwarrior dit *quel jour* j'ai lu *quel papier*. mdscan dit *ce que je sais* de chaque papier.

### 5.5 Tâches de synthèse et rédaction

```bash
# Tâche "lente" — exige n articles lus
task add "Synthétiser section méthodo (FES vs FDG)" \
  project:medecine.literature.tep-fes +synthesis +@deep \
  note:docs/synthesis/methods-comparison.md \
  depends:55,56,57    # 3 articles à lire d'abord

task add "Rédiger intro draft v1" \
  project:medecine.literature.tep-fes +writing +@deep \
  note:docs/synthesis/intro-v1.md \
  due:2026-06-15

task add "Envoyer draft à Dr. Y pour relecture" \
  project:medecine.literature.tep-fes +collab +waiting \
  depends:<UUID intro draft>

task add "Soumettre à JNM" \
  project:medecine.literature.tep-fes +submission +waiting \
  depends:<UUID review co-auteurs>
```

Les **dépendances** Taskwarrior brillent ici : la tâche "Envoyer draft" reste masquée tant que "Rédiger intro" n'est pas done. `task next` ne propose jamais une tâche dont les prérequis ne sont pas faits. **mdscan ne saurait pas faire ça** ; Taskwarrior le fait nativement avec 15 ans de rodage.

### 5.6 Revue hebdomadaire

```bash
# 1. Tableau de bord — où en est la review ?
$ task project:medecine.literature.tep-fes status:pending
ID  Description                                          Tags        Due
56  Lire Ulaner 2023                                     reading     -
57  Lire umbrella PMC 2025                               reading     -
60  Synthétiser méthodo                                  synthesis   -      (bloqué par 56,57)
61  Rédiger intro v1                                     writing     06-15
62  Envoyer draft à Dr. Y                                waiting     -      (bloqué par 61)

# 2. Burndown des lectures
$ task project:medecine.literature.tep-fes +reading status:pending count
3

$ task project:medecine.literature.tep-fes +reading status:completed count
8

# 3. Quelles notes existent déjà ? (vue mdscan)
$ mdscan docs/papers/
docs/papers/liu-2025-fes-fdg-ilc.md      Liu et al. 2025 — FES-PET et FDG-PET pour les ILC métastatiques…
docs/papers/ulaner-2023-prospective.md   Ulaner et al. 2023 — Étude prospective FES-PET dans 25 ILC…
docs/papers/nccn-2025-guidelines.md      NCCN 2025 — Recommandations FES-PET pour ILC métastatique…
[...]

# 4. Quels concepts sont écrits ?
$ mdscan docs/concepts/ --json | jq -r '.[] | "\(.path)\t\(.description)"'
docs/concepts/er-biology-ilc.md       Biologie des ER dans ILC — expression, signalisation…
docs/concepts/fes-radiopharm.md       18F-FES — synthèse, demi-vie, mécanisme captation…

# 5. Cross-référence : tâche → note pour vérifier que tout est lié
$ task project:medecine.literature.tep-fes status:completed export \
   | jq -r '.[] | "\(.description)\t\(.note // "—")"'
Lire Liu 2025                  docs/papers/liu-2025-fes-fdg-ilc.md
Lire Ulaner 2023               docs/papers/ulaner-2023-prospective.md
Lire NCCN 2025                 docs/papers/nccn-2025-guidelines.md
Lire AJR expert panel          —                                            # ⚠️ pas de note !
Lire EJNMMI 2024 Boers         docs/papers/boers-2024-spect-comparison.md
```

La dernière ligne révèle une faille : article lu, mais pas de note prise. À refaire ou justifier (peut-être hors-scope).

### 5.7 Comment l'agent IA synthétise

Workflow : "Claude, écris-moi le draft de la section méthodo."

```bash
# L'agent collecte le matériel
$ task project:medecine.literature.tep-fes status:completed +reading export \
   | jq -r '.[] | .note' | grep -v null > /tmp/papers.txt

# L'agent lit les frontmatters
$ xargs mdscan --json < /tmp/papers.txt \
   | jq '.[] | {path, description, tags}'

# Avec ça en contexte, l'agent décide quoi lire en plein (L4)
# Probablement 2-3 articles parmi les 8 lus
$ mdscan show docs/papers/liu-2025-fes-fdg-ilc.md
$ mdscan show docs/papers/ulaner-2023-prospective.md
```

L'agent **trie sans lire** — les `description` d'une phrase suffisent pour décider lesquels charger en L4. Si on a 30 articles, ça fait la différence entre "lire 30 articles entiers" et "lire 30 résumés + 5 articles entiers". C'est l'argument central de mdscan, validé sur un vrai cas.

### 5.8 Le manuscript final

`manuscript/tep-fes-review.md` cite les notes via liens Markdown. Quand l'agent rédige, il peut suivre les liens (mdscan backlinks de la note d'article remonte chaque section du manuscript qui la cite). Trivial pour Claude Code, impossible sans :

```bash
$ mdscan backlinks docs/papers/liu-2025-fes-fdg-ilc.md
manuscript/tep-fes-review.md:142  "Liu et al. ont montré [...]"
manuscript/tep-fes-review.md:198  "[...] consistent with the findings of Liu et al."
docs/synthesis/methods-comparison.md:24  "Le pattern high-FES/low-FDG (Liu 2025) [...]"
```

Trois citations remontées en une commande. Si on retire Liu de la bibliographie, on sait exactement quelles sections corriger.

### 5.9 Limites et frictions du cas 2

- **Bibliographie externe** (Zotero, BibTeX) : pas géré par mdscan, pas géré par Taskwarrior. Il faut un troisième outil (Zotero+Better BibTeX). Le doi en frontmatter des notes est une copie locale, pas une source de vérité. Pas grave en pratique, mais c'est une limite à connaître.
- **Articles non-lus mais cités** : si on cite Liu 2025 sans encore avoir lu en profondeur, la note a juste un stub frontmatter + `kind: reference, tags: [stub]`. Convention à respecter.
- **PDF des articles** : pas dans le corpus mdscan (binaires). Garder dans `~/recherche/tep-fes-lobulaire/pdfs/` ou Zotero ; les notes pointent les PDF par chemin (ou DOI). mdscan ne tracke pas.

---

## 6. Cas 3 — Vie perso : impôts, nounou, courses

Le terrain où l'on perd le plus de temps faute de système. Plein de petites choses, échéances disparates, contextes hétérogènes.

### 6.1 Setup global

```bash
# Contextes GTD (lieux/modes)
task context define perso project:perso
task context define admin project:perso.admin

# Tags conventionnels
# +@phone — peut être fait au téléphone
# +@drive — courses, supermarché
# +@admin — paperasse, scan, démarches
# +@home — à la maison (bricolage, ménage)
# +@out  — courses ville, RV externes
# +@quick (<10min) / +@deep (focus profond)
```

### 6.2 Impôts — tâche annuelle composée

Note de référence permanente : `~/perso/docs/impots/checklist.md`

```yaml
---
description: Checklist annuelle pour la déclaration d'impôts ; documents à rassembler, étapes, comptes en banque pertinents.
kind: guide
tags: [impots, annual, admin]
last_updated: 2026-04-30
---

# Checklist impôts

## Documents à rassembler

- Bulletins de salaire (12 mois)
- Récap annuel CPAM (libéral)
- Récap PFU banque(s) (livret A non, mais comptes-titres oui)
- Avis de taxe foncière (si applicable)
- Justificatifs charges déductibles : dons, frais réels…
- Récap rétrocession SCP (médical)

## Où sont mes docs

- Bulletins : Drive `/perso/salaire/2025/`
- Cpam libéral : amelipro.fr, espace pro, exports
- Banques : envoyés par mail entre mi-fév et mi-mars
- Foncière : mail DGFiP mi-août

## Étapes

1. Janvier : rassembler les exports banque
2. Mi-février : exporter CPAM libéral
3. Mi-mars : ouvrir impots.gouv, vérifier pré-rempli
4. Compléter, simuler, soumettre
5. Vérifier l'avis fin août, contester si erreur

## Liens
- [impots-2025-recap.md](recap-2025.md)
- [impots-2024-recap.md](recap-2024.md)
```

Cette note ne change quasi jamais. C'est de la **référence stable** — mdscan, point barre.

Côté tâches Taskwarrior — la déclaration 2026 :

```bash
# Tâche parent
task add "Déclaration impôts 2026" \
  project:perso.admin.impots-2026 +annual +@admin \
  due:2026-05-15 \
  note:perso/docs/impots/checklist.md

# Sous-tâches (= autres tâches du même projet, avec dependencies si besoin)
task add "Rassembler bulletins salaire 2025" \
  project:perso.admin.impots-2026 +@admin scheduled:2026-04-01
task add "Exporter CPAM libéral 2025" \
  project:perso.admin.impots-2026 +@admin scheduled:2026-04-01
task add "Exporter PFU banques" \
  project:perso.admin.impots-2026 +@admin scheduled:2026-04-15
task add "Faire la déclaration en ligne" \
  project:perso.admin.impots-2026 +@admin \
  depends:<UUID 3 tâches au-dessus> \
  due:2026-05-15 priority:H
```

Avantages :

- La **note** survit d'année en année — chaque déclaration la lit, l'enrichit.
- Les **tâches** sont jetables : finies après mai 2026, archivées dans `task completed`.
- L'année prochaine : nouveau projet `perso.admin.impots-2027`, mais on relit `checklist.md`.

### 6.3 Payer la nounou — récurrence mensuelle

```bash
task add "Payer la nounou" \
  project:perso.admin +@admin +@phone \
  due:eom recur:monthly until:2027-09-01 \
  note:perso/docs/famille/nounou-contrat.md
```

`due:eom` = end of month. `recur:monthly` = à chaque échéance, Taskwarrior crée une nouvelle instance. `until:2027-09-01` = arrêt quand la nounou ne sera plus là (rentrée scolaire). La note `nounou-contrat.md` reste, contient le RIB, le contrat, le téléphone, etc.

Vue typique :

```bash
$ task project:perso.admin +recurring or status:recurring
ID  Description           Recur    Due
21  Payer la nounou       monthly  2026-05-31
```

Et le mois prochain :

```bash
$ task 21 done
Completed task 21.
# Une nouvelle instance est auto-créée avec due:2026-06-30
$ task project:perso.admin
ID  Description           Recur    Due
22  Payer la nounou       monthly  2026-06-30
```

**Aucune chance de gérer ça en Markdown checkbox** sans réinventer mal la récurrence. Taskwarrior fait ça en 0.1s, le mécanisme est rodé.

### 6.4 Liste de courses — trade-off explicite

Trois options pour gérer une liste de courses :

#### Option A — Une note `.md` éditée à la main

`~/perso/docs/courses/current.md` :

```markdown
---
description: Liste de courses en cours pour le drive du samedi.
kind: reference
tags: [courses, drive]
last_updated: 2026-05-13
---

# Courses pour samedi

## Drive Auchan
- Lait
- Pain de mie
- Pâtes (rigatoni)
- Yaourts grecs
- Tomates cerise

## Pharmacie
- Doliprane 500
- Coton-tiges

## Ville (à pied)
- Pain de boulanger
- Fromage à la fromagerie
```

**Avantages** : rapide à lire d'un coup d'œil ; édition libre (groupements, ratures, prix) ; pas de friction d'ajout (`mdscan edit current.md` ou n'importe quel éditeur).

**Inconvénients** : pas d'état "fait/pas fait" persistant (on rature, on recommence chaque semaine) ; pas de contexte (`+@drive` vs `+@phone`) ; ne se cross-référence pas (mais on s'en fout pour des courses).

#### Option B — Tâches Taskwarrior

```bash
task add "Lait" project:perso.courses +@drive
task add "Pain de mie" project:perso.courses +@drive
task add "Doliprane 500" project:perso.courses +@pharm
# ...
```

Au drive : `task +@drive`. À la pharmacie : `task +@pharm`. Done chaque item au fur et à mesure.

**Avantages** : contextes (`+@drive` vs `+@pharm` vs `+@boulang`) ; état explicite ; archivable (savoir ce qu'on a acheté la semaine dernière) ; agenda mobile via app companion (Taskwarrior-android, etc.).

**Inconvénients** : verbeux à saisir ; quel `project:` ? (perso.courses.2026-w20 ?) ; le côté "liste consultable d'un coup d'œil" se perd dans un report `task` colonné.

#### Option C — Hybride : note vivante + tâche conteneur

```bash
task add "Faire les courses drive samedi" \
  project:perso.courses +@drive \
  due:saturday \
  note:perso/docs/courses/current.md
```

La **tâche** rappelle qu'il faut faire le drive samedi (`due:saturday`). La **note** contient la liste, éditée librement. On done la tâche quand on a fini le drive.

**Avantages** : "what next?" géré par Taskwarrior, "what to buy?" géré par la note. Les deux outils dans leur couloir.

**Inconvénients** : pour des courses ce niveau de structure est over-engineered si on fait les courses 1×/sem. Vaut le coup si on a 3-4 listes parallèles (drive, pharmacie, ville).

#### Recommandation contextuelle

- **Liste unique hebdo** : option A (juste une note). KISS.
- **Multi-contextes** (drive + pharm + ville) : option C (tâche conteneur par contexte + 1 note par contexte).
- **Option B** : seulement si on veut un historique exhaustif de tout ce qu'on a acheté (rare).

### 6.5 Rendez-vous médicaux

Catégorie spéciale : rendez-vous = événement avec date, pas action.

Taskwarrior n'est pas pensé pour les événements (vs Org-mode qui distingue `SCHEDULED` task / `<>` event). Deux options :

#### Option A — Tâche avec `due` = date du RV

```bash
task add "RV dentiste Dr. X" \
  project:perso.sante +@phone +@out \
  due:2026-05-21T14:30 \
  note:perso/docs/sante/dentiste-x.md
```

La tâche apparaît dans `task next` à l'approche du RV. On done après le RV. La note contient l'historique des RV, soins, ordonnances.

**Limite** : ce n'est pas vraiment une "action à faire" — c'est un événement. Le faire = y aller. Sémantiquement bricolé mais ça marche.

#### Option B — Calendrier externe (Google/iCal/CalDAV)

Taskwarrior pour les **actions**, calendrier pour les **événements**. Pas de double saisie : un événement n'est pas une tâche. La tâche qui peut compléter : "Prendre RV chez le dentiste" → action ; le RV lui-même → calendrier.

```bash
task add "Prendre RV dentiste annuel" \
  project:perso.sante +@phone \
  due:2026-05-01 priority:M
# (quand fait : task done + ajout calendrier manuel)
```

**Recommandation** : option B, calendrier pour les événements ; Taskwarrior pour les actions préparatoires. Et garder une note `dentiste-x.md` pour l'historique médical.

### 6.6 Le "trou noir" des petits trucs — capture systématique

Le pire échec : l'item qu'on a en tête, qu'on remet à demain, et qui disparaît. La parade Taskwarrior :

```bash
# Alias dans le .zshrc
alias t='task'
alias ti='task add +in'

# Capture en 1 seconde
$ ti "Penser à appeler le syndic"
$ ti "Acheter pile bouton CR2032"
$ ti "Renouveler carte CPAM"

# Triage en batch — une fois/semaine
$ t +in list
$ t 41 modify -in project:perso.admin +@phone due:tomorrow
$ t 42 modify -in project:perso.courses +@drive
$ t 43 modify -in project:perso.admin +@admin scheduled:2026-06-01
```

Pas de note pour ces items. Ils naissent et meurent dans Taskwarrior. **mdscan n'a rien à dire dessus**. Et c'est exactement le point : tout ne mérite pas une note.

### 6.7 Comment l'agent IA aide

Cas typique : "Claude, qu'est-ce que je dois faire aujourd'hui ?"

```bash
$ task next limit:10 \
   '(due.before:tomorrow or +urgent or priority:H)' \
   status:pending
```

Et si l'agent veut comprendre le contexte d'une tâche :

```bash
$ task 41 export | jq -r '.[].note'
perso/docs/famille/nounou-contrat.md

$ mdscan show perso/docs/famille/nounou-contrat.md
```

Cas typique 2 : "Claude, prépare-moi un mémo synthétique sur les impôts cette année."

```bash
# Tâches du projet
$ task project:perso.admin.impots-2026 export | jq '.'

# Note de référence
$ mdscan show perso/docs/impots/checklist.md
$ mdscan show perso/docs/impots/recap-2025.md
$ mdscan show perso/docs/impots/recap-2024.md
```

Quatre commandes, l'agent a tout le matériel. Aucun parsing, aucun secret, aucun magicien.

### 6.8 Limites du cas 3

- **Échec de la discipline** : si tu n'utilises pas `+in` systématiquement, des trucs passent à travers. Vrai dans tout système GTD ; pas spécifique à cette archi.
- **Mobile** : sur téléphone, Taskwarrior est moins agréable que Things 3 / Todoist. Workarounds existent (taskwarrior-android, Tasknotes pour Obsidian + sync) mais c'est moins poli. À considérer si la vie perso se gère majoritairement mobile.
- **Calendrier** : explicitement out-of-scope, mais c'est une vraie pièce manquante. Plug : `task2cal` ou similaire si on veut un rendu agenda dans le calendrier OS.

---

## 7. Synthèse — découpage de responsabilités

Tableau récapitulatif des trois cas :

| Item | mdscan (Markdown) | Taskwarrior |
|---|---|---|
| **Cas 1 — dev mdscan** | | |
| Spec v0.4 | ✅ `kind: reference` | — |
| ADR | ✅ `kind: decision` | — |
| Roadmap (doc) | ✅ `kind: reference` | — |
| Items roadmap | — | ✅ `project:mdscan.v0.4.*` |
| Bug | note si non-trivial | ✅ `+bug` |
| Idée capturée | — | ✅ `+in` |
| Decision pending | note `kind: decision` (draft) | ✅ tâche `+decision-needed` pointant la note |
| **Cas 2 — TEP FES** | | |
| Notes de lecture | ✅ `docs/papers/X.md` | — |
| Concepts (FES biology) | ✅ `docs/concepts/X.md` | — |
| "Lire X" | — | ✅ `+reading` |
| "Synthétiser méthodo" | note draft `kind: reference` | ✅ tâche avec `depends:` |
| "Soumettre" | — | ✅ tâche avec `+waiting` cascade |
| Bibliographie | (DOI dans frontmatter) | — (Zotero externe) |
| **Cas 3 — perso** | | |
| Checklist impôts (référence) | ✅ `kind: guide` | — |
| Déclaration 2026 (action) | — | ✅ projet `perso.admin.impots-2026` |
| Payer nounou | note contrat | ✅ `recur:monthly` |
| Courses hebdo simple | ✅ note vivante | — |
| Courses multi-contexte | ✅ note par contexte | ✅ tâche conteneur |
| RV médicaux | note historique | (action de prise de RV + calendrier OS) |
| "N'oublie pas X" | — | ✅ `+in` capture, triage |

Une règle qui émerge nettement : **mdscan = ce qui a du contenu et survit ; Taskwarrior = ce qui a un état et finit**. Tous les conflits du cas 2 (où mettre les checkboxes ?) se résolvent par ce critère.

---

## 8. Patterns d'intégration concrets

### 8.1 Découvrir notes + tâches d'un projet

```bash
PROJ=medecine.literature.tep-fes

# Notes
mdscan --json | jq --arg p "$PROJ" '.[] | select(.tags | index($p | gsub("\\."; "-")))'
# ou par convention de path
mdscan docs/papers/

# Tâches
task project:$PROJ
task project:$PROJ status:pending export
task project:$PROJ status:completed limit:20
```

Un alias `proj-status` peut combiner :

```bash
proj-status() {
  local p=$1
  echo "=== Tasks pending ==="
  task project:$p status:pending
  echo
  echo "=== Notes ==="
  mdscan --json | jq -r --arg p "$p" '.[] | select(.tags | any(. == ($p | gsub("\\."; "-")))) | "\(.path)\t\(.description)"'
}
```

### 8.2 Créer une note de contexte pour une tâche

```bash
# Tâche d'abord, sans note
task add "Investiguer fuite mémoire dans scanner" project:mdscan.bugs +bug
# Taskwarrior répond : Created task 87.

# Si l'investigation devient non-triviale, créer la note
mdscan new docs/bugs/scanner-memleak.md \
  --kind reference \
  --description "Investigation fuite mémoire dans mdscan.scanner sur gros corpus ; reproduction, hypothèses, fix."

# Lier
task 87 modify note:docs/bugs/scanner-memleak.md
```

Ou en une commande via un hook `on-add` astucieux qui matche un pattern dans la description :

```python
# Hook on-add.20-auto-note
# Si la description commence par "Investiguer" ou "Spike",
# créer automatiquement une note dans docs/{bugs,spikes}/ et stamper note:
```

À utiliser avec parcimonie — les hooks magiques sont la voie rapide vers la confusion.

### 8.3 Archiver / clôturer cohéremment

Tâche done → la note reste. C'est le bon sens. La note d'investigation d'un bug résolu reste consultable.

Si on veut "archiver" un projet entier :

```bash
# Vue d'ensemble avant
task project:medecine.literature.tep-fes count                     # pending
task project:medecine.literature.tep-fes status:completed count    # done
# Si tout est done, le projet est archivé de facto (n'apparaît plus dans task next).

# Pour le déplacer hors du projet de référence :
task project:medecine.literature.tep-fes modify project:medecine.archive.tep-fes-2026
```

Les notes ? Si on veut nettoyer :

```bash
# Identifier les notes du projet
mdscan --json | jq -r '.[] | select(.tags | index("tep-fes")) | .path'

# On peut les déplacer
mv docs/papers/tep-fes/ docs/archive/tep-fes-2026/papers/
# mdscan suit (le scan re-découvre)
```

Pas besoin de "fonction archive" custom : `mv` suffit, parce que mdscan **n'a pas d'état interne sur les chemins**.

### 8.4 Workflow GTD complet

Cycle hebdomadaire :

**Capture (continu)** :
```bash
ti "anything"            # = task add +in
```

**Triage (vendredi 17h)** :
```bash
task +in
# Pour chaque item :
# - actionnable ? non → delete ou note
# - actionnable < 2min ? → fait immédiatement, done
# - actionnable plus long ? → triage (proj, tags, due, scheduled)
# - délégué ? → +waiting + annotation "demandé à X le YYYY-MM-DD"
```

**Review (vendredi 17h, après triage)** :
```bash
# Projets actifs — où en est chacun ?
task projects
task project:perso.admin
task project:mdscan.v0.4

# Tâches scheduled qui arrivent
task scheduled.before:2w

# Tâches waiting — relancer ?
task +waiting

# Tâches sans projet — anomalie
task project:
```

**Doing (en cours de semaine)** :
```bash
task next
task context perso  # ou tep-fes, ou mdscan
task <id> start
# ... travail ...
task <id> done
```

Aucun outil custom. Aucun glue manuel. **Le système de fichiers `.md` + Taskwarrior + `task export` + `mdscan --json` couvrent tout le pipeline GTD**, avec deux outils + jq.

### 8.5 Hooks pour automatiser des notes

Cas d'usage : à chaque `task done`, append une ligne `done:YYYY-MM-DD` dans un journal de l'année.

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""on-modify hook: if a task transitions to completed, append to ~/perso/docs/journal/YYYY-Q{N}.md."""
import json
import sys
from datetime import datetime
from pathlib import Path

orig = json.loads(sys.stdin.readline())
modif = json.loads(sys.stdin.readline())

# Detect transition pending → completed
if orig.get("status") == "pending" and modif.get("status") == "completed":
    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    journal = Path.home() / f"perso/docs/journal/{now.year}-Q{quarter}.md"
    journal.parent.mkdir(parents=True, exist_ok=True)
    if not journal.exists():
        journal.write_text(
            f"---\ndescription: Journal des tâches complétées Q{quarter} {now.year}.\n"
            f"kind: reference\ntags: [journal]\nlast_updated: {now:%Y-%m-%d}\n---\n\n"
            f"# Journal Q{quarter} {now.year}\n\n"
        )
    with journal.open("a") as f:
        f.write(f"- {now:%Y-%m-%d %H:%M} — {modif['description']}")
        if proj := modif.get("project"):
            f.write(f"  `{proj}`")
        f.write("\n")

# Le hook doit toujours print la tâche modifiée
print(json.dumps(modif))
sys.exit(0)
```

C'est **40 lignes de Python**. Effet : un journal Markdown auto-tenu, indexé par mdscan, qui contient l'historique des tâches complétées. Aucune duplication d'info — la tâche reste source de vérité, le journal est dérivé.

### 8.6 Inverse : afficher tâches actives dans une note via mdscan

Hypothétique (v0.5) : `mdscan show docs/adr/003-no-query-dsl.md` enrichit l'affichage avec les tâches Taskwarrior pointant cette note.

```bash
$ mdscan show docs/adr/003-no-query-dsl.md
---
description: Décision — pas de DSL de query dans mdscan ; on s'appuie sur jq pour les filtres.
kind: decision
tags: [adr, cli, design]
last_updated: 2026-05-10
---

# ADR-003 : pas de DSL de query
[...contenu...]

---
=== Tasks linked ===  (via Taskwarrior `task note:<path>`)
[pending] 123 (urg 6.2) Supprimer mdscan query du code
[pending] 124 (urg 3.1) Écrire docs/recipes.md avec exemples jq
[done]    98          Migrer tests existants de query vers jq pipelines
```

Implémentation triviale : à la fin de `mdscan show`, un appel `task note:<path> export` et un formatage. Mais c'est de la cosmétique — l'agent peut faire les deux appels lui-même.

---

## 9. Limites, frictions, anti-patterns

### 9.1 Là où ça ne marche pas bien

- **Quand une "tâche" a vraiment beaucoup de contenu** (un long brief, une enquête en cours) : le pattern UDA `note:` est obligatoire, mais la note et la tâche sont 1:1 — duplication conceptuelle. Pas un drame mais à savoir.
- **Multi-tasking** sur N projets en parallèle : Taskwarrior ne te dit pas "tu as fait du context-switching toutes les 12 min aujourd'hui". Pas son boulot. Si tu veux du quantified-self, prends Timewarrior + le hook qui auto-track les `start`/`stop`.
- **Mobile-first** : Taskwarrior 3 sur mobile est moins poli que les SaaS. Si la vie perso se gère majoritairement depuis le téléphone, ce setup tire moins de valeur.
- **Sync multi-machines** : Taskchampion-sync demande un serveur (self-hosted ou cloud). Pas instantané à mettre en place. Pour mdscan, git suffit (les `.md` sont des fichiers texte).
- **Visualisations** : Taskwarrior n'a pas de board kanban natif (TaskWarrior-TUI ou Vit existent mais sont des outils tiers). Si tu veux un board, faut un client.
- **Partage d'équipe** : Taskwarrior est mono-utilisateur. Pour du collab vrai (équipe partageant tâches), prendre Linear / Jira / GitHub Projects. mdscan + Taskwarrior reste un setup **individuel** (même si commitable en repo équipe pour les notes).

### 9.2 Frictions du couplage

- **Aucune validation cross-outil native** : un UUID Taskwarrior dans le frontmatter peut pointer une tâche supprimée. Pas de hook qui le détecte automatiquement. Mitigation : `mdscan validate` (v0.4) peut intégrer un check de cohérence si on adopte le champ frontmatter `tasks:` (cf. §10).
- **Format d'export Taskwarrior peut évoluer** : `task export` est stable depuis 2.x mais les UDAs apparaissent comme champs top-level, ce qui peut surprendre les parseurs naïfs. Faire attention dans le glue code.
- **Conventions de naming** : `project:medecine.literature.tep-fes` côté Taskwarrior vs `tags: [tep-fes, lobulaire, ...]` côté mdscan. Faut une discipline manuelle pour que ça matche. Pas de schéma unifié.

### 9.3 Anti-patterns à éviter

- **Dupliquer une description** : tâche Taskwarrior `"Lire Liu 2025"` + note frontmatter `description: "Lire Liu 2025"`. La note doit décrire **le papier**, pas la tâche. Si la `description` de la note ressemble à un verbe d'action, c'est mauvais signe.
- **Tracker des décisions en tâches** : la décision (ADR) est un doc qui survit. La tâche "trancher l'ADR" est une action ponctuelle. Bien séparer.
- **Réinventer le frontmatter en UDA Taskwarrior** : si tu te retrouves à déclarer `uda.kind`, `uda.tags`, `uda.description`, tu as inversé l'architecture. Frontmatter vit dans la note ; UDA est seulement pour les attributs propres à la tâche (estimate, doi, etc.).
- **Trop de UDAs custom** : tentation de tout indexer dans Taskwarrior. Garde minimal : `note:` (chemin Markdown), `doi:` (cas review littérature), `estimate:` (si tu fais du planning fin). Plus c'est over-engineered.

---

## 10. Implications pour mdscan v0.4 / v0.5

Si on adopte explicitement le modèle bicéphale, qu'est-ce qui change dans la spec ?

### 10.1 Changements légers dans la spec v0.4

**Schema frontmatter** :

- Pas de nouveau champ obligatoire.
- **Optionnel** : un champ `tasks: [uuid, ...]` (list of UUID strings), avec validation faible (warn si UUID inconnu via `task export`, pas erreur dure). À introduire **uniquement** si l'usage prouve qu'on en a besoin (Pattern A du §3.2). Attendre.

**CLI surface** :

- **Pas** d'ajout de `mdscan tasks`, `mdscan agenda`, `mdscan board`, `mdscan task add/done/cancel` dans v0.4 (contrairement à la proposition de [kb-task-hybrid-research.md](kb-task-hybrid-research.md) §5).
- Au lieu de ça, un paragraphe dans le README et `docs/recipes.md` qui documente le pattern Taskwarrior — comment poser `uda.note`, comment cross-référencer.

**Body conventions** :

- Pas de syntax étendue `[/]`, `[?]` pour les checkboxes. Standard GFM `[ ]` / `[x]` autorisé pour les checklists statiques dans une note (ex: checklist impôts), mais **non parsé par mdscan**.

**Phasing** :

- Phase 2.5 (la proposition "Task primitives" du hybrid) est **annulée**. Remplacée par "documentation du pattern Taskwarrior" dans Phase 4 (Recipes and docs).
- Phase 5 (Claude Code integration) peut inclure une commande `mdscan tasks` *facultative* qui sub-process `task export` (cf. ci-dessous).

### 10.2 Nouvelle commande envisageable en v0.5 (optionnelle)

```bash
mdscan tasks [--for <path>] [--project <proj>] [--json]
```

Sous-process `task export`, filtre, agrège par note pointée, jointure avec `mdscan --json`. Discovery cross-outil, **lecture seule**, pas d'écriture (Taskwarrior fait l'écriture mieux).

Implémentation : ~80 lignes de Python. Détection de Taskwarrior installé via `which task`. Si absent, exit 0 avec message "Taskwarrior not detected — `mdscan tasks` is a no-op."

Critère pour l'inclure : que **au moins 2 utilisateurs** (ou cas d'usage réels) le demandent. Sinon, le pattern reste documenté dans `docs/recipes.md` comme `mdscan --json | jq ... | xargs ...`.

### 10.3 `docs/recipes.md` — section dédiée Taskwarrior

Section dans le futur `docs/recipes.md` (Phase 4) :

```markdown
## Combiner avec Taskwarrior

Setup minimal :

```bash
task config uda.note.type string
task config uda.note.label Note
```

Recettes :

- Tâches d'un projet, avec leurs notes :
  `task project:<proj> export | jq '.[] | {desc:.description, note}'`

- Notes liées à des tâches actives :
  `task status:pending export | jq -r '.[].note // empty' | sort -u`

- Tâches sans note (candidates à documenter) :
  `task export | jq -r '.[] | select(has("note") | not) | .description'`

- Notes orphelines (sans tâche associée) — backlinks croisé :
  ```
  mdscan --json | jq -r '.[].path' | sort > /tmp/all-notes.txt
  task export | jq -r '.[].note // empty' | sort -u > /tmp/linked-notes.txt
  comm -23 /tmp/all-notes.txt /tmp/linked-notes.txt
  ```


C'est du **glue plat**. Aucune feature à coder côté mdscan — la composition Unix suffit.

### 10.4 La question du `kind: tasks`

La spec v0.4 actuelle a `kind: tasks` en valeur acceptée. La conclusion [kb-task-hybrid-research](kb-task-hybrid-research.md) recommandait déjà de le retirer (au profit de tâches-as-checkboxes). L'analyse bicéphale renforce cette conclusion : **un `kind: tasks` ne sert à rien**, parce que les tâches ne sont pas des documents.

Recommandation : **drop `kind: tasks`** dans la spec v0.4 finale. Une roadmap reste `kind: reference`. Sa "task-ness" est dans les tâches Taskwarrior qui pointent vers elle (`note:docs/plans/roadmap.md`).

### 10.5 Comparaison avec la proposition hybride [kb-task-hybrid-research]

| Aspect | Hybride (kb-task-hybrid) | Bicéphale (ce doc) |
|---|---|---|
| Granularité tâche | Item dans le body Markdown | Item dans Taskwarrior |
| Syntaxe | `- [ ] foo @owner due:` + 5 states | CLI Taskwarrior, JSON canonique |
| États | 5 fixes (`[ ]`/`[/]`/`[x]`/`[-]`/`[?]`) | Taskwarrior natifs (pending/completed/deleted/waiting/recurring) |
| Urgency | À implémenter | Polynôme Taskwarrior 15 ans rodé |
| Récurrence | Reportée (pas en v1) | Native (`recur:monthly`) |
| Dépendances | Reportées (pas en v1) | Natives (`depends:`) |
| Hooks d'extension | Aucun | `on-add/modify/exit` (Python/shell) |
| Stockage | `.md` (git-friendly) | SQLite local + `task export` JSON (commitable) |
| Commandes mdscan ajoutées | 5 (`tasks`, `agenda`, `board`, `task add`, `task done`) | 0 (ou 1 optionnelle `mdscan tasks`) |
| Code à écrire | Parseur GFM tâche + 5 commandes + agenda + board | ~0 (glue Unix) |
| Couplage externe | Aucun | Dépendance Taskwarrior installée |
| Mobile | Lit-écrit du Markdown (Obsidian Mobile) | Taskwarrior-android, moins poli |
| Compatibilité GFM | Native (rendered par GitHub) | N/A (tasks pas dans Markdown) |
| Audit trail | Git log sur les `.md` | `task history` + `task export status:completed` |

Conclusion honnête : **les deux approches sont défendables**, et le choix dépend de **deux questions** :

1. **L'utilisateur a-t-il déjà Taskwarrior ?** Si oui, le bicéphale est presque gratuit. Sinon, c'est un outil de plus à apprendre.
2. **Quelle proportion du corpus est task-shaped ?** Si dominant (un repo dont 80% des fichiers contiennent des checkboxes), l'hybride donne une expérience plus intégrée. Si minoritaire (un repo de docs où les tâches sont quelques cycles ouverts), le bicéphale donne plus de puissance par effort moindre.

Pour le contexte mdscan v0.4 (un repo de docs avec quelques tâches actives par phase), **le bicéphale gagne**.

Pour le contexte literature review (notes denses, peu de checkboxes), **le bicéphale gagne encore plus nettement** — la review n'a pas besoin de tasks-as-checkboxes, elle a besoin de "qu'est-ce qu'il me reste à lire ?", ce qui est Taskwarrior pur.

Pour le contexte vie perso (récurrences, contextes, échéances éparses), **le bicéphale écrase l'hybride** — Taskwarrior gère récurrence + contextes + dépendances nativement, l'hybride ne le fait pas et ne devrait pas chercher à le faire.

### 10.6 Décision recommandée pour la spec v0.4

1. **Drop `kind: tasks`** de la spec. Valeurs finales : `reference | guide | explanation | decision`.
2. **Pas d'ajout** des commandes `mdscan tasks/agenda/board/task ...` proposées dans [kb-task-hybrid-research](kb-task-hybrid-research.md) §5. La Phase 2.5 disparaît.
3. **Pas de champ frontmatter `tasks:`** par défaut. Optionnel, activable via `[tool.mdscan.schema] fields_optional = ["tasks"]` si le projet en a usage.
4. **Documentation** dans `docs/recipes.md` (Phase 4) du pattern Taskwarrior — UDA `note:`, recettes jq, hooks Python.
5. **Commande `mdscan tasks`** repoussée en Phase 5 (intégration Claude Code), conditionnée à la demande utilisateur réelle. ~80 lignes de glue si demandé.
6. **Open questions** mises à jour : la décision tâches-as-items vs tâches-Taskwarrior tranche en faveur de Taskwarrior pour ce repo et ce profil utilisateur ; reste ouverte pour d'autres profils.

---

## 11. Preuve d'intégration — `mdscan scan docs/`

Vérification que ce document s'intègre proprement au corpus existant et que mdscan le détecte avec la description frontmatter :

```
$ uv run mdscan scan docs/
hint: run 'mdscan check-links' to verify link reachability
cli-audit.md                        Audit of mdscan CLI against clig.dev and agent-focused CLI design principles.
kb-task-hybrid-research.md          Reconciles mdscan's dual mandate as knowledge base + task tracker by separating doc-kind (content shape) from item-level tasks (GFM checkboxes with inline metadata), surveys hybrid plaintext PKM/PM tools, and proposes a concrete kind enum, syntax, and command surface.
knowledge-organisation-research.md  Web-researched survey of knowledge-organisation methodologies (Diataxis, Zettelkasten, PARA, LATCH, ADRs, GitLab CTRT, etc.) used to validate and refine mdscan's `kind` frontmatter enum, with an opinionated recommendation.
mdscan-taskwarrior-synergy.md       Etude du couplage mdscan + Taskwarrior comme architecture bicéphale connaissance/tâches, avec trois cas d'usage concrets (dev mdscan, literature review TEP FES, vie perso) et implications pour la spec v0.4/v0.5.
obsidian-query-survey.md            Deep survey of Obsidian's query surfaces (Search, Dataview DQL, Dataview JS, Bases) with side-by-side use-case examples and concrete mdscan CLI adaptations.
pkm-for-agents.md                   Analysis of Obsidian PKM features translated into agent-facing primitives for an AI-native knowledge system built on top of mdscan.
plan-cli-v0.3.md                    Implementation plan for mdscan v0.3 CLI improvements based on clig.dev and agent CLI audit.
plan-v0.2.md                        Implementation plan for mdscan v0.2 features (config, tree, coverage, all-links).
spec-v0.4.md                        Living specification for mdscan v0.4 — evolution toward "madge for markdown" with minimal frontmatter, graph primitives, and standalone CLI design. Updated as decisions are taken in discussion.
```

Le fichier apparaît en quatrième position (ordre alphabétique), avec sa description complète. C'est exactement le L1 (inventaire) que la spec v0.4 décrit : un agent voyant cette ligne décide en une seconde s'il a besoin du contenu, sans le charger.

---

## 12. Conclusion

Si on prend mdscan au sérieux comme "**madge for markdown**" (positionnement spec v0.4), alors la conclusion est forcée : **mdscan n'a pas à faire de la gestion de tâches**. Pas plus que `madge` ne fait du build, du test, du déploiement. Il scanne, il graphe, il discovere.

Pour la partie tâches, **Taskwarrior est mature, libre, scriptable, plain-text-exportable, hook-extensible**. Le coupler via un UDA `note:` et — éventuellement — un champ frontmatter `tasks:` (optionnel) est un protocole minimal. L'agent IA orchestre les deux outils via `task export` et `mdscan --json`, agrège avec `jq`, et a tout ce qu'il faut.

Les trois cas d'usage démontrent que :

- **Pour un projet de dev** (cas 1), la séparation est nette et productive. Tasks dans Taskwarrior, decisions/specs/ADRs dans `.md`. Le lien est explicite et facultatif.
- **Pour une literature review** (cas 2), la séparation est encore plus claire. Lecture pipeline dans Taskwarrior, contenu intellectuel dans `.md`. mdscan tire toute sa valeur sur le tri des frontmatters d'articles.
- **Pour la vie perso** (cas 3), Taskwarrior porte 80% de la charge (récurrences, contextes, échéances) ; les `.md` portent les 20% qui survivent (checklists référence, historiques médicaux).

La friction n°1 du couplage est **la discipline humaine** : penser à mettre `note:` quand pertinent, garder les conventions de naming cohérentes entre `project:` et `tags:`. Pas une friction d'outillage.

mdscan v0.4 peut sortir **sans aucune feature liée aux tâches** et être complet. v0.5 peut ajouter — si la demande arrive — une commande `mdscan tasks` de discovery cross-outil. Pas plus.

---

## 13. Références

### Taskwarrior

- [Taskwarrior — Task Representation](https://taskwarrior.org/docs/task/)
- [Taskwarrior — Urgency](https://taskwarrior.org/docs/urgency/)
- [Taskwarrior — UDAs](https://taskwarrior.org/docs/udas/)
- [Taskwarrior — Hooks v2 Guide](https://taskwarrior.org/docs/hooks/)
- [Taskwarrior — Hook Author's Guide](https://taskwarrior.org/docs/hooks_guide/)
- [Taskwarrior — Recurrence](https://taskwarrior.org/docs/recurrence/)
- [Taskwarrior — Best Practices](https://taskwarrior.org/docs/best-practices/)
- [Taskwarrior — Workflow Examples](https://taskwarrior.org/docs/workflow/)
- [Taskwarrior — Commands](https://taskwarrior.org/docs/commands/)
- [Taskwarrior — Export Command](https://taskwarrior.org/docs/commands/export/)
- [Taskwarrior — Upgrading to v3](https://taskwarrior.org/docs/upgrade-3/)
- [Brokenpip3 — Taskwarrior practical guide 2025](https://www.brokenpip3.com/posts/2025-02-09-taskwarrior-practical-guide-1/)
- [CS Syd — GTD with Taskwarrior series](https://cs-syd.eu/posts/2015-07-05-gtd-with-taskwarrior-part-4-processing)
- [tasklib (Python)](https://tasklib.readthedocs.io/)
- [tw-hooks framework](https://github.com/bergercookie/tw-hooks)

### Médecine — FES-PET et ILC

- [NCCN Guidelines 2025 — FES-PET pour ILC](https://investor.gehealthcare.com/news-releases/news-release-details/updated-nccn-clinical-practice-guidelines-oncology-nccn)
- [Liu et al. 2025 — FES vs FDG dans ILC métastatique](https://link.springer.com/article/10.1007/s11307-025-02015-2)
- [Ulaner et al. 2023 — Étude prospective ILC](https://ajronline.org/doi/10.2214/AJR.22.28809)
- [AJR Expert Panel 2024 — FES status](https://ajronline.org/doi/full/10.2214/AJR.23.30330)
- [PMC Umbrella Review 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12110083/)
- [Lobular Breast Cancer Alliance — FES Trial](https://lobularbreastcancer.org/imaging-trial-18f-fluoroestradiol-fes-pet-ct-for-breast-cancer/)

### Documents internes mdscan

- [CLAUDE.md](../CLAUDE.md) — instructions agent et vue d'ensemble projet
- [spec-v0.4.md](spec-v0.4.md) — spécification vivante v0.4
- [kb-task-hybrid-research.md](kb-task-hybrid-research.md) — proposition hybride checkboxes (alternative à ce doc)
- [knowledge-organisation-research.md](knowledge-organisation-research.md) — méthodologies d'organisation
- [pkm-for-agents.md](pkm-for-agents.md) — features PKM traduites en primitives agent
- [obsidian-query-survey.md](obsidian-query-survey.md) — survey query Obsidian/Dataview/Bases
