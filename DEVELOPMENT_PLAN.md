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

### V1 — Parallel-Aware Scheduler (OOD)

**Goal:** Produce a level-grouped execution plan where every project within a level can execute concurrently (unbounded compute assumed), preserving all dependency constraints.

**Scope assumption:** Compute resources are unlimited — every level emits *all* projects whose dependencies are already satisfied. No `max_parallelism` cap in V1; that can be revisited in V2 if resource/cost models are introduced.

#### Architecture

```
┌─────────────────────────────────────────────────┐
│                   Client Code                    │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
          ┌────────────────────────────────┐
          │  ParallelProjectScheduler      │  ◄── New abstract interface
          │  (Protocol / ABC)              │      for parallel variants
          │  + schedule_parallel() ->      │
          │    list[list[str]]             │
          └────────────┬───────────────────┘
                       │ implements
                       ▼
          ┌────────────────────────┐       ┌──────────────────────┐
          │  ParallelScheduler     │──────▶│   DependencyGraph    │
          │  (level-BFS Kahn's)    │ reuse │  (imported from V0)  │
          └────────────┬───────────┘       └──────────────────────┘
                       │ raises on cycle
                       ▼
          ┌────────────────────────┐
          │  CyclicDependencyError │  (reused from V0)
          └────────────────────────┘
```

**Data flow:** Client → `ParallelScheduler.schedule_parallel(projects, dependencies)` → builds `DependencyGraph` → runs level-BFS Kahn's (drain all zero-in-degree nodes as one level, decrement neighbors, repeat) → returns `list[list[str]]` or raises `CyclicDependencyError`.

**Separation from V0's ABC:** `ParallelProjectScheduler` is a *new* abstract interface — it does **not** inherit from `ProjectScheduler`, because the return shape differs (`list[list[str]]` vs `list[str]`) and forcing a common supertype would violate LSP. V0 and V1 live side by side; both reuse `DependencyGraph` and `CyclicDependencyError`.

#### Design Patterns

| Pattern  | Where                          | Why                                                                 |
|----------|--------------------------------|---------------------------------------------------------------------|
| Strategy | `ParallelProjectScheduler` ABC | Room for future variants (e.g., priority-weighted, resource-aware). |
| Reuse (composition over inheritance) | `ParallelScheduler` uses `DependencyGraph` | Avoid re-implementing graph construction/validation. |

#### Strategy Comparison — Level-Grouping Algorithm

| Approach                                 | Pros                                                                                   | Cons                                                                 | Verdict     |
|------------------------------------------|----------------------------------------------------------------------------------------|----------------------------------------------------------------------|-------------|
| **Level-BFS Kahn's** (drain all zero-in-degree per step) | Minimal change from V0's Kahn's. Cycle detection falls out naturally. Output is exactly the level grouping. | Requires collecting all current zero-in-degree nodes before decrement. | **Selected** |
| **Longest-path levels** (node level = max predecessor level + 1) | Produces the same grouping; no BFS queue. | Two passes over the graph; harder to integrate cycle detection cleanly. | Rejected    |

**Verdict:** Level-BFS Kahn's — lowest cognitive delta from V0, and cycle detection is inherited.

#### Class & Data Structure Reference

| Type                        | Kind      | Fields / Attributes          | Key Methods                                                                                                         | Thread-Safe |
|-----------------------------|-----------|------------------------------|---------------------------------------------------------------------------------------------------------------------|-------------|
| `ParallelProjectScheduler`  | ABC       | —                            | `schedule_parallel(projects: list[str], dependencies: list[tuple[str, str]]) -> list[list[str]]` (abstract)         | N/A         |
| `ParallelScheduler`         | Class     | —                            | `schedule_parallel(projects, dependencies) -> list[list[str]]` — builds graph, runs level-BFS, returns level groups or raises `CyclicDependencyError`. | No (V1) |
| `DependencyGraph`           | Class     | (reused from V0, unchanged)  | (reused from V0)                                                                                                    | No          |
| `CyclicDependencyError`     | Exception | (reused from V0)             | (reused from V0)                                                                                                    | N/A         |

**Module:** `src/parallel_scheduler.py` — imports `DependencyGraph` from `src.graph` and `CyclicDependencyError` from `src.exceptions`.
**Output semantics:** `[["A"], ["B", "C"], ["D"]]` means A runs first (level 0), then B and C run concurrently (level 1), then D runs (level 2). Within a level, order is not significant.

