---
description: Implementation plan for mdscan v0.2 features (config, tree, coverage, all-links).
---

# mdscan v0.2 — Plan d'implementation

## Vue d'ensemble

4 features, ordonnees par dependance d'implementation :

| #   | Feature                          | Fichiers touches                                   | Nouveaux fichiers          |
| --- | -------------------------------- | -------------------------------------------------- | -------------------------- |
| F1  | Config `[tool.mdscan]`           | `cli.py`, `scanner.py`                             | `config.py`                |
| F2  | `mdscan tree`                    | `cli.py`                                           | `tree.py`                  |
| F3  | `mdscan coverage`                | `cli.py`                                           | —                          |
| F4  | `check-links --all-links`        | `cli.py`, `links.py`                               | —                          |

Ordre d'implementation recommande : **F1 → F2 → F4 → F3**

- F1 d'abord car les features suivantes en beneficient (ignore patterns, entrypoint par defaut).
- F3 en dernier car c'est la plus simple et elle aggrege les resultats des autres features.

---

## F1 — Config `[tool.mdscan]` dans `pyproject.toml`

### Comportement

Lire `pyproject.toml` dans le repertoire courant (ou le parent le plus proche qui en contient un) et extraire `[tool.mdscan]` :

```toml
[tool.mdscan]
ignore = ["drafts/*", "archive/*"]
max-depth = 3
entrypoint = "docs/index.md"
```

Les flags CLI sont prioritaires sur la config fichier (**CLI > config > defaults**).

### Schema de la config

| Cle          | Type         | Defaut       | Utilise par                |
| ------------ | ------------ | ------------ | -------------------------- |
| `ignore`     | `list[str]`  | `[]`         | `scan`, `check-links`      |
| `max-depth`  | `int | null` | `null`       | `scan`                     |
| `entrypoint` | `str | null` | `null`       | `check-links`, `tree`, `coverage` |

### Nouveau module : `src/mdscan/config.py`

```python
@dataclass
class MdscanConfig:
    ignore: list[str]
    max_depth: int | None
    entrypoint: str | None

def load_config(start_dir: Path) -> MdscanConfig:
    """Walk up from start_dir to find pyproject.toml, parse [tool.mdscan]."""
```

- Utilise `tomllib` (stdlib Python 3.11+) — **aucune dependance a ajouter**.
- Remonte les repertoires parents jusqu'a trouver `pyproject.toml` (ou atteint `/`).
- Retourne un `MdscanConfig` avec les defauts pour les cles absentes.

### Modifications `cli.py`

Dans `_run_scan` et `_run_check_links` :

```python
cfg = load_config(directory)
ignore = (args.ignore or []) + cfg.ignore          # CLI prioritaire mais cumulatif
max_depth = args.max_depth if args.max_depth is not None else cfg.max_depth
entrypoint = args.entrypoint or cfg.entrypoint
```

### Decouvrabilite par les agents

Quand `_print_diagnostics` emet des warnings et qu'il n'y a pas de config trouvee, ajouter un hint :

```
hint: to persist settings, add a [tool.mdscan] section in pyproject.toml (see mdscan --help)
```

Ce hint ne s'affiche **que s'il y a des warnings** et **qu'aucune config n'existe deja**. Il evite du bruit sur les projets deja configures.

### Tests (dans `test_config.py` + ajouts a `test_cli.py`)

1. `test_load_config_from_pyproject` — parse correctement les 3 cles
2. `test_load_config_missing_section` — retourne les defauts
3. `test_load_config_no_pyproject` — retourne les defauts
4. `test_load_config_walks_up_parents` — trouve `pyproject.toml` dans un parent
5. `test_cli_config_ignore_merged_with_flag` — les deux sources se cumulent
6. `test_cli_flag_overrides_config_max_depth` — le flag CLI prend le dessus
7. `test_config_hint_shown_when_no_config` — hint affiche si warnings sans config
8. `test_config_hint_hidden_when_config_exists` — pas de hint si config presente

---

## F2 — `mdscan tree`

### Comportement

Affiche le graphe documentaire sous forme d'arbre depuis l'entrypoint :

```
$ mdscan tree docs/
CLAUDE.md
├── docs/architecture.md
│   ├── docs/api.md
│   └── docs/database.md
├── docs/setup.md
└── docs/contributing.md
    └── docs/code-style.md
```

- Entrypoint resolu comme dans `check-links` (auto-detect ou `--entrypoint`).
- Liens deja visites affiches avec un suffixe `(*)` pour indiquer un cycle sans le re-developper.
- Fichiers orphelins (non atteints) listes a la fin avec un prefixe distinct.
- Supporte `--json` pour une sortie machine-readable (arbre comme objet imbrique).

### CLI

```
mdscan tree [directory] [--entrypoint FILE] [--json] [--ignore PATTERN]
```

Exit codes : `0` succes, `2` erreur d'usage.

### Nouveau module : `src/mdscan/tree.py`

```python
def build_tree(
    entrypoint: str,
    file_by_path: dict[str, MdFile],
) -> TreeNode:
    """DFS from entrypoint, return tree structure."""

def format_tree(node: TreeNode) -> str:
    """Render tree as box-drawing characters string."""
```

