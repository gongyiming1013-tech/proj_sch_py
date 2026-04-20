"""Function-based sequential project scheduler (V0.1).

Self-contained module: defines its own exceptions and uses plain dict/list
structures internally. Implements the same Kahn's-algorithm contract as V0's
SequentialScheduler, but as pure functions with no class wrappers.
"""

from collections import deque


# ── Exceptions ──────────────────────────────────────────────────────


class SchedulerError(Exception):
    """Base exception for V0.1 scheduler errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CyclicDependencyError(SchedulerError):
    """Raised when the dependency graph contains a cycle."""

    def __init__(self, message: str = "Cyclic dependency detected") -> None:
        super().__init__(message)


# ── Private helpers ─────────────────────────────────────────────────


def _build_graph(
    projects: list[str],
    dependencies: list[tuple[str, str]],
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Build adjacency and in-degree maps from projects and dependencies.

    Args:
        projects: List of project names.
        dependencies: List of (prerequisite, dependent) pairs.

    Returns:
        (adjacency, in_degree) — adjacency maps each project to its dependents;
        in_degree counts incoming edges per project.

    Raises:
        SchedulerError: If a dependency references a project not in `projects`.
    """
    nodes = set(projects)
    adjacency: dict[str, list[str]] = {node: [] for node in projects}
    in_degree: dict[str, int] = {node: 0 for node in projects}

    for prereq, dependent in dependencies:
        if prereq not in nodes:
            raise SchedulerError(
                f"Prerequisite '{prereq}' is not in the project list"
            )
        if dependent not in nodes:
            raise SchedulerError(
                f"Dependent '{dependent}' is not in the project list"
            )
        adjacency[prereq].append(dependent)
        in_degree[dependent] += 1

    return adjacency, in_degree


def _kahn_sort(
    projects: list[str],
    adjacency: dict[str, list[str]],
    in_degree: dict[str, int],
) -> list[str]:
    """Run Kahn's BFS topological sort.

    Args:
        projects: Original project list (used for deterministic seed order).
        adjacency: Adjacency map from `_build_graph`.
        in_degree: In-degree map from `_build_graph` (copied locally before mutation).

    Returns:
        Projects in a valid topological order.

    Raises:
        CyclicDependencyError: If processed count < total nodes.
    """
    remaining = dict(in_degree)
    queue: deque[str] = deque(node for node in projects if remaining[node] == 0)

    result: list[str] = []
    while queue:
        current = queue.popleft()
        result.append(current)
        for neighbor in adjacency[current]:
            remaining[neighbor] -= 1
            if remaining[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(projects):
        raise CyclicDependencyError("Cyclic dependency detected")

    return result


# ── Public API ──────────────────────────────────────────────────────


def schedule(
    projects: list[str],
    dependencies: list[tuple[str, str]],
) -> list[str]:
    """Produce a valid execution order for the given projects.

    Args:
        projects: List of project names.
        dependencies: List of (prerequisite, dependent) pairs. ("A", "B") means
                      A must complete before B.

    Returns:
        Project names in a valid topological order.

    Raises:
        CyclicDependencyError: If dependencies contain a cycle.
        SchedulerError: If a dependency references a project not in `projects`.
    """
    adjacency, in_degree = _build_graph(projects, dependencies)
    return _kahn_sort(projects, adjacency, in_degree)


# ── V1.1 — Parallel-aware additions (Phase C stubs) ─────────────────


def _kahn_level_sort(
    projects: list[str],
    adjacency: dict[str, list[str]],
    in_degree: dict[str, int],
) -> list[list[str]]:
    """Run level-BFS Kahn's algorithm to produce parallel level groups.

    Each iteration drains *all* currently zero-in-degree projects into one
    level, then decrements their dependents' in-degrees. Repeats until the
    graph is empty (success) or progress stalls (cycle).

    Args:
        projects: Original project list (used for deterministic level order).
        adjacency: Adjacency map from `_build_graph`.
        in_degree: In-degree map from `_build_graph` (copied locally).

    Returns:
        A list of levels; each inner list contains projects runnable in
        parallel at that level.

    Raises:
        CyclicDependencyError: If progress stalls before all projects are placed.
    """
    remaining = dict(in_degree)
    current_level = [node for node in projects if remaining[node] == 0]

    plan: list[list[str]] = []
    placed = 0
    while current_level:
        plan.append(current_level)
        placed += len(current_level)
        next_level: list[str] = []
        for node in current_level:
            for neighbor in adjacency[node]:
                remaining[neighbor] -= 1
                if remaining[neighbor] == 0:
                    next_level.append(neighbor)
        current_level = next_level

    if placed != len(projects):
        raise CyclicDependencyError("Cyclic dependency detected")

    return plan


def schedule_parallel(
    projects: list[str],
    dependencies: list[tuple[str, str]],
) -> list[list[str]]:
    """Produce a level-grouped execution plan (unbounded parallelism).

    Projects within a level may execute concurrently; every project is
    placed in the earliest level its prerequisites allow.

    Args:
        projects: List of project names.
        dependencies: List of (prerequisite, dependent) pairs.

    Returns:
        List of levels; each inner list contains concurrently runnable projects.
        Order within a level is not significant.

    Raises:
        CyclicDependencyError: If dependencies contain a cycle.
        SchedulerError: If a dependency references a project not in `projects`.
    """
    adjacency, in_degree = _build_graph(projects, dependencies)
    return _kahn_level_sort(projects, adjacency, in_degree)