#### Test Plan

| Dimension             | Covers                                       | Key Scenarios                                                                                           |
|-----------------------|----------------------------------------------|---------------------------------------------------------------------------------------------------------|
| Core functionality    | Valid level grouping                         | Linear chain (each project its own level), diamond DAG (middle level has 2 projects), independent projects (single level), single project, empty input. |
| Cycle detection       | Cyclic dependency error                      | Simple 2-node cycle, 3-node cycle, self-dependency, cycle within a larger graph.                        |
| Edge cases            | Boundary and degenerate inputs               | Empty project list → `[]`, single project with no deps → `[["X"]]`, duplicate dependencies, unknown project in dependency. |
| Input validation      | Malformed or inconsistent input              | Dependency referencing a project not in the project list.                                                |
| Ordering correctness  | Every dependency pair respected across levels | For each `(a, b)` in dependencies, level(a) < level(b) in the result.                                  |
| Parallelism maximality| Every project appears in the earliest level its deps allow | Diamond DAG: middle two projects must share a level, not be split.                                      |
| V0 regression         | V0's `SequentialScheduler` unaffected        | Running V0 test suite after V1 lands still passes unchanged.                                            |

---

### V1.1 — Function-Based Parallel Scheduler

**Goal:** Provide a function-based equivalent of V1 — same level-BFS Kahn's, same cycle semantics — added to `src/scheduler_func.py` alongside V0.1's `schedule()`. Mirrors the V0 → V0.1 pattern one level up.

#### Architecture

```
┌─────────────────────────────────────────────┐
│                Client Code                   │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
     ┌──────────────────────────────────────────┐
     │  schedule_parallel(projects, deps)        │  ◄── New public function
     │  (src/scheduler_func.py, sibling of V0.1) │
     └────────────────┬─────────────────────────┘
                      │ calls
       ┌──────────────┴────────────────┐
       ▼                               ▼
 ┌──────────────────┐          ┌──────────────────────┐
 │ _build_graph()   │─────────▶│ _kahn_level_sort()   │
 │ (reused from V0.1)│         │ pure function        │
 └──────────────────┘          │ over dicts           │
                               └────────┬─────────────┘
                                        │ raises on cycle
                                        ▼
                          ┌──────────────────────────┐
                          │ CyclicDependencyError    │ (reused from V0.1, local)
                          └──────────────────────────┘
```

**Data flow:** Client → `schedule_parallel(projects, dependencies)` → `_build_graph` (reused from V0.1) returns `(adjacency, in_degree)` → `_kahn_level_sort` drains zero-in-degree nodes per level → returns `list[list[str]]` or raises `CyclicDependencyError`.

**Self-contained:** Stays in `src/scheduler_func.py`, reusing V0.1's `_build_graph` and local exceptions. No imports from V0 or V1's OOD modules.

#### Strategy Comparison — OOD (V1) vs Function-Based (V1.1)

| Approach                | Pros                                                                                   | Cons                                                                                | Verdict           |
|-------------------------|----------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|-------------------|
| **OOD (V1)**            | Strategy seam for future parallel variants. `ParallelScheduler` is a drop-in alongside `SequentialScheduler`. | More files, more ceremony. Two ABCs now coexist (`ProjectScheduler` + `ParallelProjectScheduler`). | Kept as V1.       |
| **Function-based (V1.1)** | ~20 additional LOC on top of V0.1. Stateless; reuses `_build_graph`. Closer to algorithmic spec. | No strategy seam — additional variants require sibling functions. | Adopted as V1.1.  |

**Verdict:** Keep both, mirroring V0/V0.1. Once V2's direction is clear (metadata/cost models vs. pure algorithm enrichment), consolidate or diverge accordingly.

#### Class / Function & Data Structure Reference

