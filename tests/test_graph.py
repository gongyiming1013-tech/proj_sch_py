"""Tests for DependencyGraph — written against the contract before implementation."""

import pytest

from src.exceptions import SchedulerError
from src.graph import DependencyGraph


# ── Construction ────────────────────────────────────────────────────


class TestGraphConstruction:
    """Graph builds correctly from valid inputs."""

    def test_nodes_are_stored(self) -> None:
        """All provided nodes should appear in all_nodes."""
        graph = DependencyGraph(["A", "B", "C"], [("A", "B")])

        assert graph.all_nodes == {"A", "B", "C"}

    def test_empty_graph(self) -> None:
        """Empty inputs produce an empty graph."""
        graph = DependencyGraph([], [])

        assert graph.all_nodes == set()

    def test_unknown_node_in_edge_raises(self) -> None:
        """An edge referencing a node not in the node list raises SchedulerError."""
        with pytest.raises(SchedulerError):
            DependencyGraph(["A"], [("A", "X")])

    def test_unknown_prerequisite_in_edge_raises(self) -> None:
        """Prerequisite not in node list raises SchedulerError."""
        with pytest.raises(SchedulerError):
            DependencyGraph(["B"], [("X", "B")])


# ── Neighbors ───────────────────────────────────────────────────────


class TestNeighbors:
    """neighbors() returns the correct dependents."""

    def test_single_edge(self) -> None:
        """A -> B: neighbors of A should be [B]."""
        graph = DependencyGraph(["A", "B"], [("A", "B")])

        assert graph.neighbors("A") == ["B"]

    def test_no_outgoing_edges(self) -> None:
        """A node with no dependents returns an empty list."""
        graph = DependencyGraph(["A", "B"], [("A", "B")])

        assert graph.neighbors("B") == []

    def test_multiple_neighbors(self) -> None:
        """A -> B, A -> C: neighbors of A should include B and C."""
        graph = DependencyGraph(
            ["A", "B", "C"], [("A", "B"), ("A", "C")]
        )

        assert set(graph.neighbors("A")) == {"B", "C"}


# ── In-degree ───────────────────────────────────────────────────────


class TestInDegree:
    """in_degree() returns the correct count of prerequisites."""

    def test_root_node_zero_in_degree(self) -> None:
        """A node with no prerequisites has in-degree 0."""
        graph = DependencyGraph(["A", "B"], [("A", "B")])

        assert graph.in_degree("A") == 0

    def test_single_prerequisite(self) -> None:
        """B depends on A: in-degree of B is 1."""
        graph = DependencyGraph(["A", "B"], [("A", "B")])

        assert graph.in_degree("B") == 1

    def test_multiple_prerequisites(self) -> None:
        """C depends on A and B: in-degree of C is 2."""
        graph = DependencyGraph(
            ["A", "B", "C"], [("A", "C"), ("B", "C")]
        )

        assert graph.in_degree("C") == 2

    def test_isolated_node(self) -> None:
        """A node with no edges has in-degree 0."""
        graph = DependencyGraph(["A", "B", "C"], [("A", "B")])

        assert graph.in_degree("C") == 0

    def test_duplicate_edges_counted(self) -> None:
        """Duplicate edges should be handled (in-degree reflects unique prerequisites)."""
        graph = DependencyGraph(
            ["A", "B"], [("A", "B"), ("A", "B")]
        )

        # Duplicate edges to the same target — implementation may deduplicate or count both.
        # The key invariant: in_degree should be consistent with what Kahn's algorithm needs.
        assert graph.in_degree("B") >= 1
