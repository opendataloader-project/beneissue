"""CLI entry point for the calculator."""

import sys
from .add import add
from .subtract import subtract
from .multiply import multiply
from .divide import divide


def main():
    """Run the calculator CLI."""
    if len(sys.argv) < 4:
        print("Usage: python -m src <operation> <a> <b>")
        print("Operations: add, subtract, multiply, divide")
        sys.exit(1)

    operation = sys.argv[1]
    a = float(sys.argv[2])
    b = float(sys.argv[3])

    operations = {
        "add": add,
        "subtract": subtract,
        "multiply": multiply,
        "divide": divide,
    }

    if operation not in operations:
        print(f"Unknown operation: {operation}")
        sys.exit(1)

    result = operations[operation](a, b)
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
