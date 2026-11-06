
# Please create a simple example use of the pynn library for your end user. Assume that the end
# user knows a lot about their subject matter but has only a basic understanding of Python.

# Meaningful examples may include reading a file, finding a few nearby points and writing them
# out to the console.

"""
Simple example use of the pynn library.

Run with:
    python examples/simple_example.py
"""

from pynn import NearestNeighborIndex


def main():
    # Points to index, represented as (x, y) tuples.
    points = [
        (1.0, 2.0),
        (1.0, 0.0),
        (10.0, 5.0),
        (-1000.0, 20.0),
        (3.14159, 42.0),
        (42.0, 3.14159),
    ]

    index = NearestNeighborIndex(points)

    queries = [
        (0.0, 0.0),
        (-2000.0, 0.0),
        (40.0, 3.0),
    ]

    for query in queries:
        nearest = index.find_nearest(query)
        print(f"Query {query} -> nearest indexed point {nearest}")


if __name__ == "__main__":
    main()