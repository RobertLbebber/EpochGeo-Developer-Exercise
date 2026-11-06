from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence, TypeAlias


# A 2D point, e.g. (x, y)
Point2D: TypeAlias = tuple[float, float]
# (point, original_index) pair used during tree construction
IndexedPoint: TypeAlias = tuple[Point2D, int]
# (best_dist, best_point, best_index) triple returned by _find_nearest
NearestResult: TypeAlias = tuple[Optional[float], Optional[Point2D], Optional[int]]


class _KDNode:
    __slots__ = ("point", "index", "axis", "left", "right")

    point: Point2D
    index: int
    axis: int
    left: Optional[_KDNode]
    right: Optional[_KDNode]

    def __init__(self, point: Point2D, index: int, axis: int) -> None:
        self.point = point
        self.index = index
        self.axis = axis
        self.left = None
        self.right = None


def _build_kd_tree(
    indexed_points: list[IndexedPoint], depth: int = 0
) -> Optional[_KDNode]:
    if not indexed_points:
        return None

    axis = depth % 2
    indexed_points.sort(key=lambda item: item[0][axis])

    mid = len(indexed_points) // 2
    point, original_index = indexed_points[mid]

    node = _KDNode(point, original_index, axis)
    node.left = _build_kd_tree(indexed_points[:mid], depth + 1)
    node.right = _build_kd_tree(indexed_points[mid + 1:], depth + 1)
    return node


def _find_nearest(
    node: Optional[_KDNode],
    query_point: Point2D,
    best_dist: Optional[float] = None,
    best_point: Optional[Point2D] = None,
    best_index: Optional[int] = None,
) -> NearestResult:
    if node is None:
        return best_dist, best_point, best_index

    point = node.point
    dx = point[0] - query_point[0]
    dy = point[1] - query_point[1]
    dist = dx * dx + dy * dy

    if (
        best_dist is None
        or dist < best_dist
        or (dist == best_dist and (best_index is None or node.index < best_index))
    ):
        best_dist = dist
        best_point = point
        best_index = node.index

    axis = node.axis
    diff = query_point[axis] - point[axis]

    near: Optional[_KDNode]
    far: Optional[_KDNode]
    if diff < 0:
        near, far = node.left, node.right
    else:
        near, far = node.right, node.left

    best_dist, best_point, best_index = _find_nearest(
        near, query_point, best_dist, best_point, best_index
    )

    if best_dist is None or diff * diff <= best_dist:
        best_dist, best_point, best_index = _find_nearest(
            far, query_point, best_dist, best_point, best_index
        )

    return best_dist, best_point, best_index


class NearestNeighborIndex:
    """
    Indexes 2D points in a KD-tree for fast nearest-neighbor lookup.

    The index is built once in __init__, then each call to find_nearest
    runs in roughly O(log n) time for typical point sets.
    """

    points: list[Point2D]
    _root: Optional[_KDNode]

    def __init__(self, points: Iterable[Point2D]) -> None:
        """
        Takes an iterable of 2D tuples as input points to be indexed.
        """
        self.points = list(points)
        indexed_points: list[IndexedPoint] = [
            (point, i) for i, point in enumerate(self.points)
        ]
        self._root = _build_kd_tree(indexed_points)

    @staticmethod
    def find_nearest_slow(
        query_point: Point2D, haystack: Sequence[Point2D]
    ) -> Optional[Point2D]:
        """
        find_nearest_slow returns the point that is closest to query_point. If there are no indexed
        points, None is returned.
        """

        min_dist: Optional[float] = None
        min_point: Optional[Point2D] = None

        for point in haystack:
            deltax = point[0] - query_point[0]
            deltay = point[1] - query_point[1]
            dist = math.sqrt(deltax * deltax + deltay * deltay)
            if min_dist is None or dist < min_dist:
                min_dist = dist
                min_point = point

        return min_point

    def find_nearest_fast(self, query_point: Point2D) -> Optional[Point2D]:
        """
        find_nearest_fast returns the point that is closest to query_point using the KD-tree.
        If there are no indexed points, None is returned.
        """
        _, point, _ = _find_nearest(self._root, query_point)
        return point

    def find_nearest(self, query_point: Point2D) -> Optional[Point2D]:
        """
        Returns the indexed point closest to query_point.
        """
        return self.find_nearest_fast(query_point)