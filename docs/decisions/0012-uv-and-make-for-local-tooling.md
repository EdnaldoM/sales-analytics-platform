# ADR-0012: uv and Make for local tooling

- **Status:** Accepted
- **Date:** 2026-11-22
- **Related:** [getting-started.md](../getting-started.md)

## Context

The project must run identically on a second computer. Python tools (data generator, dbt, linters, tests) need the **same Python version and the same dependency versions** everywhere. The commands to operate the platform should be easy to discover and identical across machines.

## Decision

1. **uv** manages Python versions, virtual environments and dependencies:
   - `.python-version` pins the Python version (uv downloads it if missing);
   - `pyproject.toml` declares direct dependencies;
   - **`uv.lock`** records the exact resolved versions (including transitive dependencies, with hashes) and is committed;
   - `uv sync` recreates an identical `.venv` on any machine.
2. **GNU Make** is the command entry point: a `Makefile` exposes short, documented targets (`make setup`, `make up`, `make seed`, `make dbt-build`, `make help`).

## Alternatives considered

| Alternative | Pros | Cons | Why not chosen |
|---|---|---|---|
| pip + `requirements.txt` | Universal | No Python version management; `pip freeze` is manual and error-prone; no lockfile with hashes by default | Weaker reproducibility |
| Poetry | Mature lockfile | Slower; no Python version management; another install | uv covers more with one tool |
| pyenv + venv + pip-tools | Flexible | Three tools to install and explain | More moving parts |
| Plain shell scripts instead of Make | No new syntax | No dependency between steps; no built-in discovery | Make gives targets, dependencies and `make help` for free |
| `just` / Taskfile | Nicer syntax | Extra installation on every machine | Make is already available on Ubuntu |

## Consequences

- Positive: `uv sync` gives a reproducible environment in seconds; `make help` documents the operations; both are fast to explain.
- Negative: Make has syntax pitfalls (recipe lines must start with a **tab**) and is not native on Windows. Not a problem here, because everything runs in WSL.

## References

- [uv documentation](https://docs.astral.sh/uv/)
- [GNU Make manual](https://www.gnu.org/software/make/manual/)
