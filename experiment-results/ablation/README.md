# Mechanism-Comparison Results

`full-list-p8-1200s/` contains the p8/1200-second results for the manuscript's
BICP and clause-reduction comparisons. It covers QF_LRA, QF_LIA, QF_NRA, and
QF_NIA with twelve theory-by-configuration totals and eight
Full-versus-Disabled comparisons.

The totals are in `summary.csv`, all eight comparisons are in `delta.csv`,
and the eight-row manuscript rendering is in `table.tex`.
`result-metadata.json` records the experimental scope and result semantics.
`source-provenance.json` identifies the evaluated implementation, and
`SHA256SUMS` covers the published files.

Verify the bundle from the repository root with:

```bash
(cd experiment-results/ablation/full-list-p8-1200s && sha256sum --check SHA256SUMS)
```

Positive solved-count and aggregate PAR-2 deltas favor the Full configuration.
See `full-list-p8-1200s/README.md` for the experimental scope, numerical
table, and validation procedure.
