"""Division module for the calculator."""


def divide(a: float, b: float) -> float:
    """Divide a by b.

    Args:
        a: The dividend
        b: The divisor

    Returns:
        The quotient of a divided by b
    """
    # Bug: No check for division by zero - causes crash
    return a / b
