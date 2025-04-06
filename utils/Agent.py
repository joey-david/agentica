import json


initial_prompt = """
You should think step by step in order to fullfill the objective by reasoning in a clear Thought/Action/Observation pattern.
Before starting the loop, write a clear plan on how to achieve the objective. Then, start the loop:
- You should first reflect with `Thought: {your_thoughts}` on the current situation.
During this step, if the objective is achieved, write your final answer/observation in the following format `Final Answer: {your_answer}`.
- Then, in an Action step, call one or several of the tools at your disposal in the format `Action: {JSON_BLOB}` to achieve the objective.
- After this you will receive the result of your Action step. You should reflect on this result and update your plan if necessary in the format `Observation: {result}`.
"""


class ToolCallingAgent:
    def __init__(self, tools: list, persistent_prompt: str):
        """
        Initialize the agent with tools and a model inference function.

        Args:
            tools (list): A list of Tool objects.
            persistent_prompt (str): A prompt to be used for the model inference at every step.
        """
        self.tools = {tool.name: tool for tool in tools}
        self.model_inference = model_inference
    

    def step(self, prompt: str) -> str:
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
        plan= self.model_inference(prompt)
        print(f"Plan: {plan}")
