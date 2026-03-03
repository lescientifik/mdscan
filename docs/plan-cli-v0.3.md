---
description: Implementation plan for mdscan v0.3 CLI improvements based on clig.dev and agent CLI audit.
---

# Plan v0.3 — CLI Improvements

**Ref**: [docs/cli-audit.md](cli-audit.md)
**Approach**: TDD red/green. Each task starts with a failing test, then implementation.

---

## Phase 1 — Robustness & Signal Handling

### 1.1 Catch `KeyboardInterrupt` cleanly
> Audit point #1 (P0)

- [ ] **RED** — `test_cli.py::TestSignals::test_ctrl_c_no_traceback`: send `SIGINT` to a subprocess running `mdscan scan` on a directory. Assert exit code is non-zero, stderr does NOT contain "Traceback", stdout is empty or minimal.
- [ ] **GREEN** — In `cli.py::main()`, wrap the dispatch in a `try/except KeyboardInterrupt` that prints nothing (or a single newline) and calls `sys.exit(130)` (128 + SIGINT=2, UNIX convention).
- [ ] Verify: run `mdscan scan .` in terminal, hit Ctrl+C, confirm clean exit.

### 1.2 Catch `BrokenPipeError` cleanly
> Piping to `head` or truncating pipe consumers triggers this.

- [ ] **RED** — `test_cli.py::TestSignals::test_broken_pipe_no_traceback`: pipe `mdscan scan` output through a process that closes early (e.g. `head -1`). Assert no traceback on stderr.
- [ ] **GREEN** — Add `except BrokenPipeError` in `main()`, close stdout/stderr quietly, `sys.exit(0)`.

---

## Phase 2 — Exit Code Semantics

### 2.1 Define exit code constants
> Audit point #5 (P1)

Schema decided:

```
EXIT_OK        = 0   # Success, no issues
EXIT_WARN      = 1   # Soft warnings (missing descriptions, too-long descriptions)
EXIT_USAGE     = 2   # Usage error (bad args, missing directory, missing entrypoint)
EXIT_STRUCTURE = 3   # Structural issues (broken links, unreachable files)
```

- [ ] **RED** — `test_cli.py::TestExitCodes::test_exit_3_broken_links`: `check-links` with a broken link → exit 3. Currently asserts `returncode == 1`, change to `== 3`.
- [ ] **RED** — `test_cli.py::TestExitCodes::test_exit_3_unreachable_files`: `check-links` with unreachable file → exit 3.
- [ ] **RED** — `test_cli.py::TestExitCodes::test_exit_1_remains_for_soft_warnings`: `scan` with missing descriptions → exit 1 (unchanged).
- [ ] **RED** — `test_cli.py::TestExitCodes::test_exit_3_coverage_structural`: `coverage` with broken links → exit 3.
- [ ] **RED** — `test_cli.py::TestExitCodes::test_exit_1_coverage_soft`: `coverage` where all reachable but some missing descriptions → exit 1.
- [ ] **GREEN** — Create `_types.py` constants `EXIT_OK`, `EXIT_WARN`, `EXIT_USAGE`, `EXIT_STRUCTURE`. Update `_run_check_links`, `_run_coverage`, `_run_scan`, `_run_set_description` to use them. Rules:
  - `_run_scan`: broken links not checked here, so only 0 (clean) or 1 (soft warnings). No change.
  - `_run_check_links`: broken links or unreachable → 3. Only soft warnings from diagnostics → 1. Both → 3 (worst wins).
  - `_run_coverage`: `is_perfect` logic split: if broken links or unreachable → 3, elif missing descriptions → 1, else → 0.
  - `_run_set_description`: too-long description → 1 (soft warning). No change.
- [ ] **REFACTOR** — Update all existing tests that hardcode `returncode == 1` for structural issues to use `== 3`. Grep for `returncode == 1` in tests, update those that test broken links or unreachable files.

---

## Phase 3 — Help Text & Discoverability

### 3.1 Add examples to all subcommand help
> Audit point #2 (P0)

