# Remove
from langchain.tools import tool

import os
from typing import Dict
import requests
from requests.structures import CaseInsensitiveDict
from common_utils.logger import logger

GEOAPIFY_API_KEY = os.getenv('GEOAPIFY_API_KEY', "")  # Replace with your Geoapify API key

import requests
from typing import Dict, Tuple

class WeatherAPIError(Exception):
    """Custom exception for weather API errors."""
    pass

class GeocodingError(Exception):
    """Custom exception for geocoding errors."""
    pass

def get_coordinates(location: str, api_key: str) -> Tuple[float, float]:
    """
    Get latitude and longitude coordinates for a given location.
    
    Args:
        location: The location name or address to geocode
        api_key: Geoapify API key
        
    Returns:
        Tuple of (latitude, longitude)
        
    Raises:
        GeocodingError: If geocoding fails or no results found
    """
    url = "https://api.geoapify.com/v1/geocode/search"
    params = {
        "text": location.strip(),
        "apiKey": api_key,
        "limit": 1  # Only need the first result
    }
    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("features"):
            raise GeocodingError(f"No location found for: {location}")
            
        feature = data["features"][0]
        coordinates = feature["geometry"]["coordinates"]
        formatted_address = feature["properties"].get("formatted", location)
        
        longitude, latitude = coordinates
        logger.info(f"Found coordinates for '{formatted_address}': {latitude}, {longitude}")
        
        return latitude, longitude
        
    except requests.RequestException as e:
        raise GeocodingError(f"Geocoding request failed: {str(e)}")
    except (KeyError, IndexError, ValueError) as e:
        raise GeocodingError(f"Invalid geocoding response format: {str(e)}")

def get_weather_data(latitude: float, longitude: float) -> Dict:
    """
    Get weather data for given coordinates.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        
    Returns:
        Dictionary containing weather data
        
    Raises:
        WeatherAPIError: If weather API request fails
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "timezone": "auto",
        "forecast_days": 1
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if "current" not in data:
            raise WeatherAPIError("Invalid weather API response format")
            
        return data
        
    except requests.RequestException as e:
        raise WeatherAPIError(f"Weather API request failed: {str(e)}")

def format_weather_response(weather_data: Dict, location: str) -> Dict:
    """
    Format weather data into a clean response.
    
    Args:
        weather_data: Raw weather data from API
        location: Original location query
        
    Returns:
        Formatted weather information
    """
    current = weather_data.get("current", {})
    
    return {
        "location": location,
        "temperature_celsius": current.get("temperature_2m"),
        "humidity_percent": current.get("relative_humidity_2m"),
        "wind_speed_ms": current.get("wind_speed_10m"),
        "weather_code": current.get("weather_code"),
        "timestamp": current.get("time"),
        "timezone": weather_data.get("timezone")
    }

@tool
def get_weather(location: str) -> Dict:
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
    if not location or not location.strip():
        return {"error": "Location cannot be empty"}
        
    if not GEOAPIFY_API_KEY:
        return {"error": "Geoapify API key is required"}
    
    try:
        # Get coordinates for the location
        latitude, longitude = get_coordinates(location, GEOAPIFY_API_KEY)
        
        # Get weather data
        weather_data = get_weather_data(latitude, longitude)
        
        # Format and return response
        formatted_response = format_weather_response(weather_data, location)
        
        logger.info(f"Successfully retrieved weather for {location}")
        return formatted_response
        
    except (GeocodingError, WeatherAPIError) as e:
        error_msg = f"Failed to get weather for '{location}': {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error getting weather for '{location}': {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}
