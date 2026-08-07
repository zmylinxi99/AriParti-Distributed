import importlib.util
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


def load_prebuilt_partition_tree():
    module_path = PREBUILT_DIR / "partition_tree.py"
    spec = importlib.util.spec_from_file_location(
        "ariparti_prebuilt_partition_tree", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PrebuiltPackageTests(unittest.TestCase):
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
