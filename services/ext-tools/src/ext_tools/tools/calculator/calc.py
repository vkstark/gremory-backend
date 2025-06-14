from langchain_core.tools import tool

@tool
def add(a: int, b: int) -> int:
    """
    Add two integers.

    Args:
        a: First integer
        b: Second integer

    Returns:
        The sum of a and b
    """
    return a + b

@tool
def subtract(a: int, b: int) -> int:
    """
    Subtract two integers.

    Args:
        a: First integer
        b: Second integer

    Returns:
        The result of a minus b
    """
    return a - b

@tool
def multiply(a: int, b: int) -> int:
    """
    Multiply two integers.

    Args:
        a: First integer
        b: Second integer

    Returns:
        The product of a and b
    """
    return a * b

@tool
def divide(a: int, b: int) -> float:
    """
    Divide two integers.

    Args:
        a: First integer
        b: Second integer

    Returns:
        The result of a divided by b
    """
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b

@tool
def power(base: int, exponent: int) -> int:
    """
    Raise a number to the power of another.

    Args:
        base: The base integer
        exponent: The exponent integer

    Returns:
        The result of base raised to the power of exponent
    """
    return base ** exponent
