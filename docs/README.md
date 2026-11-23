# Documentation Index

Start with the [project README](../README.md) for the overview, then follow the reading order below.

## Suggested reading order

| # | Document | Answers |
|---|---|---|
| 1 | [Business context](business/business-context.md) | Who is the company, what problem are we solving? |
| 2 | [Analytical requirements](business/analytical-requirements.md) | Which questions must the platform answer? |
| 3 | [Metrics definition](business/metrics-definition.md) | How exactly is Net Revenue calculated? |
| 4 | [Source systems](architecture/source-systems.md) | What do the operational systems look like? (ERDs) |
| 5 | [Analytical data model](architecture/data-model.md) | What is the star schema and why? (ERD) |
| 6 | [Architecture overview](architecture/architecture-overview.md) | Which components, where do they run, which risks? |
| 7 | [Data flow](architecture/data-flow.md) | How does data move through the layers and the pipeline? |
| 8 | [Data governance](governance/data-governance.md) | Who can see what, how is PII protected, how is quality tested? |
| 9 | [DataOps strategy](dataops/dataops-strategy.md) | How are changes developed, validated and deployed? |
| 10 | [Getting started](getting-started.md) | How do I run it on my machine? |
| 11 | [Architecture decisions](decisions/README.md) | Why was each decision taken? |
| — | [Legacy modernization study](modernization/legacy-migration.md) | How would a Talend/Informatica migration to this stack work? |

## By topic

| Topic | Documents |
|---|---|
| Business | [business/](business/) |
| Architecture and modeling | [architecture/](architecture/) · [diagrams/](diagrams/) |
| Governance | [governance/](governance/) |
| DataOps | [dataops/](dataops/) · [getting-started.md](getting-started.md) |
| Decisions | [decisions/](decisions/) |

## Diagrams

| Diagram | Where | Format |
|---|---|---|
| 1. Architecture overview | [architecture-overview.drawio.svg](diagrams/architecture-overview.drawio.svg) | diagrams.net (editable SVG) |
| 2. Logical data flow and governance points | [data-flow.md](architecture/data-flow.md#1-logical-data-flow-and-governance-points) | Mermaid |
| 3. Source systems ERD | [source-systems.md](architecture/source-systems.md) | Mermaid |
| 4. Analytical model ERD | [data-model.md](architecture/data-model.md#3-gold-layer-erd) | Mermaid |
| Order status lifecycle | [source-systems.md](architecture/source-systems.md#3-e-commerce-ecommerce) | Mermaid |
| Pipeline DAG | [data-flow.md](architecture/data-flow.md#3-orchestration-flow-daily-pipeline) | Mermaid |
| Branching and release flow | [dataops-strategy.md](dataops/dataops-strategy.md) | Mermaid |

**Editing diagrams.**
- Mermaid diagrams are text blocks inside the Markdown files. GitHub renders them automatically; in VS Code, use the "Markdown Preview Mermaid Support" extension.
- `.drawio.svg` files are regular SVG images that also contain the editable diagram. Open them in [diagrams.net](https://app.diagrams.net/) or with the VS Code "Draw.io Integration" extension, edit, and save: the image updates automatically.

**Logos.**
- Technology logos come from [Simple Icons](https://simpleicons.org/) (v16.38.1).
- dbt and Power BI are not available in Simple Icons, so they are shown as brand-colored labels.

## Documentation conventions

- Every document starts with its **status** and **last updated** date.
- Facts that depend on tools are linked to the official documentation.
- Planned logic is marked as such and confirmed in the stage that implements it.
- Decisions are recorded as ADRs, which are never edited after acceptance; superseding decisions create new ADRs.
