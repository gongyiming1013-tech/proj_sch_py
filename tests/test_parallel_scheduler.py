"""Tests for V1 ParallelScheduler — written against the contract before implementation."""

import pytest

from src.exceptions import CyclicDependencyError, SchedulerError
from src.parallel_scheduler import ParallelScheduler


@pytest.fixture
def scheduler() -> ParallelScheduler:
    """Provide a fresh ParallelScheduler instance."""
    return ParallelScheduler()


# ── helpers ──────────────────────────────────────────────────────────


def _assert_valid_level_plan(
    plan: list[list[str]],
    projects: list[str],
    dependencies: list[tuple[str, str]],
) -> None:
    """Assert every project appears exactly once and deps cross levels correctly."""
    flat = [p for level in plan for p in level]
    assert set(flat) == set(projects), (
        f"Plan projects {set(flat)} != expected {set(projects)}"
    )
    assert len(flat) == len(projects), (
        f"Plan has duplicates or missing entries: {flat}"
    )

    level_of = {p: i for i, level in enumerate(plan) for p in level}
    for prereq, dependent in dependencies:
        assert level_of[prereq] < level_of[dependent], (
            f"Expected {prereq} before {dependent}, "
            f"got levels {level_of[prereq]} vs {level_of[dependent]} in {plan}"
        )


def _assert_maximal_parallelism(
    plan: list[list[str]],
    projects: list[str],
    dependencies: list[tuple[str, str]],
) -> None:
    """Assert every project is at the earliest level its prerequisites allow.

    Level of a project = max(level of its prerequisites) + 1, or 0 if none.
    """
    level_of = {p: i for i, level in enumerate(plan) for p in level}
    prereqs_of: dict[str, list[str]] = {p: [] for p in projects}
    for prereq, dependent in dependencies:
        prereqs_of[dependent].append(prereq)

    for project in projects:
        if not prereqs_of[project]:
            expected = 0
        else:
            expected = max(level_of[q] for q in prereqs_of[project]) + 1
        assert level_of[project] == expected, (
            f"Project {project} should be at level {expected}, "
            f"got {level_of[project]} in {plan}"
        )


# ── Core functionality ──────────────────────────────────────────────


