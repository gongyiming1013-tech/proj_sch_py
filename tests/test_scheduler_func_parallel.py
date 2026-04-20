"""Tests for V1.1 function-based parallel scheduler — written against the contract before implementation."""

import pytest

from src import scheduler_func
from src.parallel_scheduler import ParallelScheduler
from src.scheduler_func import (
    CyclicDependencyError,
    SchedulerError,
    schedule_parallel,
)


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
    """Assert every project is at the earliest level its prerequisites allow."""
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

    def test_linear_chain(self) -> None:
        """A -> B -> C should produce three singleton levels."""
        projects = ["A", "B", "C"]
        deps = [("A", "B"), ("B", "C")]

        plan = schedule_parallel(projects, deps)

        assert plan == [["A"], ["B"], ["C"]]
        _assert_valid_level_plan(plan, projects, deps)

    def test_diamond_dag(self) -> None:
        """Diamond: A -> {B,C} -> D should put B and C in the same level."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]

        plan = schedule_parallel(projects, deps)

        assert len(plan) == 3
        assert plan[0] == ["A"]
        assert set(plan[1]) == {"B", "C"}
        assert plan[2] == ["D"]
        _assert_valid_level_plan(plan, projects, deps)
        _assert_maximal_parallelism(plan, projects, deps)

    def test_multiple_independent_components(self) -> None:
        """Two disconnected chains: A->B and C->D — levels should overlap."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("C", "D")]

        plan = schedule_parallel(projects, deps)

        assert len(plan) == 2
        assert set(plan[0]) == {"A", "C"}
        assert set(plan[1]) == {"B", "D"}
        _assert_valid_level_plan(plan, projects, deps)
        _assert_maximal_parallelism(plan, projects, deps)

    def test_single_project_no_deps(self) -> None:
        """Single project produces a single-level, single-project plan."""
        plan = schedule_parallel(["A"], [])

        assert plan == [["A"]]

    def test_all_independent_projects(self) -> None:
        """All projects are independent — one level containing all."""
        projects = ["A", "B", "C"]

        plan = schedule_parallel(projects, [])

        assert len(plan) == 1
        assert set(plan[0]) == {"A", "B", "C"}

    def test_example_from_spec(self) -> None:
        """Spec example: projects=[A,B,C,D], deps A->B, B->C, A->C."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("B", "C"), ("A", "C")]

        plan = schedule_parallel(projects, deps)

        _assert_valid_level_plan(plan, projects, deps)
        _assert_maximal_parallelism(plan, projects, deps)


# ── Cycle detection ─────────────────────────────────────────────────


class TestCycleDetection:
    """Cyclic graphs must raise CyclicDependencyError."""

    def test_simple_two_node_cycle(self) -> None:
        """A -> B -> A."""
        with pytest.raises(CyclicDependencyError):
            schedule_parallel(["A", "B"], [("A", "B"), ("B", "A")])

    def test_three_node_cycle(self) -> None:
        """A -> B -> C -> A."""
        with pytest.raises(CyclicDependencyError):
            schedule_parallel(
                ["A", "B", "C"], [("A", "B"), ("B", "C"), ("C", "A")]
            )

    def test_self_dependency(self) -> None:
        """A depends on itself."""
        with pytest.raises(CyclicDependencyError):
            schedule_parallel(["A"], [("A", "A")])

    def test_cycle_within_larger_graph(self) -> None:
        """Cycle among B,C,D while A is independent."""
        with pytest.raises(CyclicDependencyError):
            schedule_parallel(
                ["A", "B", "C", "D"],
                [("B", "C"), ("C", "D"), ("D", "B")],
            )


# ── Edge cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    """Boundary and degenerate inputs."""

    def test_empty_project_list(self) -> None:
        """Empty input should return an empty plan."""
        plan = schedule_parallel([], [])

        assert plan == []

    def test_duplicate_dependencies_are_tolerated(self) -> None:
        """Duplicate edges should not cause errors or repeated projects."""
        projects = ["A", "B"]
        deps = [("A", "B"), ("A", "B")]

        plan = schedule_parallel(projects, deps)

        assert plan == [["A"], ["B"]]
        _assert_valid_level_plan(plan, projects, deps)


# ── Input validation ────────────────────────────────────────────────


class TestInputValidation:
    """Malformed or inconsistent input."""

    def test_dependency_references_unknown_dependent(self) -> None:
        """A dependency pair mentions a dependent not in the project list."""
        with pytest.raises(SchedulerError):
            schedule_parallel(["A"], [("A", "X")])

    def test_dependency_prerequisite_unknown(self) -> None:
        """The prerequisite in a dependency is not in the project list."""
        with pytest.raises(SchedulerError):
            schedule_parallel(["B"], [("X", "B")])

    def test_local_exceptions_match_v0_1(self) -> None:
        """V1.1 reuses V0.1's local exceptions (same classes), not V0's."""
        from src.exceptions import (
            CyclicDependencyError as V0Cyclic,
            SchedulerError as V0Base,
        )

        assert SchedulerError is not V0Base
        assert CyclicDependencyError is not V0Cyclic


# ── Ordering correctness ───────────────────────────────────────────


class TestOrderingCorrectness:
    """Every dependency pair must cross levels correctly."""

    def test_complex_dag_levels(self) -> None:
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

        plan = schedule_parallel(projects, deps)

        _assert_valid_level_plan(plan, projects, deps)
        _assert_maximal_parallelism(plan, projects, deps)

    def test_wide_fan_out(self) -> None:
        """One root feeding four children — two levels."""
        projects = ["root", "a", "b", "c", "d"]
        deps = [("root", "a"), ("root", "b"), ("root", "c"), ("root", "d")]

        plan = schedule_parallel(projects, deps)

        assert len(plan) == 2
        assert plan[0] == ["root"]
        assert set(plan[1]) == {"a", "b", "c", "d"}
        _assert_maximal_parallelism(plan, projects, deps)


# ── Parallelism maximality ─────────────────────────────────────────


class TestParallelismMaximality:
    """Every project must appear in the earliest feasible level."""

    def test_diamond_middle_shares_level(self) -> None:
        """Diamond middle projects must share a level (not be split)."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]

        plan = schedule_parallel(projects, deps)

        level_of = {p: i for i, lvl in enumerate(plan) for p in lvl}
        assert level_of["B"] == level_of["C"], (
            f"B and C should share a level, got plan={plan}"
        )

    def test_asymmetric_prereq_depth(self) -> None:
        """A -> X, A -> B -> X: X must wait for the deeper path."""
        projects = ["A", "B", "X"]
        deps = [("A", "X"), ("A", "B"), ("B", "X")]

        plan = schedule_parallel(projects, deps)

        _assert_valid_level_plan(plan, projects, deps)
        _assert_maximal_parallelism(plan, projects, deps)
        assert len(plan) == 3