`TreeNode` : simple dataclass `(path: str, children: list[TreeNode], is_cycle: bool)`.

### Modifications `cli.py`

- Nouveau subparser `tree` avec les memes options que `check-links`.
- `_run_tree` : scan + resolution entrypoint (factoriser avec `_run_check_links`).
- La resolution de l'entrypoint et le scan initial sont identiques a `check-links` → extraire une fonction `_resolve_entrypoint(args) -> tuple[list[MdFile], str]` pour eviter la duplication.

### Tests (`test_tree.py` + ajouts a `test_cli.py`)

1. `test_tree_simple_hierarchy` — arbre lineaire correct
2. `test_tree_cycle_detection` — lien circulaire affiche `(*)`
3. `test_tree_orphan_section` — fichiers non atteints listes en bas
4. `test_tree_json_output` — structure JSON imbriquee valide
5. `test_tree_entrypoint_auto_detection` — meme logique que check-links
6. `test_tree_respects_ignore` — patterns d'exclusion appliques

---

## F3 — `mdscan coverage`

### Comportement

```
$ mdscan coverage docs/
files:         42
described:     38 (90%)
reachable:     35/42 (83%)
broken links:  1
avg words:     12
longest:       docs/api.md (87 words)
```

Exit codes : `0` si 100% described + 100% reachable + 0 broken links, `1` sinon.

### CLI

```
mdscan coverage [directory] [--entrypoint FILE] [--json] [--ignore PATTERN]
```

### Implementation dans `cli.py`

Pas de nouveau module. `_run_coverage` :
1. Appelle `scan(directory, ...)` pour les stats de description.
2. Appelle la logique de `check-links` (refactorisee en F2) pour reachability.
3. Formate et affiche.

Le JSON output est un objet plat avec les memes cles.

### Tests (ajouts a `test_cli.py`)

1. `test_coverage_all_perfect` — exit 0, tous les compteurs a 100%
2. `test_coverage_missing_descriptions` — exit 1, pourcentage correct
3. `test_coverage_unreachable_files` — exit 1, reachable count correct
4. `test_coverage_json` — structure JSON valide avec toutes les cles

---

## F4 — `check-links --all-links`

### Comportement

Par defaut, `check-links` ne verifie que les liens vers des `.md`. Avec `--all-links`, il verifie aussi les liens vers des fichiers non-markdown (`.py`, `.yaml`, images, etc.).

```
$ mdscan check-links --all-links docs/
warn: 2 broken asset links (target file not found):
  - docs/setup.md → src/old_config.py
  - docs/arch.md → diagrams/flow.png
  fix: for EACH source file, have a dedicated agent (e.g. fast model like Haiku) fix or remove its broken links
```

### Modifications `links.py`

Nouvelle fonction :

```python
def extract_all_links(text: str) -> list[str]:
    """Return all relative file paths referenced in markdown links.

    Unlike extract_md_links, includes non-.md targets (images, code, etc.).
    Filters out http(s):// and absolute paths.
    """
```

Le regex : `r"\[([^\]]*)\]\(([^)\s]+)\)"` — capture tout lien markdown, puis filtre les URLs et paths absolus.

### Modifications `cli.py`

- Ajouter `--all-links` au subparser `check-links`.
- Dans `_run_check_links`, si `--all-links` :
  - Extraire les liens non-md avec `extract_all_links`.
  - Pour chaque lien non-md, verifier que le fichier cible existe (`Path(directory / resolved).is_file()`).
  - Reporter les broken asset links dans un groupe diagnostique separe.

Les broken asset links ne comptent pas pour la reachability BFS (qui reste md-only). Ils sont un diagnostic additionnel.

### Tests (ajouts a `test_cli.py` + `test_links.py`)

1. `test_extract_all_links` — capture `.py`, `.png`, `.md`, ignore URLs
2. `test_check_links_all_links_valid` — lien vers `.py` existant → pas d'erreur
3. `test_check_links_all_links_broken` — lien vers `.py` inexistant → warning
4. `test_check_links_without_flag_ignores_assets` — sans `--all-links`, pas de check assets

---

## Refactoring partage

Plusieurs features ont besoin de la meme logique. A extraire :

### 1. Resolution d'entrypoint

Utilise par `check-links`, `tree`, `coverage` (F2, F3). Extraire de `_run_check_links` :

```python
def _resolve_and_scan(
    args: argparse.Namespace,
    cfg: MdscanConfig,
) -> tuple[list[MdFile], str, dict[str, MdFile]]:
    """Scan directory, resolve entrypoint, build lookup. Shared by check-links, tree, coverage."""
```

### 2. BFS reachability

Utilise par `check-links` et `coverage`. Extraire :

```python
def _compute_reachability(
    entrypoint: str,
    file_by_path: dict[str, MdFile],
    scanned_paths: set[str],
) -> tuple[set[str], list[tuple[str, str]]]:
    """BFS from entrypoint. Returns (reachable, broken_links)."""
```

Ces deux fonctions restent dans `cli.py` (privees) ou vont dans un module `analysis.py` si la taille le justifie.
