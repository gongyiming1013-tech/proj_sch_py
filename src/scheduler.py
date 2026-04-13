"""Project scheduler interface and sequential implementation."""

from abc import ABC, abstractmethod
from collections import deque

from src.exceptions import CyclicDependencyError
from src.graph import DependencyGraph


class ProjectScheduler(ABC):
    """Abstract interface for project scheduling strategies.

    Subclasses implement a specific scheduling algorithm
    (e.g., sequential topological sort, parallel level-based).
    """

    @abstractmethod
    def schedule(
        self,
        projects: list[str],
        dependencies: list[tuple[str, str]],
    ) -> list[str]:
        """Produce a valid execution order for the given projects.

        Args:
            projects: List of project names.
            dependencies: List of (prerequisite, dependent) pairs.
                          ("A", "B") means A must complete before B.

        Returns:
            A list of project names in a valid execution order.

        Raises:
            CyclicDependencyError: If dependencies contain a cycle.
            SchedulerError: If input is otherwise invalid.
        """


class SequentialScheduler(ProjectScheduler):
    """Schedules projects in a single linear order using Kahn's algorithm."""

    def schedule(
        self,
        projects: list[str],
        dependencies: list[tuple[str, str]],
    ) -> list[str]:
        """Produce a valid topological order using Kahn's algorithm.

        Args:
            projects: List of project names.
            dependencies: List of (prerequisite, dependent) pairs.

        Returns:
            A list of project names in valid topological order.

        Raises:
            CyclicDependencyError: If dependencies contain a cycle.
            SchedulerError: If input is otherwise invalid.
        """
        graph = DependencyGraph(projects, dependencies)

        # Kahn's algorithm
        queue: deque[str] = deque()
        in_degrees = {node: graph.in_degree(node) for node in graph.all_nodes}

        for node in projects:
            if in_degrees[node] == 0:
                queue.append(node)

        result: list[str] = []
        while queue:
            current = queue.popleft()
            result.append(current)
            for neighbor in graph.neighbors(current):
                in_degrees[neighbor] -= 1
                if in_degrees[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(graph.all_nodes):
            raise CyclicDependencyError("Cyclic dependency detected")

        return result
