from utils.Agent import ToolCallingAgent
import requests
from utils.Tool import tool

@tool
def get_weather(location) -> str:
    """
    Fetches the weather information for a given city.
    Arguments:
        location (str): The name of the city to fetch the weather for.
    Returns:
        str: A string containing the weather information.
    """
    return f"the weather in {location} is sunny, with a high of 25°C and a low of 15°C. The wind is blowing at 10 km/h from the north. There is a 10% chance of rain. The humidity level is 60%."

Agent = ToolCallingAgent(
    [get_weather],
    persistent_prompt="You are a weather assistant. You can provide weather information for any city, using the tools at your disposal.",
)

if __name__ == "__main__":
    city_name = "New York"
    weather_info = Agent.run(f"What's the weather like in {city_name}?")
    print(weather_info)