# Full-List p8/1200-Second Mechanism-Ablation Evidence

This directory preserves the complete, validated aggregate results for the
full-list mechanism-ablation campaigns. Both `delta.csv` and `table.tex` cover
all eight Full-versus-Disabled comparisons formed by four benchmark theories
and two mechanisms.

This directory is the aggregate and audit bundle for the study. Its release
scope is aggregate-level; per-instance campaign logs are outside this bundle.

## Experimental Scope

- benchmark lists: QF_LRA (1,753), QF_LIA (13,226), QF_NIA (25,358), and
  QF_NRA (12,134)
- eight cores per benchmark instance
- 1,200-second timeout
- one recorded run per benchmark instance and configuration
- backend solvers: OpenSMT2 2.5.2 for QF_LRA/QF_LIA, Z3 4.12.1 for QF_NIA,
  and cvc5 1.0.8 for QF_NRA

The bundle records the launcher identity as
`linux-pre_built/AriParti_launcher.py` (SHA-256
`26a7f57c66f6361a60a78048abb55c3eb436675094f4115684905dee2a6e3443`), and
the partitioner identity as `linux-pre_built/binaries/partitioner-bin`
(SHA-256
`17f871c5afb70bdbfced171c2d1c5983f33557f7010709eae1ecd761594320f7`).
All twelve rows in `summary.csv` use these identities; the
`required_partitioner_sha256` field is identical to `partitioner_sha256`.

The `no_bicp` variant disables Boolean clause propagation,
Boolean-activated arithmetic constraints, and BICP-derived facts while
retaining arithmetic interval contraction. The `no_clause_reduction` variant
disables theory-level clause reduction. The original formula constraints and
partition-path bounds remain present in both variants.

## Complete Results

| Theory | Disabled mechanism | Full solved | Disabled solved | Solved advantage | Full PAR-2 | Disabled PAR-2 | PAR-2 advantage |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QF_LRA | BICP | 1,723 | 1,720 | 3 | 98,686 | 109,876 | 11,190 |
| QF_LRA | Clause reduction | 1,723 | 1,722 | 1 | 98,686 | 100,619 | 1,933 |
| QF_LIA | BICP | 12,881 | 12,483 | 398 | 1,432,372 | 2,542,383 | 1,110,011 |
| QF_LIA | Clause reduction | 12,881 | 12,554 | 327 | 1,432,372 | 2,338,220 | 905,848 |
| QF_NIA | BICP | 20,787 | 20,382 | 405 | 11,544,246 | 12,690,780 | 1,146,534 |
| QF_NIA | Clause reduction | 20,787 | 20,520 | 267 | 11,544,246 | 12,320,757 | 776,511 |
| QF_NRA | BICP | 11,541 | 11,448 | 93 | 1,496,897 | 1,724,833 | 227,936 |
| QF_NRA | Clause reduction | 11,541 | 11,533 | 8 | 1,496,897 | 1,513,858 | 16,961 |

`Solved advantage` is `Full solved - Disabled solved`. `PAR-2 advantage` is
`Disabled PAR-2 - Full PAR-2`. Positive values favor Full. PAR-2 values are
aggregate sums in seconds over the corresponding complete benchmark list.

## Result Files

- `summary.csv`: all twelve theory-by-configuration totals
- `delta.csv`: all eight Full-versus-Disabled aggregate comparisons
- `table.tex`: all eight mechanism-ablation comparisons reported in the
  manuscript
- `paired-solved-set.csv`: benchmark identities behind solved-set differences
- `status-distribution.csv`: recorded status counts
- `metadata-audit.csv`, `config-audit.csv`, and `consistency-audit.csv`:
  validation outputs for the campaign data
- `result-metadata.json`: machine-readable result scope and semantics
- `source-provenance.json`: hashes of the immutable intake files from which the
  compact public bundle was derived

`table.tex` is generated from all eight validated comparison rows.

Verify the result files from the repository root with:

```bash
(cd experiment-results/ablation/full-list-p8-1200s && sha256sum --check SHA256SUMS)
```
