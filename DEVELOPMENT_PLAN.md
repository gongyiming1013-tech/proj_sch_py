# Project Scheduler — Development Plan

## Overview

**Problem:** Given a set of projects with inter-project dependencies, determine a valid execution order such that every project runs only after all of its prerequisites have completed. If the dependency graph contains a cycle, the system must detect it and report an error rather than producing an invalid schedule.

**High-Level Goals:**
- Accept a list of project names and a list of dependency pairs as input.
- Produce a valid linear execution order (topological sort) or raise a clear error on cyclic input.
- Design for extensibility — future versions will introduce parallel execution, priority scheduling, and richer project metadata.

**Expected Outcome (MVP):** A Python library that, given `projects = ["A","B","C","D"]` and `dependencies = [("A","B"), ("B","C"), ("A","C")]`, returns a valid topological order such as `["A", "B", "C", "D"]` — or raises `CyclicDependencyError` when the graph contains a cycle.

---

## Design

### V0 (MVP) — Sequential Project Scheduler

**Goal:** Produce a single valid linear execution order for a set of projects with dependencies, rejecting cyclic inputs.

#### Architecture

```
┌─────────────────────────────────────────────────┐
│                   Client Code                    │
│         (passes projects + dependencies)         │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │   ProjectScheduler     │  ◄── Abstract interface
          │   (Protocol / ABC)     │
          │  + schedule() -> list  │
          └────────────┬───────────┘
                       │ implements
                       ▼
          ┌────────────────────────┐       ┌──────────────────────┐
          │  SequentialScheduler   │──────▶│   DependencyGraph    │
          │  (Kahn's algorithm)    │ uses  │  (adjacency list +   │
          └────────────────────────┘       │   in-degree map)     │
                       │                   └──────────────────────┘
                       │ raises on cycle
                       ▼
          ┌────────────────────────┐
          │  CyclicDependencyError │──▶ SchedulerError (base)
          └────────────────────────┘
```

**Data flow:** Client → `SequentialScheduler.schedule(projects, dependencies)` → builds `DependencyGraph` → runs Kahn's algorithm → returns ordered list or raises `CyclicDependencyError`.

#### Design Patterns

| Pattern  | Where                    | Why                                                                 |
|----------|--------------------------|---------------------------------------------------------------------|
| Strategy | `ProjectScheduler` ABC   | Swappable scheduling algorithms; V0 uses sequential, V1+ adds parallel. |
| Factory Method | (Planned for V1+)  | Conditional creation of scheduler instances based on configuration. |

#### Strategy Comparison — Topological Sort Algorithm

| Approach              | Pros                                          | Cons                                         | Verdict     |
|-----------------------|-----------------------------------------------|----------------------------------------------|-------------|
| **Kahn's (BFS)**      | Cycle detection is built-in (incomplete processing = cycle). Iterative, no recursion-depth risk. Naturally yields a level-order result. | Requires explicit in-degree bookkeeping. | **Selected** |
| **DFS-based**         | Familiar recursive pattern. Can detect back-edges for cycles. | Needs three-color state tracking. Recursion depth may be a concern for large graphs. Output is reverse post-order (must reverse). | Rejected    |

**Verdict:** Kahn's algorithm — cycle detection falls out naturally (if processed count < total nodes, a cycle exists), and the iterative approach avoids stack-depth issues for large project sets.

#### Class & Data Structure Reference

| Type                    | Kind      | Fields / Attributes                                                                 | Key Methods                                                                                                    | Thread-Safe |
|-------------------------|-----------|-------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|-------------|
| `ProjectScheduler`      | ABC       | —                                                                                   | `schedule(projects: list[str], dependencies: list[tuple[str, str]]) -> list[str]` (abstract)                   | N/A         |
| `SequentialScheduler`   | Class     | —                                                                                   | `schedule(projects, dependencies) -> list[str]` — builds graph, runs Kahn's, returns order or raises error.    | No (V0)     |
| `DependencyGraph`       | Class     | `_adjacency: dict[str, list[str]]`, `_in_degree: dict[str, int]`, `_nodes: set[str]` | `__init__(nodes, edges)`, `neighbors(node) -> list[str]`, `in_degree(node) -> int`, `nodes() -> set[str]`      | No (V0)     |
| `SchedulerError`        | Exception | `message: str`                                                                      | Inherits from `Exception`.                                                                                     | N/A         |
| `CyclicDependencyError` | Exception | `message: str`                                                                      | Inherits from `SchedulerError`.                                                                                | N/A         |

**Dependency pair semantics:** `("A", "B")` means "A must complete before B can start" — A is a prerequisite of B.

#### Test Plan

