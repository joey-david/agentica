from utils.Agent import ToolCallingAgent
import requests
from utils.Tool import tool
import os
from dotenv import load_dotenv

@tool
def get_weather(location: str) -> str:
    """
    Fetches the weather information for a given city using an actual weather API.
    Arguments:
        location (str): The name of the city to fetch the weather for.
    Returns:
        str: A string containing the weather information.
    """
    load_dotenv()
    api_key = os.getenv("OPENWEATHER_API")  # Replace with your actual API key
    base_url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": ''.join(c if c.isalnum() or c==" " else '' for c in location),
        "appid": api_key,
        "units": "metric"
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        weather_description = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        temp_min = data["main"]["temp_min"]
        temp_max = data["main"]["temp_max"]
        wind_speed = data["wind"]["speed"]
        humidity = data["main"]["humidity"]
        
        return (f"The weather in {location} is {weather_description}, "
                f"with a temperature of {temp}°C (high of {temp_max}°C, low of {temp_min}°C). "
                f"The wind is blowing at {wind_speed} m/s. "
                f"The humidity level is {humidity}%.")
    except requests.exceptions.RequestException as e:
        return f"Failed to fetch weather data: {e}"
    except KeyError:
        return "Could not retrieve weather information. Please check the city name or try again later."

Agent = ToolCallingAgent(
    [get_weather],
    persistent_prompt="You are a weather assistant. You can provide weather information for any city, using the tools at your disposal. Make sure to follow the thought/action/observation loop.",
)

if __name__ == "__main__":
    city_name = "Tokyo"
    weather_info = Agent.run(f"For a nice walk right now, should I teleport to tokyo or new york?")
    print(weather_info)