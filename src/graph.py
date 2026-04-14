"""Dependency graph representation for project scheduling."""

from src.exceptions import SchedulerError


class DependencyGraph:
    """Directed graph representing project dependencies.

    Stores an adjacency list and in-degree map for efficient
    topological sort processing.
    """

    def __init__(
        self, nodes: list[str], edges: list[tuple[str, str]]
    ) -> None:
        """Build the dependency graph from nodes and edges.

        Args:
            nodes: List of project names.
            edges: List of (prerequisite, dependent) pairs.
                   ("A", "B") means A must complete before B.

        Raises:
            SchedulerError: If an edge references a project not in nodes.
        """
        self._nodes: set[str] = set(nodes)
        self._adjacency: dict[str, list[str]] = {node: [] for node in nodes}
        self._in_degree: dict[str, int] = {node: 0 for node in nodes}

        for prereq, dependent in edges:
            if prereq not in self._nodes:
                raise SchedulerError(
                    f"Prerequisite '{prereq}' is not in the project list"
                )
            if dependent not in self._nodes:
                raise SchedulerError(
                    f"Dependent '{dependent}' is not in the project list"
                )
            self._adjacency[prereq].append(dependent)
            self._in_degree[dependent] += 1

    def neighbors(self, node: str) -> list[str]:
        """Return the list of dependents for a given node.

        Args:
            node: The project name.

        Returns:
            List of project names that depend on the given node.
        """
        return self._adjacency[node]

    def in_degree(self, node: str) -> int:
        """Return the in-degree (number of prerequisites) of a node.

        Args:
            node: The project name.

        Returns:
            Number of incoming edges to this node.
        """
        return self._in_degree[node]

    @property
    def all_nodes(self) -> set[str]:
        """Return the set of all nodes in the graph."""
        return self._nodes
