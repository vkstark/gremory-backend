from typing import Dict, Optional
from langchain_core.tools import tool

@tool
def get_weather(location: str) -> Optional[Dict]:
    """
    Get the current weather if a location is provided.

    Args:
        location: The name of the location to get the weather for

    Returns:
        Dictionary containing weather information, or error details if failed
        
    Example:
        >>> weather = await get_weather("London", "your-api-key")
        >>> print(f"Temperature: {weather['temperature_celsius']}°C")
    """
    pass

@tool
def add(a: int, b: int) -> Optional[int]:
    """
    Add two integers.

    Args:
        a: First integer
        b: Second integer

    Returns:
        The sum of a and b

    Example:
        >>> result = add(2, 3)
        >>> print(result)
    """
    pass