- [ ] **RED** — `test_cli.py::TestHelp::test_scan_help_has_examples`: run `mdscan scan -h`, assert stdout contains "example" (case-insensitive) and a `mdscan scan` invocation.
- [ ] **RED** — `test_cli.py::TestHelp::test_check_links_help_has_examples`: same for `check-links`.
- [ ] **RED** — `test_cli.py::TestHelp::test_tree_help_has_examples`: same for `tree`.
- [ ] **RED** — `test_cli.py::TestHelp::test_coverage_help_has_examples`: same for `coverage`.
- [ ] **RED** — `test_cli.py::TestHelp::test_set_description_help_has_examples`: same for `set-description`.
- [ ] **GREEN** — Switch to `argparse.RawDescriptionHelpFormatter` on each subparser. Add an `epilog` with 1-2 realistic examples per subcommand. Format:
  ```
  examples:
    mdscan scan docs/
    mdscan scan --json --max-depth 2 .
  ```

### 3.2 Add support link to top-level help
> Audit point #9 (P1)

- [ ] **RED** — `test_cli.py::TestHelp::test_top_level_help_has_url`: run `mdscan --help`, assert "github.com" appears in output.
- [ ] **GREEN** — Add `epilog` to the top-level parser with the repo URL.

### 3.3 Typo suggestions for unknown subcommands
> Audit point #3 (P0)