| Type                    | Kind              | Signature / Fields                                                                                                                     | Thread-Safe              |
|-------------------------|-------------------|----------------------------------------------------------------------------------------------------------------------------------------|--------------------------|
| `schedule_parallel`     | Function (public) | `schedule_parallel(projects: list[str], dependencies: list[tuple[str, str]]) -> list[list[str]]` — entry point; orchestrates build + level-BFS. | Yes (no shared state)    |
| `_kahn_level_sort`      | Function (private)| `_kahn_level_sort(projects, adjacency, in_degree) -> list[list[str]]` — level-BFS variant of Kahn's; returns level groups or raises `CyclicDependencyError`. | Yes                      |
| `_build_graph`          | Function (private, reused) | Unchanged from V0.1.                                                                                                          | Yes                      |
| `CyclicDependencyError` | Exception (reused from V0.1) | Unchanged.                                                                                                                 | N/A                      |

**Module:** `src/scheduler_func.py` (single self-contained module — V0.1 + V1.1 coexist, share `_build_graph` and local exceptions).

#### Test Plan

| Dimension              | Covers                                       | Key Scenarios                                                                                           |
|------------------------|----------------------------------------------|---------------------------------------------------------------------------------------------------------|
| Core functionality     | Valid level grouping                         | Linear chain, diamond DAG, independent projects, single project, empty input.                           |
| Cycle detection        | Cyclic dependency error                      | Simple 2-node cycle, 3-node cycle, self-dependency, cycle within a larger graph.                        |
| Edge cases             | Boundary and degenerate inputs               | Empty project list, single project, duplicate dependencies, unknown project in dependency.              |
| Input validation       | Malformed or inconsistent input              | Dependency referencing a project not in the project list.                                                |
| Ordering correctness   | Every dependency pair respected across levels | For each `(a, b)` in dependencies, level(a) < level(b).                                                |
| Parallelism maximality | Every project appears in the earliest feasible level | Diamond DAG: middle two projects must share the same level.                                       |
| Equivalence with V1    | Sanity cross-check (Option A — single test) | One test feeds a representative input (diamond DAG) to both `ParallelScheduler.schedule_parallel` (V1) and `scheduler_func.schedule_parallel` (V1.1); both outputs must satisfy every dependency constraint and produce the same number of levels. |

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

### V1 — Parallel-Aware Scheduler (OOD)

**Scope:** Add an OOD parallel scheduler that emits a level-grouped plan (`list[list[str]]`) — every project whose dependencies are satisfied runs in the same level, with no concurrency cap (unlimited compute assumed). V0 is untouched. The new `ParallelProjectScheduler` ABC is introduced as a sibling to V0's `ProjectScheduler` (separate interfaces — LSP-safe) and `ParallelScheduler` is its first concrete implementation, reusing V0's `DependencyGraph` and `CyclicDependencyError`.

- [x] Define new ABC `ParallelProjectScheduler` with `schedule_parallel()` signature in `src/parallel_scheduler.py`.
- [x] Implement `ParallelScheduler` using level-BFS Kahn's, reusing `DependencyGraph` and `CyclicDependencyError` from V0.
- [x] Write unit tests in `tests/test_parallel_scheduler.py` covering all test plan dimensions (core, cycle, edge cases, validation, ordering, parallelism maximality) — 18 tests.
- [x] Regression check: full V0 test suite still passes unchanged.
- [x] Verify ≥ 95% branch coverage (achieved 100% — 26 stmts / 10 branches).

### V1.1 — Function-Based Parallel Scheduler

**Scope:** Add a function-based parallel scheduler to `src/scheduler_func.py` alongside V0.1's `schedule()`. Reuses V0.1's local `_build_graph` and `CyclicDependencyError`. New private helper `_kahn_level_sort()` drains all zero-in-degree nodes per iteration to produce levels. No imports from V0 or V1's OOD modules. Tests mirror V1 dimensions and add one Option-A equivalence sanity check against V1.

- [x] Add `schedule_parallel()` public function and `_kahn_level_sort()` private helper to `src/scheduler_func.py`.
- [x] Write unit tests in a **new file** `tests/test_scheduler_func_parallel.py` mirroring V1 dimensions (keeps V0.1 tests in `tests/test_scheduler_func.py` unchanged) — 19 tests.
- [x] Add **one** equivalence sanity test: feed a representative input (diamond DAG) to both `ParallelScheduler.schedule_parallel` (V1) and `scheduler_func.schedule_parallel` (V1.1); assert outputs satisfy all dependency constraints and produce identical level counts.
- [x] Verify ≥ 95% branch coverage (achieved 100% — `src/scheduler_func.py`: 58 stmts / 24 branches combined V0.1 + V1.1).