class TestCoreFunctionality:
    """Valid level-grouped plans for acyclic graphs."""

    def test_linear_chain(self, scheduler: ParallelScheduler) -> None:
        """A -> B -> C should produce three singleton levels."""
        projects = ["A", "B", "C"]
        deps = [("A", "B"), ("B", "C")]

        plan = scheduler.schedule_parallel(projects, deps)

        assert plan == [["A"], ["B"], ["C"]]
        _assert_valid_level_plan(plan, projects, deps)

    def test_diamond_dag(self, scheduler: ParallelScheduler) -> None:
        """Diamond: A -> {B,C} -> D should put B and C in the same level."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]

        plan = scheduler.schedule_parallel(projects, deps)

        assert len(plan) == 3
        assert plan[0] == ["A"]
        assert set(plan[1]) == {"B", "C"}
        assert plan[2] == ["D"]
        _assert_valid_level_plan(plan, projects, deps)
        _assert_maximal_parallelism(plan, projects, deps)

    def test_multiple_independent_components(
        self, scheduler: ParallelScheduler
    ) -> None:
        """Two disconnected chains: A->B and C->D — levels should overlap."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("C", "D")]

        plan = scheduler.schedule_parallel(projects, deps)

        assert len(plan) == 2
        assert set(plan[0]) == {"A", "C"}
        assert set(plan[1]) == {"B", "D"}
        _assert_valid_level_plan(plan, projects, deps)
        _assert_maximal_parallelism(plan, projects, deps)

    def test_single_project_no_deps(
        self, scheduler: ParallelScheduler
    ) -> None:
        """Single project produces a single-level, single-project plan."""
        plan = scheduler.schedule_parallel(["A"], [])

        assert plan == [["A"]]

    def test_all_independent_projects(
        self, scheduler: ParallelScheduler
    ) -> None:
        """All projects are independent — one level containing all."""
        projects = ["A", "B", "C"]

        plan = scheduler.schedule_parallel(projects, [])

        assert len(plan) == 1
        assert set(plan[0]) == {"A", "B", "C"}

    def test_example_from_spec(
        self, scheduler: ParallelScheduler
    ) -> None:
        """Spec example: projects=[A,B,C,D], deps A->B, B->C, A->C."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("B", "C"), ("A", "C")]

        plan = scheduler.schedule_parallel(projects, deps)

        _assert_valid_level_plan(plan, projects, deps)
        _assert_maximal_parallelism(plan, projects, deps)


# ── Cycle detection ─────────────────────────────────────────────────


class TestCycleDetection:
    """Cyclic graphs must raise CyclicDependencyError."""

    def test_simple_two_node_cycle(
        self, scheduler: ParallelScheduler
    ) -> None:
        """A -> B -> A."""
        with pytest.raises(CyclicDependencyError):
            scheduler.schedule_parallel(["A", "B"], [("A", "B"), ("B", "A")])

    def test_three_node_cycle(
        self, scheduler: ParallelScheduler
    ) -> None:
        """A -> B -> C -> A."""
        with pytest.raises(CyclicDependencyError):
            scheduler.schedule_parallel(
                ["A", "B", "C"],
                [("A", "B"), ("B", "C"), ("C", "A")],
            )

    def test_self_dependency(
        self, scheduler: ParallelScheduler
    ) -> None:
        """A depends on itself."""
        with pytest.raises(CyclicDependencyError):
            scheduler.schedule_parallel(["A"], [("A", "A")])

    def test_cycle_within_larger_graph(
        self, scheduler: ParallelScheduler
    ) -> None:
        """Cycle among B,C,D while A is independent."""
        with pytest.raises(CyclicDependencyError):
            scheduler.schedule_parallel(
                ["A", "B", "C", "D"],
                [("B", "C"), ("C", "D"), ("D", "B")],
            )


# ── Edge cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    """Boundary and degenerate inputs."""

    def test_empty_project_list(
        self, scheduler: ParallelScheduler
    ) -> None:
        """Empty input should return an empty plan."""
        plan = scheduler.schedule_parallel([], [])

        assert plan == []

    def test_duplicate_dependencies_are_tolerated(
        self, scheduler: ParallelScheduler
    ) -> None:
        """Duplicate edges should not cause errors or repeated projects."""
        projects = ["A", "B"]
        deps = [("A", "B"), ("A", "B")]

        plan = scheduler.schedule_parallel(projects, deps)

        assert plan == [["A"], ["B"]]
        _assert_valid_level_plan(plan, projects, deps)


# ── Input validation ────────────────────────────────────────────────


class TestInputValidation:
    """Malformed or inconsistent input."""

    def test_dependency_references_unknown_dependent(
        self, scheduler: ParallelScheduler
    ) -> None:
        """A dependency pair mentions a dependent not in the project list."""
        with pytest.raises(SchedulerError):
            scheduler.schedule_parallel(["A"], [("A", "X")])

    def test_dependency_prerequisite_unknown(
        self, scheduler: ParallelScheduler
    ) -> None:
        """The prerequisite in a dependency is not in the project list."""
        with pytest.raises(SchedulerError):
            scheduler.schedule_parallel(["B"], [("X", "B")])


# ── Ordering correctness ───────────────────────────────────────────


class TestOrderingCorrectness:
    """Every dependency pair must cross levels correctly."""

    def test_complex_dag_levels(
        self, scheduler: ParallelScheduler
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

        plan = scheduler.schedule_parallel(projects, deps)

        _assert_valid_level_plan(plan, projects, deps)
        _assert_maximal_parallelism(plan, projects, deps)

    def test_wide_fan_out(
        self, scheduler: ParallelScheduler
    ) -> None:
        """One root feeding four children — two levels."""
        projects = ["root", "a", "b", "c", "d"]
        deps = [("root", "a"), ("root", "b"), ("root", "c"), ("root", "d")]

        plan = scheduler.schedule_parallel(projects, deps)

        assert len(plan) == 2
        assert plan[0] == ["root"]
        assert set(plan[1]) == {"a", "b", "c", "d"}
        _assert_maximal_parallelism(plan, projects, deps)


# ── Parallelism maximality ─────────────────────────────────────────


class TestParallelismMaximality:
    """Every project must appear in the earliest feasible level."""

    def test_diamond_middle_shares_level(
        self, scheduler: ParallelScheduler
    ) -> None:
        """Diamond middle projects must share a level (not be split)."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]

        plan = scheduler.schedule_parallel(projects, deps)

        level_of = {p: i for i, lvl in enumerate(plan) for p in lvl}
        assert level_of["B"] == level_of["C"], (
            f"B and C should share a level, got plan={plan}"
        )

    def test_asymmetric_prereq_depth(
        self, scheduler: ParallelScheduler
    ) -> None:
        """A -> X, A -> B -> X: X must wait for the deeper path."""
        projects = ["A", "B", "X"]
        deps = [("A", "X"), ("A", "B"), ("B", "X")]

        plan = scheduler.schedule_parallel(projects, deps)

        _assert_valid_level_plan(plan, projects, deps)
        _assert_maximal_parallelism(plan, projects, deps)
        assert len(plan) == 3
