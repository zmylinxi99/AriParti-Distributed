# Mechanism-Comparison Results

This directory contains one maintained full-list p8/1200-second mechanism
archive under `full-list-p8-1200s/`. It preserves twelve
theory-by-configuration totals and eight Full-versus-Disabled aggregate
comparisons across the four arithmetic benchmark lists.

The current manuscript reports all eight Full-versus-Disabled comparisons,
covering BICP and clause reduction on QF_LRA, QF_LIA, QF_NRA, and QF_NIA.

The totals are in `summary.csv`, all eight comparisons are in `delta.csv`,
and the eight-row manuscript rendering is in `table.tex`.
`result-metadata.json` records the experimental scope and result semantics.
`source-provenance.json` and `SHA256SUMS` provide the derivation and integrity
chains.

This maintained release provides the aggregate result and audit layer for the
full-list study. Verify it from the repository root with:

```bash
(cd experiment-results/ablation/full-list-p8-1200s && sha256sum --check SHA256SUMS)
```

Positive solved-count and aggregate PAR-2 deltas favor the Full configuration.
See `full-list-p8-1200s/README.md` for the exact experimental scope, numerical
table, and validation procedure.
