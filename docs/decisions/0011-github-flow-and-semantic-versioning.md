# ADR-0011: GitHub Flow and semantic versioning

- **Status:** Accepted
- **Date:** 2026-11-22
- **Related:** [dataops-strategy.md](../dataops/dataops-strategy.md)

## Context

One developer, continuous delivery, a public GitHub repository and CI checks that must run before changes reach production.

## Decision

| Topic | Decision |
|---|---|
| Branching | **GitHub Flow**: protected `main`; short-lived branches `<type>/<description>`; changes only through pull requests with green CI |
| Merge | **Squash merge**: one Conventional Commit per PR on `main` |
| Commits | **Conventional Commits** (`feat`, `fix`, `docs`, `test`, `refactor`, `ci`, `chore`, `build`) with scopes per component |
| Versioning | **SemVer tags** with GitHub Releases: `v0.<stage>.0` per completed stage; `v1.0.0` when the clean-clone test passes |
| Visibility | **Public repository**, which enables branch protection on the free plan and gives unlimited GitHub Actions minutes for public repositories *(to be confirmed in the GitHub documentation before Stage 7)* |
| First commit | Stage 1 documentation committed directly to `main` (nothing to protect yet) |

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| GitFlow | Long-lived `develop` and `release` branches suit scheduled releases and large teams; overhead for one developer |
| Trunk-based without PRs | No CI gate before `main`; does not demonstrate the review process |
| Merge commits / rebase merge | Merge commits clutter the history; rebase keeps every work-in-progress commit |
| Private repository | Branch protection on private repositories requires a paid plan; Actions minutes are limited |

## Consequences

- Positive: a clean, readable history (one commit per change) and traceable versions per stage.
- Negative: nothing secret may ever be committed, because the repository is public. This is enforced by `.gitignore`, the review checklist and GitHub secret scanning.
