# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-11-21

## Context

This project is built incrementally over several stages, and its purpose is learning. Decisions are discussed and compared before implementation. Without a record, the reasons behind a decision (and the alternatives rejected) are lost, and later changes risk undoing a decision without knowing why it was made.

## Decision

Record every significant architectural or business-rule decision as an **Architecture Decision Record** in `docs/decisions/`, using the template in [README.md](README.md).

A decision is "significant" when it:
- chooses between technologies or patterns,
- defines a business rule that affects metrics,
- is costly to reverse, or
- would surprise a new reader of the code.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Decisions only in commit messages / PR descriptions | Hard to find; no structure for alternatives and consequences |
| Decisions only inside the architecture documents | Documents describe the *current* state; the history of *why* it changed is lost |
| Wiki outside the repository | Not versioned with the code; does not travel with a clone |

## Consequences

- Positive: every decision is traceable, with context and alternatives; reviewing the ADR index explains the architecture quickly.
- Negative: small writing overhead per decision.
- ADRs are immutable: a change of decision creates a new ADR that supersedes the old one.

## References

- Michael Nygard, *Documenting Architecture Decisions* (2011)
- [adr.github.io](https://adr.github.io/)
