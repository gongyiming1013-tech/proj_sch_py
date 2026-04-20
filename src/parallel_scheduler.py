"""Parallel-aware project scheduler (V1).

Defines a new abstract interface `ParallelProjectScheduler` — kept separate
from V0's `ProjectScheduler` to preserve LSP, because the return shape
differs (`list[list[str]]` vs `list[str]`).

Reuses V0's `DependencyGraph` and `CyclicDependencyError`.
"""

from abc import ABC, abstractmethod

from src.exceptions import CyclicDependencyError
from src.graph import DependencyGraph


class ParallelProjectScheduler(ABC):
    """Abstract interface for parallel-aware scheduling strategies.

    Subclasses emit a level-grouped execution plan: projects within the
    same level may run concurrently. V1 assumes unbounded compute, so
    every project appears in the earliest level its prerequisites allow.
    """

    @abstractmethod
    def schedule_parallel(
        self,
        projects: list[str],
        dependencies: list[tuple[str, str]],
    ) -> list[list[str]]:
        """Produce a level-grouped execution plan.

        Args:
            projects: List of project names.
            dependencies: List of (prerequisite, dependent) pairs.
                          ("A", "B") means A must complete before B.

        Returns:
            A list of levels; each inner list contains project names that
            may run concurrently once all prior-level projects complete.
            Within a level, project order follows the original `projects`
            input order (deterministic), though callers should treat the
            level as an unordered set for correctness purposes.

        Raises:
            CyclicDependencyError: If dependencies contain a cycle.
            SchedulerError: If input is otherwise invalid.
        """


class ParallelScheduler(ParallelProjectScheduler):
    """Level-BFS Kahn's variant that maximizes within-level parallelism."""

    def schedule_parallel(
        self,
        projects: list[str],
        dependencies: list[tuple[str, str]],
    ) -> list[list[str]]:
        """Produce a level-grouped plan using level-BFS Kahn's algorithm.

        Args:
            projects: List of project names.
            dependencies: List of (prerequisite, dependent) pairs.

        Returns:
            A list of levels; each inner list contains every project whose
            dependencies became satisfied at the same BFS step.

        Raises:
            CyclicDependencyError: If dependencies contain a cycle.
            SchedulerError: If input is otherwise invalid.
        """
        graph = DependencyGraph(projects, dependencies)
        in_degrees = {node: graph.in_degree(node) for node in graph.all_nodes}

        current_level = [node for node in projects if in_degrees[node] == 0]

        plan: list[list[str]] = []
        placed = 0
        while current_level:
            plan.append(list(current_level))
            placed += len(current_level)
            next_level: list[str] = []
            for node in current_level:
                for neighbor in graph.neighbors(node):
                    in_degrees[neighbor] -= 1
                    if in_degrees[neighbor] == 0:
                        next_level.append(neighbor)
            current_level = next_level

        if placed != len(graph.all_nodes):
            raise CyclicDependencyError("Cyclic dependency detected")

        return plan
