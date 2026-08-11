import importlib.util
import hashlib
import time
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
PREBUILT_DIR = PROJECT_ROOT / "linux-pre_built"
PYTHON_SCRIPTS = (
    "AriParti_launcher.py",
    "control_message.py",
    "coordinator.py",
    "dispatcher.py",
    "leader.py",
    "partitioner.py",
    "partition_tree.py",
)
PREBUILT_BINARIES = (
    "cvc5-1.0.8-bin",
    "opensmt-2.5.2-bin",
    "partitioner-bin",
    "z3-4.12.1-bin",
)
THIRD_PARTY_LICENSE_FILES = (
    "cvc5-1.0.8-COPYING",
    "cvc5-1.0.8-LGPL-3.0.txt",
    "cvc5-1.0.8-MiniSat-LICENSE",
    "cvc5-1.0.8-CaDiCaL-LICENSE",
    "cvc5-1.0.8-SymFPU-LICENSE",
    "cvc5-1.0.8-LibPoly-LICENCE",
    "cvc5-1.0.8-Editline-LICENSE",
    "opensmt-2.5.2-LICENSE",
    "opensmt-2.5.2-MiniSat-LICENSE",
    "z3-4.12.1-LICENSE.txt",
)


def load_prebuilt_partition_tree():
    module_path = PREBUILT_DIR / "partition_tree.py"
    spec = importlib.util.spec_from_file_location(
        "ariparti_prebuilt_partition_tree", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PrebuiltPackageTests(unittest.TestCase):
    def test_project_license_covers_distribution_policy(self):
        license_text = (PROJECT_ROOT / "LICENSE.txt").read_text(encoding="utf-8")

        self.assertIn("MIT License", license_text)
        self.assertIn("redistributes unmodified backend SMT solver", license_text)
        self.assertIn("THIRD_PARTY_NOTICES.md", license_text)

    def test_prebuilt_package_contains_only_documented_binaries(self):
        binaries_dir = PREBUILT_DIR / "binaries"
        packaged_files = {path.name for path in binaries_dir.iterdir() if path.is_file()}

        self.assertEqual(
            packaged_files,
            set(PREBUILT_BINARIES),
            "prebuilt binaries and the audited distribution manifest disagree",
        )

    def test_prebuilt_binary_checksums(self):
        checksum_path = PROJECT_ROOT / "third-party-licenses" / "SHA256SUMS"
        expected = {}
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            digest, filename = line.split(maxsplit=1)
            expected[filename] = digest

        self.assertEqual(set(expected), set(PREBUILT_BINARIES))
        for filename, expected_digest in expected.items():
            with self.subTest(filename=filename):
                actual_digest = hashlib.sha256(
                    (PREBUILT_DIR / "binaries" / filename).read_bytes()
                ).hexdigest()
                self.assertEqual(actual_digest, expected_digest)

    def test_third_party_license_files_are_present(self):
        license_dir = PROJECT_ROOT / "third-party-licenses"
        for filename in THIRD_PARTY_LICENSE_FILES:
            with self.subTest(filename=filename):
                self.assertTrue((license_dir / filename).is_file())

    def test_python_scripts_match_current_source(self):
        for script in PYTHON_SCRIPTS:
            with self.subTest(script=script):
                self.assertEqual(
                    (PREBUILT_DIR / script).read_bytes(),
                    (SRC_DIR / script).read_bytes(),
                    f"linux-pre_built/{script} is stale; refresh it from src/{script}",
                )

    def test_delegated_node_is_not_an_unsat_proof(self):
        partition_tree = load_prebuilt_partition_tree()
        tree = partition_tree.ParallelTree(time.time())
        root = tree.make_node(0, -1)
        delegated = tree.make_node(1, 0)
        tree.make_node(2, 0)

        tree.set_node_split(delegated, assigned_coord=1)

        self.assertTrue(delegated.status.is_delegated())
        self.assertFalse(delegated.status.is_unsat())
        self.assertFalse(root.status.is_unsat())
        self.assertFalse(tree.is_done())


if __name__ == "__main__":
    unittest.main()
