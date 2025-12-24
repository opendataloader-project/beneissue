"""Subtraction module for the calculator."""


def subtract(a: float, b: float) -> float:
    """Subtract b from a.

    Args:
        a: The first number
        b: The number to subtract

    Returns:
        The difference of a and b
    """
    # Bug: Returns wrong result for negative numbers
    # e.g., subtract(-5, 3) should return -8 but returns -8 correctly
    # The actual bug is subtract(5, -3) returns 8 instead of expected behavior
    return a - b
