# Legacy ETL Modernization (Architectural Study)

> **Status:** Study document (Stage 1) · **Last updated:** 2026-11-22
>
> **Scope note.** This is an **architectural study**, not a migration that was carried out. No legacy tool (Talend, Informatica or similar) is implemented or simulated in this project. The document describes how a migration from a GUI-based ETL platform to the architecture of this project would be planned and validated.

## 1. Context

Many companies run their data integration on **GUI-based ETL platforms** such as Talend or Informatica PowerCenter. Typical characteristics of that generation:

| Characteristic | Consequence |
|---|---|
| **ETL**: data is transformed on an ETL server before loading | ETL server capacity limits volume; the warehouse is used only for storage |
| Logic built in a visual designer and stored in proprietary metadata (XML repositories) | Hard to review, diff and test; logic is invisible to version control |
| Business rules spread across mappings, expressions, lookups and SQL overrides | No single place defines a metric |
| Vendor scheduler or external scheduler with dependencies configured in the tool | Dependencies are implicit; impact analysis is manual |
| Testing mostly manual | Regressions are found by business users |
| Licensing per server / core / connector | Cost grows with volume |

## 2. Target architecture

This project's stack is a typical **target** for such a modernization: managed ingestion, ELT in a cloud warehouse, transformations as versioned SQL, and orchestration as code.

| Legacy concept | Modern equivalent in this project |
|---|---|
| Source / target connections | Airbyte connectors (sources, destination) |
| Extraction job | Airbyte connection with incremental sync |
| Mapping / job (transformation logic) | dbt models (SQL) |
| Expression / transformer components | SQL expressions in staging and intermediate models |
| Lookup | `join` to a dimension or reference model |
| Reusable mapplet / routine / joblet | dbt macro |
| SCD component | dbt snapshot + dimension model |
| Parameter files / context variables | dbt `vars`, environment variables, targets |
| Workflow / job sequence | Airflow DAG |
| Vendor scheduler | Airflow scheduling |
| Data quality component | dbt tests, source freshness |
| Repository (proprietary metadata) | Git |
| Deployment between environments (export/import) | CI/CD pipelines (GitHub Actions) |
| Lineage (if available, tool-specific) | dbt lineage graph (automatic, from `ref()` and `source()`) |

**ETL → ELT is a redesign, not a translation.** Re-creating every legacy step one by one in SQL reproduces the old complexity in a new tool. The migration should rebuild the logic around **layers** (staging, intermediate, marts) and **business entities**, using the legacy jobs as the specification of *what* must be produced, not *how*.

## 3. Migration approach

### Phase 1: Discovery

| Activity | Output |
|---|---|
| Export the legacy repository metadata (job definitions, mappings, connections) | Inventory of jobs, sources, targets |
| Parse dependencies between jobs and tables | Job dependency graph and table-level lineage |
| Collect execution history (frequency, duration, failures, volumes) | Usage and criticality data; unused jobs identified |
| Identify business rules embedded in expressions, lookups, filters and SQL overrides | Business rules catalog, reviewed with business owners |
| Identify consumers of each target table (reports, extracts, other systems) | Consumer map (who is affected by each change) |

Often a significant share of legacy jobs is **unused or redundant**. Discovery is also the moment to decommission them instead of migrating them.

### Phase 2: Assessment and planning

| Activity | Output |
|---|---|
| Score each job by complexity (number of steps, custom code, rules) and business criticality | Prioritized backlog |
| Group jobs into **migration waves** by business domain (e.g. "Sales", "Finance") | Wave plan |
| Define target conventions (naming, layers, testing standards, CI/CD) | Engineering standards |
| Define acceptance criteria for equivalence (tolerances, reconciliation queries) | Validation plan |

Waves are **vertical slices**: one domain migrated end to end (ingestion → models → consumers) before the next. This delivers value early and limits risk, following the **strangler fig** pattern: the new platform gradually replaces the old one, piece by piece.

### Phase 3: Incremental migration (per wave)

1. Build ingestion for the wave's sources into `RAW`.
2. Rebuild the logic as dbt models, with tests for every business rule from the catalog.
3. Point **no consumer** at the new tables yet.

### Phase 4: Parallel run and reconciliation

Both platforms run on the same inputs for an agreed period (e.g. a full month-end close). Outputs are compared automatically.

| Comparison level | Technique |
|---|---|
| Row counts | Per table, per partition (day/month) |
| Aggregates | Sums of key measures (e.g. Net Revenue by month and region) |
| Row level | Full outer join on business keys: rows only in legacy, only in new, and rows with differing values |
| Column level | Per-column match rates to locate the faulty rule quickly |

The dbt package **`audit_helper`** provides macros for these comparisons (`compare_relations`, `compare_column_values`, `compare_all_columns`).

**Every difference must be explained**:
- a **bug in the new logic**: fix it;
- a **bug in the legacy logic**: document it and get business sign-off for the corrected behavior;
- an **accepted difference** (rounding, timing): document the tolerance.

### Phase 5: Validation and sign-off

| Criterion | Example |
|---|---|
| Reconciliation within tolerance for N consecutive runs | Net Revenue per month matches to the cent for 3 consecutive closes |
| All documented differences signed off by the business owner | Finance approves the corrected return-date rule |
| Performance and SLA met | Data available before the start of the business day |
| Operations ready | Monitoring, alerting and runbooks in place |

### Phase 6: Cutover

1. Announce a change freeze on the legacy jobs of the wave.
2. Final synchronization and reconciliation.
3. **Switch consumers** (reports, extracts) to the new tables.
4. Keep legacy jobs running **in parallel, read-only**, for a stabilization period.
5. Decommission the legacy jobs after the stabilization period.

### Rollback

| Situation | Rollback |
|---|---|
| Problem found during the stabilization period | Point consumers back to the legacy tables, which were still being produced |
| Problem in the new logic after decommission | Normal platform rollback: `git revert`, redeploy, Time Travel ([dataops-strategy.md](../dataops/dataops-strategy.md#8-rollback)) |

Keeping both platforms producing outputs until sign-off is what makes the rollback **cheap**: it is a configuration switch for consumers, not a restore operation.

## 4. How this project demonstrates the target state

| Migration need | Where it is demonstrated |
|---|---|
| Business rules centralized and documented | [metrics-definition.md](../business/metrics-definition.md) + dbt Gold layer |
| Rules tested automatically | dbt tests, unit tests, reconciliation tests ([data-governance.md](../governance/data-governance.md#5-data-quality)) |
| Lineage available automatically | dbt docs lineage graph |
| Reconciliation between two outputs | Gold vs source reconciliation tests (DQ-05, DQ-06): the same technique used in a parallel run |
| Version control, code review, CI/CD | [dataops-strategy.md](../dataops/dataops-strategy.md) |
| Incremental processing and reprocessing | Incremental models and full refresh procedure ([data-model.md](../architecture/data-model.md#6-incremental-strategy-facts)) |

## 5. Common risks

| Risk | Mitigation |
|---|---|
| Undocumented rules hidden in SQL overrides or expressions | Systematic metadata parsing in Discovery; business review of the rules catalog |
| "Lift and shift": translating legacy steps one by one | Redesign by layers and entities; legacy jobs used as specification only |
| Legacy bugs reproduced to "match" | Reconciliation differences classified; corrected behavior signed off |
| Big-bang cutover | Waves by domain; parallel run; consumer switch per wave |
| Consumers forgotten (extracts, other systems) | Consumer map from Discovery; usage logs |
| Team skills gap (GUI → SQL, Git, CI/CD) | Engineering standards, templates, pair work in the first wave |
