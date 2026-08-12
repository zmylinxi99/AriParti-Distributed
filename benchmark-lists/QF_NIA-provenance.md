# QF_NIA Benchmark Provenance

The QF_NIA experiments in the associated manuscript use the recorded
25,358-instance list in `all/QF_NIA-all_list-25358.txt`. This list was prepared
from the SMT-LIB repository available when the experiments began, before the
SMT-LIB 2023 collection was frozen and published on Zenodo.

The later [SMT-LIB 2023 Zenodo record](https://zenodo.org/records/10607722)
contains 25,443 non-incremental QF_NIA instances. An exact comparison of the
benchmark path identifiers found that the evaluated list is a proper subset of
the frozen list:

| Set comparison | Instances |
| --- | ---: |
| Evaluated list | 25,358 |
| Frozen SMT-LIB 2023 list | 25,443 |
| Frozen list minus evaluated list | 85 |
| Evaluated list minus frozen list | 0 |

The 85 archive-only instances belong to two benchmark families:

| Benchmark family | Archive-only instances |
| --- | ---: |
| `20230321-UltimateAutomizerSvcomp2023` | 58 |
| `20230328-sqrtmodinv-hoenicke` | 27 |
| **Total** | **85** |

Their complete path list is
`QF_NIA-frozen-2023-missing-from-experiment.txt`. The difference reflects the
repository snapshot used to prepare the experiments; it was not produced by
filtering benchmarks after observing solver results. All QF_NIA results in the
manuscript are reported over the recorded 25,358-instance experimental list,
not over the later 25,443-instance frozen collection.

## Integrity Information

The following SHA-256 values identify the exact lists used in the comparison:

| Material | SHA-256 |
| --- | --- |
| Evaluated list, `all/QF_NIA-all_list-25358.txt` | `7081c15d27bf719b117da13e3991b21dc6198fad2017563b7513bb718f4521dc` |
| Retained path list extracted from the frozen archive | `3195d36e6aa0404665a5c3371fe4e19324df344461e78f1638907f6ddae787c0` |
| Published 85-instance difference list | `7afe950dd9f8a4dbd452ff1e1609cbc4d151f4d33c63175ba21ee8f8e725eb1b` |

The full frozen archive is not duplicated in this artifact; it remains
available from the Zenodo record above.
