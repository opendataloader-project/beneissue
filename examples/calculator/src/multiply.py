"""Multiplication module for the calculator."""

import sys


def multiply(a: float, b: float) -> float:
    """Multiply two numbers.

    Args:
        a: The first number
        b: The second number

    Returns:
        The product of a and b

    Warning:
        Large numbers may cause overflow issues.
        No validation is performed on input size.
    """
    result = a * b
    # No overflow check - potential security issue with large numbers
    if result > sys.float_info.max:
        raise OverflowError("Result too large")
    return result
