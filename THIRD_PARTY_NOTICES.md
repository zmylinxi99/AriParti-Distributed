# Third-Party Executables and Notices

The AriParti-Distributed project is licensed separately under `LICENSE.txt`.
The Linux x86-64 artifact also contains the unmodified third-party executables
listed below. These executables remain under their respective upstream
copyrights and licenses; the AriParti-Distributed license does not replace or
restrict those terms.

## Redistributed backend executables

| Artifact file | Upstream release asset | Provenance check | SHA-256 | License |
| --- | --- | --- | --- | --- |
| `linux-pre_built/binaries/cvc5-1.0.8-bin` | [`cvc5-Linux` from cvc5 1.0.8](https://github.com/cvc5/cvc5/releases/download/cvc5-1.0.8/cvc5-Linux) | Byte-for-byte identical to the upstream asset | `fe74a3ae70462d715871918c6277c88b10a1335ab55ecfb53a10ff5aa501d20a` | Modified BSD; see `third-party-licenses/cvc5-1.0.8-COPYING` and the dependency notices below |
| `linux-pre_built/binaries/opensmt-2.5.2-bin` | [`opensmt` in the OpenSMT2 2.5.2 Linux archive](https://github.com/usi-verification-and-security/opensmt/releases/download/v2.5.2/opensmt-2.5.2-x64-linux.tar.bz2) | Byte-for-byte identical to the executable extracted from the upstream archive | `58461438f02fa0cc8f5bf2370c6d122a66e3dfff53fbd452eb4e17481f8e9a5b` | MIT; see `third-party-licenses/opensmt-2.5.2-LICENSE` |
| `linux-pre_built/binaries/z3-4.12.1-bin` | [`bin/z3` in the official Z3 4.12.1 manylinux1 wheel](https://github.com/Z3Prover/z3/releases/download/z3-4.12.1/z3_solver-4.12.1.0-py2.py3-none-manylinux1_x86_64.whl) | Extracted without modification from the upstream release asset | `b14068b578fe6f2ad90d46183ba73b1c4ee071de8caccc455b9fcc6d3eb1d320` | MIT; see `third-party-licenses/z3-4.12.1-LICENSE.txt` |

The SHA-256 values of the downloaded OpenSMT2 and Z3 release assets used for
the provenance comparison are respectively:

- `eb3d691489ef1a951dbf7eba9a8373ecf37ba2302cd99825ff1eea97ea671d62`
  (`opensmt-2.5.2-x64-linux.tar.bz2`)
- `41cb9ac460af30b193811eebf919d61cf51a8856bbd74b200cbe6b21e3e955e4`
  (`z3_solver-4.12.1.0-py2.py3-none-manylinux1_x86_64.whl`)

The machine-readable executable checksums are in
`third-party-licenses/SHA256SUMS` and are checked by the test suite.
They can also be verified directly from the repository root with:

```bash
(cd linux-pre_built/binaries && sha256sum --check ../../third-party-licenses/SHA256SUMS)
```

## Copyright notices

- cvc5 is copyright 2009--2023 by the cvc5 authors, contributors, and their
  institutional affiliations. The modified BSD notice and disclaimer are
  reproduced verbatim in `third-party-licenses/cvc5-1.0.8-COPYING`.
- OpenSMT2 2.5.2 is copyright 2008--2012 Roberto Bruttomesso and 2012--2020
  Antti Hyvarinen. Its MIT notice is reproduced verbatim in
  `third-party-licenses/opensmt-2.5.2-LICENSE`.
- Z3 is copyright Microsoft Corporation. Its MIT notice is reproduced verbatim
  in `third-party-licenses/z3-4.12.1-LICENSE.txt`.

No upstream project or contributor endorses AriParti-Distributed.

## cvc5 linked components

The redistributed cvc5 file is the unmodified official 1.0.8 Linux release
asset. Its `--version` output reports static linkage with CaDiCaL, Editline,
SymFPU, GMP, and LibPoly. The cvc5 1.0.8 `COPYING` file describes the applicable
third-party terms. This artifact additionally preserves the following notices:

- `cvc5-1.0.8-LGPL-3.0.txt`: LGPLv3 text referenced for GMP and LibPoly;
- `cvc5-1.0.8-MiniSat-LICENSE`: MiniSat code incorporated in cvc5;
- `cvc5-1.0.8-CaDiCaL-LICENSE`: CaDiCaL `rel-1.5.2` license;
- `cvc5-1.0.8-SymFPU-LICENSE`: SymFPU license at the commit selected by the
  cvc5 1.0.8 build configuration;
- `cvc5-1.0.8-LibPoly-LICENCE`: LibPoly 0.1.13 license; and
- `cvc5-1.0.8-Editline-LICENSE`: `COPYING` from the official Editline 20230828
  source archive. The cvc5 release asset identifies Editline but does not encode
  the exact system-package revision used by its upstream build.

Corresponding upstream source locations used by the cvc5 1.0.8 build
configuration are:

- [cvc5 1.0.8 source](https://github.com/cvc5/cvc5/tree/cvc5-1.0.8)
- [CaDiCaL rel-1.5.2](https://github.com/arminbiere/cadical/tree/rel-1.5.2)
- [SymFPU commit e6ac3af9](https://github.com/cvc5/symfpu/tree/e6ac3af9c2c574498ea171c957425b407625448b)
- [GMP 6.2.1 source selected by cvc5](https://github.com/cvc5/cvc5-deps/blob/main/gmp-6.2.1.tar.bz2)
- [LibPoly 0.1.13](https://github.com/SRI-CSL/libpoly/tree/v0.1.13)
- [Editline 20230828 source archive](https://thrysoee.dk/editline/libedit-20230828-3.1.tar.gz)

Users who modify or further redistribute these executables are responsible for
complying with the applicable upstream terms, including the LGPL provisions
described by cvc5 for its linked components.

## OpenSMT2 linked components

The redistributed OpenSMT2 executable is the unmodified statically linked file
from the official 2.5.2 Linux release archive. The OpenSMT2 2.5.2 source uses
GMP and incorporates MiniSat code. This artifact therefore also preserves:

- `cvc5-1.0.8-LGPL-3.0.txt`: the LGPLv3 text applicable to the redistributed
  GMP component (the license text is not cvc5-specific despite the filename);
  and
- `opensmt-2.5.2-MiniSat-LICENSE`: the MiniSat copyright and MIT notice from
  the OpenSMT2 2.5.2 source tree.

The corresponding OpenSMT2 source is available from the immutable
[OpenSMT2 2.5.2 tag](https://github.com/usi-verification-and-security/opensmt/tree/v2.5.2).
The upstream binary and release metadata do not encode the exact GMP package
revision used to produce that static build.

## AriParti partitioner

`linux-pre_built/binaries/partitioner-bin` is an AriParti-Distributed component
built from the Z3-derived source under `src/partitioner/`. Its SHA-256 value is
`17f871c5afb70bdbfced171c2d1c5983f33557f7010709eae1ecd761594320f7`.
The embedded Z3 license is preserved at `src/partitioner/LICENSE.txt`.