- [ ] **RED** — `test_cli.py::TestHelp::test_typo_suggestion`: run `mdscan scna`, assert stderr contains "did you mean: scan" (case-insensitive).
- [ ] **RED** — `test_cli.py::TestHelp::test_unknown_command_no_match`: run `mdscan xyzzy`, assert stderr contains "unknown command" but no "did you mean" (no close match).
- [ ] **GREEN** — In `cli.py::main()`, after the implicit-scan prepend logic, detect when the first arg looks like a misspelled command (not a path, starts with a letter, no `/` or `.`). Use `difflib.get_close_matches(arg, known_commands, n=1, cutoff=0.6)`. If match found, print `error: unknown command '{arg}'\nDid you mean: {match}` to stderr, exit 2. If no match, let argparse handle it (it'll treat it as a path to `scan`).

### 3.4 `help` subcommand
> Audit point #11 (P2)

- [ ] **RED** — `test_cli.py::TestHelp::test_help_subcommand`: run `mdscan help`, assert exit 0 and output identical to `mdscan --help`.
- [ ] **RED** — `test_cli.py::TestHelp::test_help_subcommand_with_target`: run `mdscan help scan`, assert output identical to `mdscan scan --help`.
- [ ] **GREEN** — Add a `help` subparser that accepts an optional positional `command` argument. In `_run_help(args)`, invoke the appropriate parser's `print_help()`. Add `"help"` to `known_commands` set.

### 3.5 Next-step suggestions after success
> Audit point #4 (P0)

- [ ] **RED** — `test_cli.py::TestNextSteps::test_scan_suggests_check_links`: run `mdscan scan` on a valid directory, assert stderr contains "check-links" (suggestion to run next).
- [ ] **RED** — `test_cli.py::TestNextSteps::test_no_suggestion_in_json_mode`: run `mdscan scan --json`, assert stderr does NOT contain next-step hints (agents using JSON know what they're doing).
- [ ] **RED** — `test_cli.py::TestNextSteps::test_no_suggestion_in_quiet_mode`: run `mdscan scan -q`, no next-step hint on stderr (depends on 4.1).
- [ ] **GREEN** — After successful `scan` in text mode, print `hint: run 'mdscan check-links' to verify link reachability` to stderr. Only when exit 0 or 1, not on errors. Skip in `--json` and `--quiet` modes.

---

## Phase 4 — Flags: `--quiet` and `--verbose`

### 4.1 `--quiet` / `-q` flag
> Audit point #7 (P1)

- [ ] **RED** — `test_cli.py::TestQuiet::test_quiet_suppresses_diagnostics`: run `mdscan scan -q` on a dir with missing descriptions. Assert stderr is empty, exit code unchanged (still 1).
- [ ] **RED** — `test_cli.py::TestQuiet::test_quiet_suppresses_stdout_text`: run `mdscan scan -q` on valid dir. Assert stdout is empty.
- [ ] **RED** — `test_cli.py::TestQuiet::test_quiet_preserves_json`: run `mdscan scan -q --json` still outputs JSON to stdout (data must flow for piping).
- [ ] **RED** — `test_cli.py::TestQuiet::test_quiet_on_check_links`: run `mdscan check-links -q`, assert stderr empty.
- [ ] **GREEN** — Add `-q`/`--quiet` to the top-level parser (inherited by subparsers via `parents=[]` or added to each). When set:
  - `_print_diagnostics` returns early without printing.
  - Text output skipped (but JSON still printed — `--quiet` means "no human text", not "no data").
  - Next-step hints skipped.
  - `entrypoint:` announcement on check-links skipped.

### 4.2 `--verbose` / `-v` flag
> Audit point #8 (P1)

- [ ] **RED** — `test_cli.py::TestVerbose::test_verbose_shows_config_source`: run `mdscan scan -v` in a dir with pyproject.toml. Assert stderr contains the config file path.
- [ ] **RED** — `test_cli.py::TestVerbose::test_verbose_shows_scan_stats`: run `mdscan scan -v`, assert stderr contains something like "scanned N files in M dirs".
- [ ] **GREEN** — Add `-v`/`--verbose` to top-level parser. When set, print extra info to stderr:
  - Config file location: `config: /path/to/pyproject.toml` or `config: none`
  - Scan stats: `scanned: {n} files in {m} directories`
  - Entrypoint resolution: `entrypoint: {path} (from {source})` where source is "flag", "config", "auto-detected"

---

## Phase 5 — Color

### 5.1 Minimal color on stderr prefixes
> Audit point #12 (P2)

- [ ] **RED** — `test_cli.py::TestColor::test_no_color_env_disables_color`: set `NO_COLOR=1`, run mdscan with warnings. Assert stderr contains no ANSI escape sequences (`\x1b[`).
- [ ] **RED** — `test_cli.py::TestColor::test_no_color_flag_disables_color`: run `mdscan --no-color scan` with warnings. Assert no ANSI escapes in stderr.
- [ ] **RED** — `test_cli.py::TestColor::test_color_off_when_not_tty`: (subprocess captures = not a TTY). Run mdscan with warnings. Assert no ANSI escapes. This validates the default safe behavior.
- [ ] **GREEN** — Create `src/mdscan/color.py`:
  ```python
  def use_color(stream, *, no_color_flag: bool = False) -> bool:
      """Return True if color should be used on the given stream."""
      if no_color_flag:
          return False
      if os.environ.get("NO_COLOR") is not None:
          return False
      if os.environ.get("TERM") == "dumb":
          return False
      return hasattr(stream, "isatty") and stream.isatty()
  ```
  Add `--no-color` flag to top-level parser. Wrap stderr output functions to apply ANSI codes:
  - `error:` → red (`\x1b[31m`)
  - `warn:` → yellow (`\x1b[33m`)
  - `hint:` → cyan (`\x1b[36m`)
  - `fix:` → dim (`\x1b[2m`)
  - Reset: `\x1b[0m`

  No external dependencies (just ANSI codes, no `colorama`/`rich`).

---

## Phase 6 — Environment Variables

### 6.1 `NO_COLOR` support
> Audit point #6 (P1) — covered by phase 5.

### 6.2 `MDSCAN_QUIET` and `MDSCAN_VERBOSE` env vars
> Audit point #6 (P1)

- [ ] **RED** — `test_cli.py::TestEnvVars::test_mdscan_quiet_env`: set `MDSCAN_QUIET=1`, run mdscan with warnings. Assert same behavior as `-q`.
- [ ] **RED** — `test_cli.py::TestEnvVars::test_flag_overrides_env`: set `MDSCAN_QUIET=1`, run `mdscan scan -v`. Assert verbose wins (flag > env).
- [ ] **GREEN** — In `main()`, read `MDSCAN_QUIET` and `MDSCAN_VERBOSE` from `os.environ`. Apply as defaults, let CLI flags override.

---

## Phase 7 — stdin & Output Polish

### 7.1 `set-description` reads from stdin with `-`
> Audit point #16 (P2)

- [ ] **RED** — `test_cli.py::TestSetDescription::test_stdin_dash`: run `echo "My description" | mdscan set-description file.md -`. Assert description written correctly.
- [ ] **RED** — `test_cli.py::TestSetDescription::test_stdin_dash_strips_whitespace`: pipe text with trailing newline, assert description is stripped.
- [ ] **GREEN** — In `_run_set_description()`, if `args.description == "-"`, read `sys.stdin.read().strip()`. If stdin is empty, print error and exit 2.

### 7.2 `--plain` flag for tab-separated scan output
> Audit point #13 (P2)

- [ ] **RED** — `test_cli.py::TestPlain::test_plain_output_tab_separated`: run `mdscan scan --plain`. Assert each output line has exactly one tab, path before tab, description after.
- [ ] **RED** — `test_cli.py::TestPlain::test_plain_pipeable_to_cut`: run `mdscan scan --plain | cut -f1`, assert only paths in output.
- [ ] **GREEN** — Add `--plain` flag to `scan`. In `format_text()`, when plain=True, use `f"{path}\t{desc}"` instead of column alignment. Mutually exclusive with `--json`.

### 7.3 `--limit` flag for scan
> Audit point #10 (P1)

- [ ] **RED** — `test_cli.py::TestLimit::test_limit_truncates_output`: create 10 .md files, run `mdscan scan --limit 3`. Assert only 3 lines in stdout (text mode).
- [ ] **RED** — `test_cli.py::TestLimit::test_limit_with_json`: run `mdscan scan --json --limit 3`. Assert JSON array has 3 elements.
- [ ] **RED** — `test_cli.py::TestLimit::test_limit_zero_means_no_limit`: run `mdscan scan --limit 0`. Assert all files shown.
- [ ] **GREEN** — Add `--limit` to `scan` subparser (int, default None). Apply slice to `files` list before formatting. Note: apply after sorting but before output.

### 7.4 Condense `fix:` messages
> Audit point #15 (P2)

- [ ] **RED** — `test_cli.py::TestDiagnostics::test_fix_messages_concise`: run mdscan on files with issues. Assert each `fix:` line is at most 100 chars.
- [ ] **GREEN** — Rewrite `fix:` messages to be single-line and terse:
  - Missing description: `fix: mdscan set-description <file> "..."` (one-liner)
  - Unreachable: `fix: add links from a reachable doc to each file above`
  - Broken link: `fix: remove or correct each broken link above`
  - Too long description: `fix: rewrite with fewer than {MAX} words`

---

## Phase 8 — Coverage Exit Code Refinement

### 8.1 `coverage` uses graduated exit codes
> Audit point #14 (P2) — subsumed by Phase 2

Handled in Phase 2 (exit codes). No extra task, but verify:
- [ ] **VERIFY** — After Phase 2, confirm `coverage` exits 3 for structural issues (broken links, unreachable), 1 for soft issues (missing descriptions only), 0 for perfect.

---

## Execution Order

Recommended order for minimal merge conflicts:

1. **Phase 2** — Exit codes (changes return values, many test updates)
2. **Phase 1** — Signals (small, isolated)
3. **Phase 4** — `--quiet` / `--verbose` (adds flags, plumbing needed before other phases use it)
4. **Phase 3** — Help text (uses `--quiet` in one test)
5. **Phase 7** — stdin, `--plain`, `--limit`, condensed messages
6. **Phase 5** — Color (depends on `--no-color` flag architecture)
7. **Phase 6** — Environment variables (depends on `--quiet`/`--verbose` being done)
8. **Phase 8** — Verification pass

---

## Out of scope (for now)

- Pager support (`less`) — overkill for mdscan's output size
- `--search` flag for command discovery — only 5 subcommands, not needed
- Man page generation — argparse help is sufficient
- `--offset` flag — `--limit` + `--max-depth` provide enough control
