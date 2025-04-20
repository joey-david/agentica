from core.agent import ToolCallingAgent
from agents.weather_agent.tools import get_weather
from core.utils.config import load_agent_config

config = load_agent_config(agent_name="weather_agent")
NAME = config["name"]
DESCRIPTION = config["description"]
PERSISTENT_PROMPT = config.get("persistent prompt")
MAX_STEPS = config.get("max steps", 20)
VERBOSE = config["logging"].get("verbose", True)

Agent = ToolCallingAgent(
    [get_weather],
    persistent_prompt=PERSISTENT_PROMPT,
    max_steps=MAX_STEPS,
    debug=VERBOSE
)

# Add this function to serve as the main entrypoint
def main():
    print(NAME)
    print(DESCRIPTION)
    prompt = input("Prompt: ")
    results = Agent.run(prompt)
    print(results)

# The __main__ block should call this function
if __name__ == "__main__":
    main()