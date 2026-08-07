import sys
import time
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from partition_tree import (  # noqa: E402
    DistributedTree,
    NodeReason,
    NodeStatus,
    ParallelTree,
)


class ParallelFullUnsatTests(unittest.TestCase):
    def make_binary_tree(self):
        tree = ParallelTree(time.time())
        root = tree.make_node(0, -1)
        left = tree.make_node(1, 0)
        right = tree.make_node(2, 0)
        return tree, root, left, right

    def test_parent_requires_all_children_unsat(self):
        tree, root, left, right = self.make_binary_tree()

        tree.node_solved_unsat(left, NodeReason.partitioner)
        self.assertFalse(root.status.is_unsat())
        self.assertFalse(tree.is_done())

        tree.node_solved_unsat(right, NodeReason.partitioner)
        self.assertTrue(root.status.is_unsat())
        self.assertEqual(tree.get_result(), NodeStatus.unsat)

    def test_error_or_terminated_child_cannot_promote_parent(self):
        for inconclusive in (NodeStatus.error, NodeStatus.terminated):
            with self.subTest(inconclusive=inconclusive):
                tree, root, left, right = self.make_binary_tree()
                tree.node_solved_unsat(left, NodeReason.partitioner)
                tree.update_node_status(right, inconclusive, NodeReason.itself)

                tree.unsat_push_up(root)

                self.assertFalse(root.status.is_unsat())
                self.assertFalse(tree.is_done())

    def test_unsat_promotion_is_recursive(self):
        tree = ParallelTree(time.time())
        root = tree.make_node(0, -1)
        left = tree.make_node(1, 0)
        right = tree.make_node(2, 0)
        left_left = tree.make_node(3, 1)
        left_right = tree.make_node(4, 1)

        tree.node_solved_unsat(right, NodeReason.partitioner)
        tree.node_solved_unsat(left_left, NodeReason.partitioner)
        tree.node_solved_unsat(left_right, NodeReason.partitioner)

        self.assertTrue(left.status.is_unsat())
        self.assertTrue(root.status.is_unsat())
        self.assertEqual(tree.get_result(), NodeStatus.unsat)

    def test_explicit_partitioner_unsat_children_close_parent(self):
        tree, root, left, right = self.make_binary_tree()

        tree.node_solved_unsat(left, NodeReason.partitioner)
        tree.node_solved_unsat(right, NodeReason.partitioner)

        self.assertEqual(len(root.children), 2)
        self.assertTrue(all(child.status.is_unsat() for child in root.children))
        self.assertEqual(tree.get_result(), NodeStatus.unsat)

    def test_delegated_child_is_local_closure_not_unsat_proof(self):
        tree, root, delegated, retained = self.make_binary_tree()

        tree.set_node_split(delegated, assigned_coord=1)
        self.assertTrue(delegated.status.is_delegated())
        self.assertFalse(delegated.status.is_unsat())
        self.assertFalse(root.status.is_unsat())

        tree.node_solved_unsat(retained, NodeReason.partitioner)

        self.assertTrue(root.status.is_unsat())
        self.assertTrue(delegated.status.is_delegated())
        self.assertEqual(tree.get_result(), NodeStatus.unsat)

    def test_ancestor_unsat_does_not_overwrite_delegated_child(self):
        tree, root, delegated, retained = self.make_binary_tree()
        grandchild = tree.make_node(3, delegated.pid)

        tree.set_node_split(delegated, assigned_coord=1)
        tree.node_solved_unsat(retained, NodeReason.partitioner)

        self.assertTrue(root.status.is_unsat())
        self.assertTrue(delegated.status.is_delegated())
        self.assertFalse(grandchild.status.is_unsat())


class DistributedFullUnsatTests(unittest.TestCase):
    def make_migrated_tree(self):
        tree = DistributedTree(time.time())
        root = tree.make_node(None)
        tree.root = root
        migrated_child = tree.make_node(root)
        return tree, root, migrated_child

    def test_donor_and_migrated_child_are_both_required(self):
        tree, donor, migrated_child = self.make_migrated_tree()

        tree.node_partial_solved_unsat(donor)
        self.assertFalse(donor.status.is_unsat())
        self.assertFalse(tree.is_done())

        tree.node_partial_solved_unsat(migrated_child)
        self.assertTrue(migrated_child.status.is_unsat())
        self.assertTrue(donor.status.is_unsat())
        self.assertEqual(tree.get_result(), NodeStatus.unsat)

    def test_migrated_child_without_donor_unsat_cannot_close_root(self):
        tree, donor, migrated_child = self.make_migrated_tree()

        tree.node_partial_solved_unsat(migrated_child)

        self.assertTrue(migrated_child.status.is_unsat())
        self.assertFalse(donor.status.is_unsat())
        self.assertFalse(tree.is_done())

    def test_error_migrated_child_cannot_close_unsat_donor(self):
        tree, donor, migrated_child = self.make_migrated_tree()
        tree.update_node_status(migrated_child, NodeStatus.error, NodeReason.itself)

        tree.node_partial_solved_unsat(donor)

        self.assertFalse(donor.status.is_unsat())
        self.assertFalse(tree.is_done())


if __name__ == "__main__":
    unittest.main()
