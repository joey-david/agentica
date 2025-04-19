from core.agent import ToolCallingAgent
from tools import get_weather

Agent = ToolCallingAgent(
    [get_weather],
    persistent_prompt="You are a weather assistant. You can provide weather information for any city, using the tools at your disposal. Make sure to follow the thought/action/observation loop.",
)

if __name__ == "__main__":
    print("Welcome to the Weather Agent!")
    print("Ask any weather-related question, and I'll do my best to help you.")
    prompt = input("Prompt: ")
    weather_info = Agent.run(prompt)
    print(weather_info)