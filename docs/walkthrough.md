# Following the correction

Reedglass Compute operates the fictional Lantern Yard data centre. Both [statements](../fixtures) describe the same fiscal year ending **2030-12-31**. All dates below are synthetic UTC fixture times. The clock on the machine running Docker has no bearing on the replay.

| Version | Published | Acquired | Reviewed | Promoted | Capex |
| --- | --- | --- | --- | --- | --- |
| 1 | Jan 2, 2031 | Jan 4 | Jan 5 | Jan 5 | $12m |
| 2 | Jan 8, 2031 | Jan 11 | Jan 11 | Jan 12 | $15m |

At a Jan 3 cutoff the first document has been published. At Jan 4 the archive has it, but there is still no approved financial fact. By Jan 6 the first fact is available. On Jan 11 the system has acquired and reviewed the correction, yet the first fact still applies. At precisely Jan 12 the new fact replaces it. The preserved intervals are `[Jan 5, Jan 12)` and `[Jan 12, ∞)`.

## From bytes to a response

1. `python -m demo` calls `statement` with a versioned fixture. `LocalObjectStore.put` hashes the bytes, uses a write-once key and detects conflicting contents. The extractor identifies the issuer, fiscal period and one quoted numeric line.
2. `ingest` locks the subject row, writes a document and proposal, and rejects conflicting version metadata on a retry. An extractor could misinterpret text even when its output is well formed. The proposal therefore has no standing in a historical financial query.
3. `approve` checks the reviewer role, reopens the artifact by digest, checks the cited value and units, and records the review time. `promote` independently requires approval and revalidates the proposal. It uses PostgreSQL's clock for promotion time unless the fixture supplies its simulated promotion time. At that instant it closes the previous interval and inserts the replacement within the caller's transaction. The demo scripts the analyst decision. There is no interactive reviewer or identity provider.
4. `ScenarioService.run` selects an admissible fact and normalises its units. It stores the scenario, percentage shock, formula, dollar result and source fact ID. A missing baseline raises an error. The demo rolls back that attempted run in a savepoint.
5. The CLI prints each response with the input fact ID. The two +10% scenarios give **$13.2m** and **$16.5m**. Replaying Jan 6 after Jan 12 still gives $13.2m. Treating the correction as known on Jan 6 would let later information improve the historical analysis.

## Storage relationships

```text
artifact ← sha256 ─ document(version, subject, published_at, acquired_at)
                       │
                    proposal(fragment, metric, amount, unit)
                       │
                    approval(reviewer_id, reviewed_at)
                       │
financial_period ─ financial_fact(value, unit, known_from, known_to)
financial_metric ─────┘                │                   │
                         scenario_output.source_id    frozen_input JSON
scenario ── scenario_shock / scenario_output               + digest
```

Document, proposal, approval and frozen input rows reject updates and deletes. A fact can close its knowledge interval once. PostgreSQL also rejects overlapping intervals for one fiscal period and metric. The archive and database have separate durability boundaries. Rolling back an ingestion may leave unreferenced immutable bytes, safely reusable on retry. The database owner remains trusted.

## Freeze before observing an outcome

The manifest names the target (next fiscal year's capex), horizon, methodology version, UTC cutoff and sorted fact IDs with source digests. The horizon includes the full UTC day of December 31, 2031. The service rejects cutoffs at or after midnight UTC on January 1, 2032. The digest identifies selected inputs and does not attest when they were frozen. The input fingerprint printed by this fixture is `93a0bc303c4dffb0088bbf01d4ec14572e483c526bae0219d4a662241fbb5e54`. The correction produces another admissible input at the later cutoff and leaves the earlier manifest intact. Freezing these references lets an evaluator later distinguish the evidence originally available from information learned afterward. This demo stops at input selection. It issues no prediction and never stores an outcome in a manifest.

A separate synthetic supplier example passes an unknown share directly to the rule without querying an exposure record. It asks what a revenue change would mean for a related supplier whose revenue share is undocumented. The rule returns `UNKNOWN_EXPOSURE_VALUE`. A documented zero would support a zero result. An unknown share supports no numeric result at all.