# ── Equivalence with V1 (Option A — single sanity check) ────────────


class TestEquivalenceWithV1:
    """Cross-check V1 (OOD) and V1.1 (function-based) on a representative input."""

    def test_diamond_dag_both_implementations_agree(self) -> None:
        """Diamond DAG: both implementations must yield valid plans with the same level count."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]

        out_v1 = ParallelScheduler().schedule_parallel(projects, deps)
        out_v11 = scheduler_func.schedule_parallel(projects, deps)

        _assert_valid_level_plan(out_v1, projects, deps)
        _assert_valid_level_plan(out_v11, projects, deps)
        assert len(out_v1) == len(out_v11), (
            f"Level counts differ: V1={len(out_v1)}, V1.1={len(out_v11)}"
        )


# ── V0.1 regression (schedule() still works after adding stubs) ─────


class TestV01Regression:
    """Adding V1.1 stubs must not break V0.1's existing `schedule()`."""

    def test_v01_schedule_still_works(self) -> None:
        """V0.1's sequential `schedule()` is unaffected by V1.1 additions."""
        projects = ["A", "B", "C", "D"]
        deps = [("A", "B"), ("B", "C"), ("A", "C")]

        result = scheduler_func.schedule(projects, deps)

        assert set(result) == set(projects)
        index = {name: i for i, name in enumerate(result)}
        for prereq, dependent in deps:
            assert index[prereq] < index[dependent]