| Dimension             | Covers                                       | Key Scenarios                                                                                           |
|-----------------------|----------------------------------------------|---------------------------------------------------------------------------------------------------------|
| Core functionality    | Valid topological ordering                   | Linear chain, diamond DAG, multiple independent components, single project, all independent projects.   |
| Cycle detection       | Cyclic dependency error                      | Simple 2-node cycle, 3-node cycle, self-dependency, cycle within a larger graph.                        |
| Edge cases            | Boundary and degenerate inputs               | Empty project list, single project with no deps, duplicate dependencies, unknown project in dependency. |
| Input validation      | Malformed or inconsistent input              | Dependency referencing a project not in the project list.                                                |
| Ordering correctness  | Every dependency pair respected in output     | For each `(a, b)` in dependencies, `a` appears before `b` in the result.                               |

---

### V0.1 — Function-Based Sequential Scheduler

**Goal:** Provide a function-based equivalent of V0 — same Kahn's algorithm, same cycle semantics — implemented as pure functions over plain `dict`/`list` structures, illustrating the "Functions" approach from CLAUDE.md §Implementation Approach.

#### Architecture

```
┌─────────────────────────────────────────────┐
│                Client Code                   │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
       ┌──────────────────────────────────────┐
       │   schedule(projects, dependencies)    │  ◄── Public function
       │   (src/scheduler_func.py)             │
       └────────────────┬─────────────────────┘
                        │ calls
         ┌──────────────┴───────────────┐
         ▼                              ▼
 ┌──────────────────┐         ┌──────────────────┐
 │ _build_graph()   │────────▶│ _kahn_sort()     │
 │ returns          │         │ pure function    │
 │ (adj, in_degree) │         │ over dicts       │
 └──────────────────┘         └────────┬─────────┘
                                       │ raises on cycle
                                       ▼
                          ┌────────────────────────┐
                          │ CyclicDependencyError  │ (defined in same module)
                          └────────────────────────┘
```

**Data flow:** Client → `schedule(projects, dependencies)` → `_build_graph` returns `(adjacency, in_degree)` dicts → `_kahn_sort` consumes them → returns ordered list or raises `CyclicDependencyError`.

**Self-contained:** V0.1 does not import from V0's modules (`src.exceptions`, `src.graph`, `src.scheduler`). Its own `SchedulerError` and `CyclicDependencyError` live at the top of `src/scheduler_func.py`.

#### Strategy Comparison — OOD (V0) vs Function-Based (V0.1)

| Approach              | Pros                                                                                       | Cons                                                                                          | Verdict          |
|-----------------------|--------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|------------------|
| **OOD (V0)**          | Strategy-pattern seam for V1+ enrichment. Clear extension surface. Encapsulated graph state. | More files, more ceremony. Indirection cost for a single algorithm.                          | Kept as V0.      |
| **Function-based (V0.1)** | Minimal code (~30 LOC). Stateless; easy to reason about and test. Closer to algorithmic spec. No constructor / no instance lifecycle. | No strategy seam — adding a parallel variant in V1 requires either a sibling function or a thin dispatch layer. | Adopted as V0.1. |

**Verdict:** Both are valid for V0's scope. We keep V0 to preserve the strategy seam for V1, and add V0.1 to provide a concrete A/B comparison and satisfy the "Functions default" guidance for algorithm problems.

#### Class / Function & Data Structure Reference

| Type                    | Kind              | Signature / Fields                                                                                                              | Thread-Safe              |
|-------------------------|-------------------|--------------------------------------------------------------------------------------------------------------------------------|--------------------------|
| `schedule`              | Function (public) | `schedule(projects: list[str], dependencies: list[tuple[str, str]]) -> list[str]` — entry point; orchestrates build + sort.    | Yes (no shared state)    |
| `_build_graph`          | Function (private)| `_build_graph(projects, dependencies) -> tuple[dict[str, list[str]], dict[str, int]]` — returns adjacency + in-degree maps; raises `SchedulerError` on unknown node. | Yes |
| `_kahn_sort`            | Function (private)| `_kahn_sort(projects, adjacency, in_degree) -> list[str]` — runs Kahn's BFS; returns order or raises `CyclicDependencyError`.  | Yes                      |
| `SchedulerError`        | Exception         | Defined locally in `src/scheduler_func.py`. Base error for V0.1.                                                                | N/A                      |
| `CyclicDependencyError` | Exception         | Defined locally in `src/scheduler_func.py`. Subclass of local `SchedulerError`.                                                  | N/A                      |

**Module:** `src/scheduler_func.py` (single self-contained module — no imports from V0).
**Internal data structures:** Plain `dict[str, list[str]]` for adjacency, `dict[str, int]` for in-degree. No wrapper class.

#### Test Plan

