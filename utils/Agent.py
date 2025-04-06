import json
import yaml
from utils.Memory import Memory
from utils.Inference import get_inference
from utils.Tool import Tool
import re

initialization_prompt = yaml.safe_load(open("utils/prompts/initialization.yaml", "r"))
observation_prompt = yaml.safe_load(open("utils/prompts/observation.yaml", "r"))
thinking_prompt = yaml.safe_load(open("utils/prompts/thinking.yaml", "r"))
specifications = yaml.safe_load(open("utils/prompts/specifications.yaml", "r"))

class ToolCallingAgent:
    def __init__(self, tools: list, persistent_prompt: str, memory_instance: Memory = None):
        """
        Initialize the agent with tools and a model inference function.

        Args:
            tools (list): A list of Tool objects.
            persistent_prompt (str): A prompt to be used for the model inference at every step.
        """
        self.tools = {tool.name: tool for tool in tools}
        self.memory = memory_instance if memory_instance else Memory(persistent_prompt=persistent_prompt)


    def parse_response(self, response: str) -> list:
        """
        Parse the model's response to extract all matches for action, plan, thought, observation, or final answer.

        Args:
            response (str): The model's response.

        Returns:
            list: A list of dictionaries, each containing the type (Plan, Thought, Action, Observation, Final_Answer) 
                  and the corresponding content.
        """

        patterns = {
            "Plan": r"Plan:\s*\{(.*?)\}",
            "Thought": r"Thought:\s*\{(.*?)\}",
            "Action": r"Action:\s*\{(.*?)\}",
            "Observation": r"Observation:\s*\{(.*?)\}",
            "Final_Answer": r"Final_Answer:\s*\{(.*?)\}"
        }

        matches = []
        for key, pattern in patterns.items():
            for match in re.finditer(pattern, response, re.DOTALL):
                content = match.group(1).strip()
                if key == "Action":
                    try:
                        matches.append({"type": key, "content": json.loads(f"{{{content}}}")})
                    except json.JSONDecodeError:
                        raise ValueError("Invalid JSON format in the Action response.")
                else:
                    matches.append({"type": key, "content": content})

        if not matches:
            raise ValueError("No valid patterns found in the response.")

        return matches

    def initialize_step(self) -> str:
        """
        Initialize the agent's state for the first step.
        This method can be overridden in subclasses to provide custom initialization.
        Returns:
            The agent's plan, and stores in it memory.
        """
        # Initialize the agent's state here

        
    def thinking_step(self, prompt: str) -> str:
        """
        Perform a single step of reasoning and action.
        Args:
            prompt (str): The prompt to process.
        Returns:
            str: The response from the model.
        """        
        
    def run(self, prompt: str) -> str:
        """
        Runs the agent's reasoning and action loop.
        
        Args:
            prompt (str): The initial prompt to start the reasoning process.
        
        Returns:
            str: The final answer after reasoning and actions.
        """
        finalThought = False
        state = self.initialize_step()
        while (not finalThought):
            thoughts_actions = self.thinking_step()
            # Parse the response to extract all matches for action, plan, thought, observation, or final answer
            parsed_thoughts_actions = self.parse_response(thoughts_actions)

            # Add the thought to the memory
            self.memory.add_to_history(parsed_response)
            if "Final_Answer" in parsed_response:
                finalThought = True
                print(f"Final Answer: {parsed_response["Final_Answer"]}")
                return parsed_response["Final_Answer"]
            
            observation = self.observation_step()
            parsed_response = self.parse_response(observation)
            if "Observation" in parsed_response:
                observation = parsed_response["Observation"]
                print(f"Observation: {observation}")
                self.memory.add("lastObservation", observation)



    def contains_final_answer(self, response: str) -> bool:
        """
        Check if the response contains a final answer.

        Args:
            response (str): The model's response.

        Returns:
            bool: True if a final answer is found, False otherwise.
        """
        return "Final_Answer" in response

if __name__ == "__main__":
    print(specifications)