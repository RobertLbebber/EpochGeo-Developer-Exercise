# How `pynn` Works

`pynn` provides `NearestNeighborIndex`, a class that indexes 2D points in a
**k-d tree** so that repeated nearest-neighbor lookups are fast. Building the
index is a one-time cost; each query after that is roughly `O(log n)` on
typical point sets instead of `O(n)` for a brute-force scan.

This document covers:

1. [What problem it solves](#1-what-problem-it-solves)
2. [Data structures](#2-data-structures)
3. [Building the tree](#3-building-the-tree)
4. [Querying: finding the nearest point](#4-querying-finding-the-nearest-point)
5. [Why pruning works](#5-why-pruning-works)
6. [Complexity](#6-complexity)
7. [Package layout & packaging](#7-package-layout--packaging)
8. [Edge cases & guarantees](#8-edge-cases--guarantees)

---

## 1. What problem it solves

Given a fixed set of 2D points and many query points, find the indexed point
closest to each query:

```python
from pynn import NearestNeighborIndex

index = NearestNeighborIndex([(0, 0), (2, 3), (5, 4), (7, 1)])

index.find_nearest((1, 1))   # -> (0, 0)
index.find_nearest((6, 0))   # -> (7, 1)
```

The naive approach (`find_nearest_slow`) compares the query against **every**
point: `O(n)` per query, `O(nm)` for `m` queries. The k-d tree stores the
points in a structure that lets a query skip most of them, giving `O(log n)`
per query in the common case.

---

## 2. Data structures

### `_KDNode`

A single node of the tree (`pynn/nearest_neighbor_index.py`):

| Field   | Type                  | Meaning                                                |
| ------- | --------------------- | ------------------------------------------------------ |
| `point` | `tuple[float, float]` | The 2D coordinate stored at this node.                 |
| `index` | `int`                 | Position of this point in the original input list.     |
| `axis`  | `int`                 | Which dimension this node splits on: `0` = x, `1` = y. |
| `left`  | `_KDNode \| None`     | Subtree of points with smaller value on `axis`.        |
| `right` | `_KDNode \| None`     | Subtree of points with larger value on `axis`.         |

`__slots__` is used to keep per-node memory small — important because a tree
of `n` points allocates `n` nodes.

The `index` field exists **only for tie-breaking**: if two points are exactly
equidistant from a query, the one with the lower original index wins. This
makes results deterministic and reproducible regardless of tree shape.

### `NearestNeighborIndex`

The public API. It holds:

- `points` — the original input list, preserved in order.
- `_root` — the root `_KDNode` of the built tree (or `None` if no points).

---

## 3. Building the tree

`_build_kd_tree(indexed_points, depth=0)` builds the tree recursively:

1. **Base case.** If there are no points, return `None`.
2. **Choose an axis.** `axis = depth % 2` — depth 0 splits on x, depth 1 on
   y, depth 2 on x again, and so on. This alternation keeps the tree balanced
   in both dimensions.
3. **Sort** the points by their coordinate on `axis`.
4. **Pick the median** as the current node. The median guarantees that half
   the points go left and half go right, so the tree stays balanced.
5. **Recurse**: build the left subtree from the lower half and the right
   subtree from the upper half, incrementing `depth`.

Each point is stored exactly once, so the tree has `n` nodes. Sorting at each
level costs `O(n log n)` total across the build — see [Complexity](#6-complexity).

```
points: [(0,0), (2,3), (5,4), (7,1)], depth=0, axis=0 (x)
sort by x: (0,0) (2,3) (5,4) (7,1)
median: (2,3)  <- becomes root

        (2,3) axis=0
       /            \
  [(0,0)]        [(5,4), (7,1)]
   depth=1        depth=1, axis=1 (y)
   axis=1         sort by y: (7,1) (5,4)
                  median: (7,1)
                     /       \
                  [(5,4)]    []
```

The build happens **once**, inside `__init__`.

---

## 4. Querying: finding the nearest point

`_find_nearest(node, query_point, best_dist, best_point, best_index)` is a
depth-first search with pruning. It carries the best candidate found so far
down the recursion and returns the improved triple.

At each node:

1. **Base case.** If `node is None`, return the current best triple.
2. **Score the current point.** Compute the **squared** Euclidean distance
   `dx*dx + dy*dy`. (The square root is skipped — it's monotonic, so ordering
   is identical and the query avoids `sqrt` per node.)
3. **Update the best** if this point is closer, or exactly as close but with a
   smaller `index` (tie-break).
4. **Decide which child is "near".** Compare the query's coordinate on this
   node's `axis` to the node's coordinate. The side the query lies on is the
   _near_ child; the other is the _far_ child.
5. **Always descend into `near` first** — it's more likely to contain a closer
   point, so we want to improve `best_dist` before considering `far`.
6. **Descend into `far` only if it could possibly win.** The split-plane
   distance is `diff = query[axis] - point[axis]`. If `diff*diff <= best_dist`,
   the far side might still contain a closer point, so recurse. Otherwise
   **prune** — skip that entire subtree.

Step 6 is the entire point of the tree. Without it you'd visit every node
(`O(n)`); with it, whole subtrees are eliminated without being touched.

---

## 5. Why pruning works

The invariant: **every point in the `far` subtree has a coordinate on `axis`
that is at least `|diff|` away from the query's coordinate on that axis.**

Because Euclidean distance is at least the distance along any single axis, no
point in `far` can be closer than `|diff|`. If `|diff|` already exceeds the
best distance found so far, no point in `far` can beat it, so we can skip the
whole subtree without looking at it.

```
         (5,4) axis=0
        /          \
   left side     right side
   x < 5          x >= 5

Query: (3, 0).  diff = 3 - 5 = -2, so near = left.
If best_dist from the near side is already 1 (dist^2 = 1),
then diff^2 = 4 > 1, so we prune the right side entirely —
no point with x >= 5 can be within distance 1 of x=3.
```

The pruning condition uses `diff * diff <= best_dist` — both sides are
**squared** distances, so the comparison is correct without taking a square
root.

---

## 6. Complexity

Let `n` = number of indexed points, `m` = number of queries.

| Operation                | Cost             | Notes                                                                          |
| ------------------------ | ---------------- | ------------------------------------------------------------------------------ |
| Build (`__init__`)       | `O(n log² n)`    | Sorting at each of `O(log n)` levels.                                          |
| `find_nearest` (typical) | `O(log n)`       | Balanced tree, well-distributed points.                                        |
| `find_nearest` (worst)   | `O(n)`           | Degenerate cases (e.g. all points collinear or on a line parallel to an axis). |
| `find_nearest_slow`      | `O(n)` per query | Brute force; used as a reference / correctness check.                          |
| Space                    | `O(n)`           | One node per point.                                                            |

The median-split build guarantees a **balanced** tree (height `O(log n)`),
so the fast path is the common one. The worst case is inherent to k-d trees
and only occurs on adversarial inputs.

---

## 7. Package layout & packaging

```
developer-exercise-version2/
├── pynn/
│   ├── __init__.py                    # exports NearestNeighborIndex
│   ├── nearest_neighbor_index.py      # the implementation
│   └── _dist_ver.py                   # generated by setuptools_scm
├── tests/
│   └── test_nearest_neighbor_index.py
├── examples/
│   └── simple_example.py
├── pyproject.toml
├── setup.cfg
└── setup.py
```

- **`pynn/__init__.py`** re-exports the public class so callers write
  `from pynn import NearestNeighborIndex`.
- **`pyproject.toml`** declares `setuptools.build_meta` as the PEP 517 build
  backend and configures `setuptools_scm` to derive the version from git tags,
  writing it to `pynn/_dist_ver.py`.
- **`setup.cfg`** holds the declarative metadata (`name`, `license`,
  `python_requires`, etc.).
- **`setup.py`** is a thin shim: `setup(use_scm_version=True)`.

Install for development:

```bash
pip install -e .
```

Run the tests:

```bash
python -m unittest discover -s tests -v
# or
pytest -v
```

---

## 8. Edge cases & guarantees

- **Empty index.** `NearestNeighborIndex([])` builds `_root = None`.
  `find_nearest(...)` returns `None`. `find_nearest_slow(q, [])` also returns
  `None`.
- **Single point.** Works — the root is that point; both children are `None`.
- **Duplicate points.** Both are stored; the one with the lower original
  index is returned on ties.
- **Equidistant points.** Deterministic: lower `index` wins.
- **Negative coordinates / floats.** Fully supported — only arithmetic is
  used, no assumptions about signs or integrality.
- **Immutability of input.** `points` is copied with `list(points)` in
  `__init__`; the caller's iterable is not retained (though the tuples
  themselves are shared).
- **Iterables.** `__init__` accepts any iterable (generators, tuples, lists).
  `find_nearest_slow` accepts any sequence.

---

## See also

- Explainer video — [![K-d Trees - Computerphile](https://www.youtube.com/watch?v=BK5x7IUTIyU)](https://www.youtube.com/watch?v=BK5x7IUTIyU)
- `./diagram.plantuml` — class diagram of the implementation.
- `../examples/simple_example.py` — minimal usage example.
- The docstrings in `./nearest_neighbor_index.py` — per-function reference.

```

### Notes on placement

- Save it as **`docs/how_it_works.md`** (create the `docs/` directory first).
- If you'd rather keep everything at the repo root, `HOW_IT_WORKS.md` works too — just update the paths in the "Package layout" section.
- The anchor links (`#1-what-problem-it-solves`, etc.) are GitHub-flavored and will work on GitHub, GitLab, VS Code preview, and most Markdown renderers.
- Want me to also add a `docs/index.md` that links to this, a `README.md` "Documentation" section pointing here, or convert it to Sphinx/MyST (`index.rst`) instead of plain Markdown?
```
