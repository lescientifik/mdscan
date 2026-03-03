---
description: Audit of mdscan CLI against clig.dev and agent-focused CLI design principles.
---

# CLI Audit — mdscan vs clig.dev + Agent CLI Design

**Date**: 2026-03-03
**Sources**: [clig.dev](https://clig.dev/), [kumak.dev — CLI Design for LLMs](https://kumak.dev/self-documenting-cli-design-for-llms/)

---

## What's already done well

| Principle | Status |
|-----------|--------|
| stdout/stderr separation | Correct: data → stdout, diagnostics → stderr |
| `--json` on all read commands | Present on scan, check-links, tree, coverage |
| Default command (`scan`) | Implicit, no subcommand needed |
| Exit code 2 for usage errors | Consistent across all subcommands |
| Config in pyproject.toml + CLI override | Proper precedence: flags > config |
| Structured error prefixes | `error:`, `warn:`, `hint:`, `fix:` |
| No interactivity | Fully non-interactive, agent-safe |
| Hints on stderr | Don't pollute piped stdout |

---

## Violations found

### P0 — Critical

#### 1. Ctrl+C shows Python traceback
No `SIGINT` handler. `KeyboardInterrupt` propagates unhandled, producing a stack trace.

- **clig.dev**: "Exit as soon as possible on Ctrl+C", "Avoid printing stack traces"
- **Impact**: Ugly for humans, wastes tokens for agents

#### 2. No examples in help text
All `--help` output uses default argparse formatting with zero examples.

- **clig.dev**: "Lead with examples, particularly common complex use cases"
- **Agent doc**: "Each subcommand's --help should include one example with realistic values"

#### 3. No typo suggestions
`mdscan scna` gives a generic argparse error, not "Did you mean: scan?"

- **clig.dev**: "Suggest corrected commands when users make typos"
- **Agent doc**: "Errors that teach — every failed interaction must answer what now?"

#### 4. No next-step suggestions after success
After a successful `mdscan scan`, no hint suggests running `check-links` or `coverage`.

- **clig.dev**: "Suggest commands users should run next to discover workflows"
- **Agent doc**: "Every output is a conversation turn, not a dead end"

### P1 — Important

#### 5. Exit codes not semantic enough
Exit code 1 used for both soft warnings (missing description) and structural issues (broken links). Agents can't distinguish severity without parsing text.

- **Agent doc**: "Avoid returning 1 for everything"
- **Decided schema**: 0=success, 1=soft warnings, 2=usage error, 3=structural issues

#### 6. No environment variable support
No `NO_COLOR`, no `MDSCAN_*`, no `DEBUG`.

- **clig.dev**: "Check general-purpose variables: NO_COLOR, DEBUG, EDITOR..."

#### 7. No `--quiet` / `-q` flag
No way to suppress stderr diagnostics. An agent that just wants the exit code is forced to read warnings.

- **clig.dev**: Standard flag `-q, --quiet`

#### 8. No `--verbose` / `--debug` flag
No way to get tracing/debug output when something is resolved unexpectedly.

- **clig.dev**: "Reserve debug output for verbose mode"

#### 9. No support link in help
Top-level `--help` has no GitHub URL or bug report path.

- **clig.dev**: "Provide a support path in top-level help"

#### 10. No pagination / `--limit`
`scan` on a large repo dumps everything. No `--limit` or `--offset`.

- **Agent doc**: "Offer truncation/pagination flags: --limit, --offset"
- Note: `--max-depth` exists and is good.

### P2 — Minor

#### 11. No `help` subcommand
`mdscan help scan` doesn't work, only `mdscan scan -h`.

- **clig.dev**: "Display help at -h, --help, and help subcommand"

#### 12. No color
`warn:`, `hint:`, `error:` prefixes would benefit from color (red/yellow/cyan).

- **clig.dev**: "Use color intentionally to highlight important items"
- **Decided**: Minimal color on prefixes, with `NO_COLOR` / `--no-color` support

#### 13. Text output not grep-friendly
Aligned columns with spaces. No `--plain` with tab separators.

- **clig.dev**: "Use --plain flag for plain, tabular text"

#### 14. `coverage` exit 1 is too strict
Any imperfection → exit 1. Partial coverage is normal for large projects.

- Subsumes into exit code refactoring (point 5)

#### 15. Verbose `fix:` messages
Multi-line suggestions cost tokens. Could be more concise.

- **Agent doc**: "Keep outputs short. Agents pay per token."

#### 16. No stdin support on `set-description`
Can't pipe description text via `-`. Forces shell quoting.

- **clig.dev**: "Support `-` to read from stdin"
- **Agent doc**: "Agents generate multi-line content more easily via stdin"