| Dimension              | Covers                                       | Key Scenarios                                                                                           |
|------------------------|----------------------------------------------|---------------------------------------------------------------------------------------------------------|
| Core functionality     | Valid topological ordering                   | Linear chain, diamond DAG, multiple independent components, single project, all-independent projects.   |
| Cycle detection        | Cyclic dependency error                      | Simple 2-node cycle, 3-node cycle, self-dependency, cycle within a larger graph.                        |
| Edge cases             | Boundary and degenerate inputs               | Empty project list, single project with no deps, duplicate dependencies, unknown project in dependency. |
| Input validation       | Malformed or inconsistent input              | Dependency referencing a project not in the project list (raises `SchedulerError`).                     |
| Ordering correctness   | Every dependency pair respected in output    | For each `(a, b)` in dependencies, `a` precedes `b` in the result.                                     |
| Equivalence with V0    | Sanity cross-check (Option A — single test) | One test feeds 1–2 representative inputs (e.g., diamond DAG) to both `SequentialScheduler.schedule` (V0) and `scheduler_func.schedule` (V0.1); both outputs must satisfy all dependency constraints (need not be byte-identical). |

---

### V1 (Planned) — Parallel-Aware Scheduler

**Goal:** Allow multiple independent projects to execute concurrently within a single scheduling step, producing a level-based execution plan.

#### Strategy Comparison

_Placeholder — to be filled before V1 implementation._

#### Design Discussion

- Should the output be `list[list[str]]` (groups of concurrently runnable projects per level)?
- How to handle configurable max-parallelism (e.g., at most N projects at once)?
- Should we introduce a `Project` value object with metadata (duration estimate, resource requirements)?

#### Class & Data Structure Changes

_Placeholder — new and modified types to be defined._

#### Test Plan

| Dimension             | Covers                                       | Key Scenarios          |
|-----------------------|----------------------------------------------|------------------------|
| Parallel grouping     | Correct level assignment                     | _To be defined._       |
| Max-parallelism cap   | Respects concurrency limits                  | _To be defined._       |
| Regression            | All V0 scenarios still pass                  | _To be defined._       |

---

## Roadmap & Implementation

### V0 (MVP) — Sequential Project Scheduler

**Scope:** Implement a sequential project scheduler that accepts a list of project names and dependency pairs, builds a directed graph, and produces a valid topological order using Kahn's algorithm. The system detects cyclic dependencies and raises a domain-specific exception. All code follows SOLID principles with a strategy-pattern interface so the scheduling algorithm can be swapped in future versions.

- [x] Define custom exceptions: `SchedulerError` (base), `CyclicDependencyError`.
- [x] Define `ProjectScheduler` abstract base class with `schedule()` method signature.
- [x] Implement `DependencyGraph` class (adjacency list, in-degree map, input validation).
- [x] Implement `SequentialScheduler` using Kahn's algorithm over `DependencyGraph`.
- [x] Write unit tests covering all test plan dimensions (core, cycle, edge cases, validation, ordering).
- [x] Verify ≥ 95% branch coverage (achieved 100%).

### V0.1 — Function-Based Sequential Scheduler

**Scope:** Add a function-based sequential scheduler as a parallel V0 implementation. Same Kahn's algorithm, same cycle semantics — but no classes, no ABC, no `DependencyGraph` wrapper. The module is **self-contained**: it defines its own local `SchedulerError` / `CyclicDependencyError` and does not import from V0's modules. Demonstrates the "Functions" approach (CLAUDE.md §Implementation Approach) and gives the user a concrete A/B comparison against V0. Tests mirror V0 dimensions and add one Option-A equivalence sanity check.

- [x] Create `src/scheduler_func.py` containing local `SchedulerError` / `CyclicDependencyError`, public `schedule()`, and private `_build_graph()` / `_kahn_sort()` helpers. No imports from V0.
- [x] Write unit tests in `tests/test_scheduler_func.py` mirroring V0 dimensions (core, cycle, edge cases, validation, ordering) — 18 tests, all passing.
- [x] Add **one** equivalence sanity test: feed a representative input (diamond DAG) to both `SequentialScheduler` (V0) and `scheduler_func.schedule` (V0.1); assert both outputs satisfy every dependency constraint.
- [x] Verify ≥ 95% branch coverage (achieved 100% — 37 stmts / 14 branches).

### V1 — Parallel-Aware Scheduler

**Scope:** Extend the scheduler to produce level-grouped output where independent projects within the same level can execute concurrently. Introduce an optional max-parallelism parameter. Retain backward compatibility with the V0 interface.

- [ ] Design parallel grouping algorithm and update Design section.
- [ ] Implement `ParallelScheduler` (new Strategy implementation).
- [ ] Add tests for parallel grouping, max-parallelism, and V0 regression.
- [ ] Verify ≥ 95% branch coverage.
