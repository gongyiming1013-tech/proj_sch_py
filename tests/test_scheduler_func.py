"""Tests for V0.1 function-based scheduler — written against the contract before implementation."""

import pytest

from src import scheduler_func
from src.scheduler import SequentialScheduler
from src.scheduler_func import CyclicDependencyError, SchedulerError, schedule


# ── helpers ──────────────────────────────────────────────────────────


def _assert_valid_order(
    result: list[str],
    dependencies: list[tuple[str, str]],
) -> None:
    """Assert every dependency pair is respected in the result order."""
    index = {name: i for i, name in enumerate(result)}
    for prereq, dependent in dependencies:
        assert index[prereq] < index[dependent], (
            f"Expected {prereq} before {dependent}, got order: {result}"
        )


# ── Core functionality ──────────────────────────────────────────────


class TestCoreFunctionality:
    """Valid topological ordering for acyclic graphs."""

    def test_linear_chain(self) -> None:
        """A -> B -> C should produce [A, B, C]."""
        projects = ["A", "B", "C"]
        deps = [("A", "B"), ("B", "C")]

        result = schedule(projects, deps)

        assert set(result) == set(projects)
        _assert_valid_order(result, deps)

    def test_diamond_dag(self) -> None:
        """Diamond: A -> B, A -> C, B -> D, C -> D."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]

        result = schedule(projects, deps)

        assert set(result) == set(projects)
        _assert_valid_order(result, deps)

    def test_multiple_independent_components(self) -> None:
        """Two disconnected chains: A->B and C->D."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("C", "D")]

        result = schedule(projects, deps)

        assert set(result) == set(projects)
        _assert_valid_order(result, deps)

    def test_single_project_no_deps(self) -> None:
        """Single project with no dependencies."""
        result = schedule(["A"], [])

        assert result == ["A"]

    def test_all_independent_projects(self) -> None:
        """All projects are independent — any permutation is valid."""
        projects = ["A", "B", "C"]

        result = schedule(projects, [])

        assert set(result) == set(projects)

    def test_example_from_spec(self) -> None:
        """The exact example from the project spec."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("B", "C"), ("A", "C")]

        result = schedule(projects, deps)

        assert set(result) == set(projects)
        _assert_valid_order(result, deps)


# ── Cycle detection ─────────────────────────────────────────────────


class TestCycleDetection:
    """Cyclic graphs must raise CyclicDependencyError."""

    def test_simple_two_node_cycle(self) -> None:
        """A -> B -> A."""
        with pytest.raises(CyclicDependencyError):
            schedule(["A", "B"], [("A", "B"), ("B", "A")])

    def test_three_node_cycle(self) -> None:
        """A -> B -> C -> A."""
        with pytest.raises(CyclicDependencyError):
            schedule(["A", "B", "C"], [("A", "B"), ("B", "C"), ("C", "A")])

    def test_self_dependency(self) -> None:
        """A depends on itself."""
        with pytest.raises(CyclicDependencyError):
            schedule(["A"], [("A", "A")])

    def test_cycle_within_larger_graph(self) -> None:
        """Cycle exists among B,C,D while A is independent."""
        with pytest.raises(CyclicDependencyError):
            schedule(
                ["A", "B", "C", "D"],
                [("B", "C"), ("C", "D"), ("D", "B")],
            )


# ── Edge cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    """Boundary and degenerate inputs."""

    def test_empty_project_list(self) -> None:
        """Empty input should return an empty list."""
        result = schedule([], [])

        assert result == []

    def test_duplicate_dependencies_are_tolerated(self) -> None:
        """Duplicate edges should not cause errors."""
        projects = ["A", "B"]
        deps = [("A", "B"), ("A", "B")]

        result = schedule(projects, deps)

        assert set(result) == set(projects)
        _assert_valid_order(result, deps)


# ── Input validation ────────────────────────────────────────────────


class TestInputValidation:
    """Malformed or inconsistent input."""

    def test_dependency_references_unknown_dependent(self) -> None:
        """A dependency pair mentions a dependent not in the project list."""
        with pytest.raises(SchedulerError):
            schedule(["A"], [("A", "X")])

    def test_dependency_prerequisite_unknown(self) -> None:
        """The prerequisite in a dependency is not in the project list."""
        with pytest.raises(SchedulerError):
            schedule(["B"], [("X", "B")])

    def test_local_exceptions_are_independent_of_v0(self) -> None:
        """V0.1 exceptions must be its own classes, not re-exports of V0."""
        from src.exceptions import (
            CyclicDependencyError as V0Cyclic,
            SchedulerError as V0Base,
        )

        assert SchedulerError is not V0Base
        assert CyclicDependencyError is not V0Cyclic


# ── Ordering correctness ───────────────────────────────────────────


class TestOrderingCorrectness:
    """Every dependency pair must be respected in the output."""

    def test_complex_dag_ordering(self) -> None:
        """Larger DAG with multiple dependency paths."""
        projects = ["A", "B", "C", "D", "E", "F"]
        deps = [
            ("A", "B"),
            ("A", "C"),
            ("B", "D"),
            ("C", "D"),
            ("D", "E"),
            ("F", "E"),
        ]

        result = schedule(projects, deps)

        assert set(result) == set(projects)
        _assert_valid_order(result, deps)

    def test_all_pairs_respected(self) -> None:
        """Verify ordering with a wide fan-out from one root."""
        projects = ["root", "a", "b", "c", "d"]
        deps = [("root", "a"), ("root", "b"), ("root", "c"), ("root", "d")]

        result = schedule(projects, deps)

        assert result[0] == "root"
        assert set(result) == set(projects)
        _assert_valid_order(result, deps)


# ── Equivalence with V0 (Option A — single sanity check) ────────────


class TestEquivalenceWithV0:
    """Cross-check V0 (OOD) and V0.1 (function-based) on a representative input."""

    def test_diamond_dag_both_implementations_produce_valid_order(self) -> None:
        """Diamond DAG fed to both implementations must yield valid topological orders."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]

        out_v0 = SequentialScheduler().schedule(projects, deps)
        out_v01 = scheduler_func.schedule(projects, deps)

        assert set(out_v0) == set(projects)
        assert set(out_v01) == set(projects)
        _assert_valid_order(out_v0, deps)
        _assert_valid_order(out_v01, deps)
