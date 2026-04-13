"""Tests for SequentialScheduler — written against the contract before implementation."""

import pytest

from src.exceptions import CyclicDependencyError, SchedulerError
from src.scheduler import SequentialScheduler


@pytest.fixture
def scheduler() -> SequentialScheduler:
    """Provide a fresh SequentialScheduler instance."""
    return SequentialScheduler()


# ── helpers ──────────────────────────────────────────────────────────


def _assert_valid_order(
    result: list[str],
    dependencies: list[tuple[str, str]],
) -> None:
    """Assert every dependency pair is respected in the result order."""
    index = {name: i for i, name in enumerate(result)}
    for prereq, dependent in dependencies:
        assert index[prereq] < index[dependent], (
            f"Expected {prereq} before {dependent}, "
            f"got order: {result}"
        )


# ── Core functionality ──────────────────────────────────────────────


class TestCoreFunctionality:
    """Valid topological ordering for acyclic graphs."""

    def test_linear_chain(self, scheduler: SequentialScheduler) -> None:
        """A -> B -> C should produce [A, B, C]."""
        projects = ["A", "B", "C"]
        deps = [("A", "B"), ("B", "C")]

        result = scheduler.schedule(projects, deps)

        assert set(result) == set(projects)
        _assert_valid_order(result, deps)

    def test_diamond_dag(self, scheduler: SequentialScheduler) -> None:
        """Diamond: A -> B, A -> C, B -> D, C -> D."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]

        result = scheduler.schedule(projects, deps)

        assert set(result) == set(projects)
        _assert_valid_order(result, deps)

    def test_multiple_independent_components(
        self, scheduler: SequentialScheduler
    ) -> None:
        """Two disconnected chains: A->B and C->D."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("C", "D")]

        result = scheduler.schedule(projects, deps)

        assert set(result) == set(projects)
        _assert_valid_order(result, deps)

    def test_single_project_no_deps(
        self, scheduler: SequentialScheduler
    ) -> None:
        """Single project with no dependencies."""
        result = scheduler.schedule(["A"], [])

        assert result == ["A"]

    def test_all_independent_projects(
        self, scheduler: SequentialScheduler
    ) -> None:
        """All projects are independent — any permutation is valid."""
        projects = ["A", "B", "C"]

        result = scheduler.schedule(projects, [])

        assert set(result) == set(projects)

    def test_example_from_spec(self, scheduler: SequentialScheduler) -> None:
        """The exact example from the project spec."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("B", "C"), ("A", "C")]

        result = scheduler.schedule(projects, deps)

        assert set(result) == set(projects)
        _assert_valid_order(result, deps)


# ── Cycle detection ─────────────────────────────────────────────────


class TestCycleDetection:
    """Cyclic graphs must raise CyclicDependencyError."""

    def test_simple_two_node_cycle(
        self, scheduler: SequentialScheduler
    ) -> None:
        """A -> B -> A."""
        with pytest.raises(CyclicDependencyError):
            scheduler.schedule(["A", "B"], [("A", "B"), ("B", "A")])

    def test_three_node_cycle(
        self, scheduler: SequentialScheduler
    ) -> None:
        """A -> B -> C -> A."""
        with pytest.raises(CyclicDependencyError):
            scheduler.schedule(
                ["A", "B", "C"],
                [("A", "B"), ("B", "C"), ("C", "A")],
            )

    def test_self_dependency(
        self, scheduler: SequentialScheduler
    ) -> None:
        """A depends on itself."""
        with pytest.raises(CyclicDependencyError):
            scheduler.schedule(["A"], [("A", "A")])

    def test_cycle_within_larger_graph(
        self, scheduler: SequentialScheduler
    ) -> None:
        """Cycle exists among B,C,D while A is independent."""
        with pytest.raises(CyclicDependencyError):
            scheduler.schedule(
                ["A", "B", "C", "D"],
                [("B", "C"), ("C", "D"), ("D", "B")],
            )


# ── Edge cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    """Boundary and degenerate inputs."""

    def test_empty_project_list(
        self, scheduler: SequentialScheduler
    ) -> None:
        """Empty input should return an empty list."""
        result = scheduler.schedule([], [])

        assert result == []

    def test_duplicate_dependencies_are_tolerated(
        self, scheduler: SequentialScheduler
    ) -> None:
        """Duplicate edges should not cause errors."""
        projects = ["A", "B"]
        deps = [("A", "B"), ("A", "B")]

        result = scheduler.schedule(projects, deps)

        assert set(result) == set(projects)
        _assert_valid_order(result, deps)


# ── Input validation ────────────────────────────────────────────────


class TestInputValidation:
    """Malformed or inconsistent input."""

    def test_dependency_references_unknown_project(
        self, scheduler: SequentialScheduler
    ) -> None:
        """A dependency pair mentions a project not in the project list."""
        with pytest.raises(SchedulerError):
            scheduler.schedule(["A"], [("A", "X")])

    def test_dependency_prerequisite_unknown(
        self, scheduler: SequentialScheduler
    ) -> None:
        """The prerequisite in a dependency is not in the project list."""
        with pytest.raises(SchedulerError):
            scheduler.schedule(["B"], [("X", "B")])


# ── Ordering correctness ───────────────────────────────────────────


class TestOrderingCorrectness:
    """Every dependency pair must be respected in the output."""

    def test_complex_dag_ordering(
        self, scheduler: SequentialScheduler
    ) -> None:
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

        result = scheduler.schedule(projects, deps)

        assert set(result) == set(projects)
        _assert_valid_order(result, deps)

    def test_all_pairs_respected(
        self, scheduler: SequentialScheduler
    ) -> None:
        """Verify ordering with a wide fan-out from one root."""
        projects = ["root", "a", "b", "c", "d"]
        deps = [("root", "a"), ("root", "b"), ("root", "c"), ("root", "d")]

        result = scheduler.schedule(projects, deps)

        assert result[0] == "root"
        assert set(result) == set(projects)
        _assert_valid_order(result, deps)
