# Simple Calculator

A basic Python calculator application with add, subtract, multiply, and divide operations.

## Installation

```bash
pip install -e .
```

## Usage

```bash
python -m src <operation> <a> <b>
```

### Examples

```bash
python -m src add 5 3        # Result: 8.0
python -m src subtract 10 4  # Result: 6.0
python -m src multiply 6 7   # Result: 42.0
python -m src divide 20 4    # Result: 5.0
```

## Project Structure

```
src/
├── __init__.py   # Package exports
├── add.py        # Addition operation
├── subtract.py   # Subtraction operation
├── multiply.py   # Multiplication operation
├── divide.py     # Division operation
└── main.py       # CLI entry point
```

## Known Issues

| # | Title | Status |
|---|-------|--------|
| 1 | Division by zero causes crash in divide() | Open |
| 2 | Negative number subtraction returns wrong result | Fixed |
| 3 | Large number multiplication causes overflow | Open |
| 4 | Missing input validation in main.py | Closed |

## Contributing

Please open an issue before submitting a pull request.
