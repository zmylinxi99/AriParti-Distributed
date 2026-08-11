# Benchmark Lists

This directory stores benchmark path lists used by the recorded experiments.
The paths are relative benchmark identifiers, not local filesystem paths.

## Lists

`all/` contains the full benchmark lists currently tracked in this repository:

| Logic | File | Records |
| --- | --- | ---: |
| QF_LIA | `all/QF_LIA-all_list-13226.txt` | 13226 |
| QF_LRA | `all/QF_LRA-all_list-1753.txt` | 1753 |
| QF_NIA | `all/QF_NIA-all_list-25358.txt` | 25358 |
| QF_NRA | `all/QF_NRA-all_list-12134.txt` | 12134 |

`pure-conjunction/` contains filtered benchmark lists:

| Logic | File | Records |
| --- | --- | ---: |
| QF_LIA | `pure-conjunction/QF_LIA-pure_conjunction_list-4066.txt` | 4066 |
| QF_LRA | `pure-conjunction/QF_LRA-pure_conjunction_list-337.txt` | 337 |
| QF_NIA | `pure-conjunction/QF_NIA-pure_conjunction_list-1520.txt` | 1520 |
| QF_NRA | `pure-conjunction/QF_NRA-pure_conjunction_list-6034.txt` | 6034 |

`all/lists_list.txt` is a compact index of the four full benchmark lists.
`manifest.csv` provides the list metadata and the comparison with the frozen
SMT-LIB 2023 Zenodo collection in a machine-readable format.

## QF_NIA Provenance

The evaluated QF_NIA list contains 25,358 instances. It was prepared from the
SMT-LIB repository available when the experiments began and predates the later
frozen SMT-LIB 2023 Zenodo collection, which contains 25,443 QF_NIA instances.
Path-level comparison confirms that the evaluated list is a proper subset of
the frozen list: it has no local-only entries and omits 85 later archived
instances from two families.

See [QF_NIA-provenance.md](QF_NIA-provenance.md) for the source, counts,
family breakdown, integrity information, and interpretation. The complete
85-instance difference is stored in
[QF_NIA-frozen-2023-missing-from-experiment.txt](QF_NIA-frozen-2023-missing-from-experiment.txt).

## Maintenance Notes

- Keep the count in each filename consistent with the number of records in the file.
- When adding or regenerating a list, document the source benchmark suite and filtering rule in this file or in a companion metadata file.
- Use the manifest and companion metadata files as the provenance source for
  paper tables and figures.
