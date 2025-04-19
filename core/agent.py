import json
import yaml
import re
from core.memory import Memory
from core.inference import get_inference
from core.tool import Tool, tool
from core.utils.display import Display, Colors

# Load prompts
initialization_prompt = yaml.safe_load(open("core/prompts/initialization.yaml", "r"))
observation_prompt = yaml.safe_load(open("core/prompts/observation.yaml", "r"))
thinking_prompt = yaml.safe_load(open("core/prompts/thinking.yaml", "r"))
specifications = yaml.safe_load(open("core/prompts/specifications.yaml", "r"))
memory_prompt = yaml.safe_load(open("core/prompts/memory.yaml", "r"))

class ToolCallingAgent:
    def __init__(self, tools: list, persistent_prompt: str, memory_instance: Memory = None, max_steps: int = 10, debug: bool = True):
        """
        Initialize the agent with tools and a model inference function.

        Args:
            tools (list): A list of Tool objects.
            persistent_prompt (str): A prompt to be used for the model inference at every step.
            memory_instance (Memory): An optional instance of the Memory class.
            max_steps (int): The maximum number of reasoning steps.
            debug (bool): Whether to print debug information to the console.
        """
        self.tools = {tool.name: tool for tool in tools}
        self.memory = memory_instance if memory_instance else Memory()
        self.persistent_prompt = persistent_prompt
        self.max_steps = max_steps
        self.display = Display(debug=debug)
        
        # Print welcome banner
        self.display.print_banner("AGENTICA TOOL AGENT INITIALIZED")

    def tools_prompt(self) -> str:
        """
        Returns a string representation of the tools available to the agent.
        """
        return "\n".join([tool.to_string() for tool in self.tools.values()])
    
    def memory_prompt(self) -> str:
        """
        Returns a string representation of the memory available to the agent.
        """
        return memory_prompt + "\n" + self.memory.get_history()

    def initialize_step(self, prompt: str) -> str:
        """
        Initialize the agent's state for the first step.
        Returns:
            The agent's plan, and stores it in memory.
        """
        self.display.print_step_header("INITIALIZATION")
            
        compiled_prompt = "\n".join([
            prompt,
            specifications,
            initialization_prompt,
            self.tools_prompt()
        ])
        
        response = get_inference(compiled_prompt)
        parsed_response = self.parse_response(response)
        
        if "Plan" in parsed_response:
            plan = parsed_response["Plan"]
            self.memory.add_structured_entry("Plan", plan)
            
            self.display.print_step_header("PLAN")
            print(f"{Colors.BRIGHT_GREEN}PLAN:{Colors.RESET}")
            print(self.display.format_content(plan, indent=2))
        else:
            raise ValueError("No valid plan found in the response.")
        return plan

    def thinking_step(self, prompt: str, step_num: int = None) -> str:
        """
        Perform a single step of reasoning and action.

        Args:
            prompt (str): The prompt to process.
            step_num (int): Current step number for display purposes.

        Returns:
            str: The response from the model.
        """
        self.display.print_step_header("THINKING", step_num)
            
        compiled_prompt = "\n".join([
            prompt,
            specifications,
            self.memory_prompt(),
            thinking_prompt,
            self.tools_prompt()
        ])
        
        response = get_inference(compiled_prompt)
        parsed_response = self.parse_response(response)
        
        # Display and store thought
        if "Thought" in parsed_response:
            thought = parsed_response["Thought"]
            self.display.print_thought(thought)
            self.memory.add_structured_entry("Thought", thought)
        
        # Store action in memory
        if "Action" in parsed_response:
            action_obj = parsed_response["Action"]
            
            actions_summary = []
            for action in action_obj.get("actions", []):
                tool_name = action.get("tool")
                tool_args = action.get("args", {})
                actions_summary.append(f"{tool_name}({', '.join([f'{k}={v}' for k, v in tool_args.items()])})")
            
            if actions_summary:
                self.memory.add_structured_entry("Action", ", ".join(actions_summary))
        
        return response
        
    def action_step(self, actions: dict, step_num: int = None) -> str:
        """
        Perform the action step of the agent by calling the specified tools.
        Args:
            actions (dict): A dictionary containing the tools to call and their arguments.
            step_num (int): Current step number for display purposes.
        Returns:
            str: The combined results of all tool calls in JSON format.
        """
        self.display.print_step_header("ACTION", step_num)
            
        results = {}
        tool_count = {}
        
        for action in actions.get("actions", []):
            # Get tool info
            tool_name = action.get("tool")
            tool_args = action.get("args", {})
            
            # Skip if tool not found
            if tool_name not in self.tools:
                error_msg = f"Error: Tool '{tool_name}' not found."
                results[f"{tool_name}_error"] = error_msg
                self.display.print_error(error_msg)
                continue
                
            # Create unique key for this tool call
            count = tool_count.get(tool_name, 0)
            tool_count[tool_name] = count + 1
            key = f"{tool_name}_{count}" if count > 0 else tool_name
            
            # For location-based lookups, include location in key
            if "location" in tool_args:
                key = f"{tool_name}_{tool_args['location']}"
            
            # Call the tool
            args_str = ", ".join([f"{k}={repr(v)}" for k, v in tool_args.items()])
            self.display.print_tool_call(tool_name, args_str)
                
            try:
                result = self.tools[tool_name](**tool_args)
                
                # Handle non-JSON serializable objects
                try:
                    # Test if result is JSON serializable
                    json.dumps(result)
                    results[key] = result
                except TypeError:
                    # If not serializable, convert it to a string representation
                    if hasattr(result, '__str__'):
                        results[key] = f"[Non-serializable object: {str(result)}]"
                    else:
                        results[key] = f"[Non-serializable object of type: {type(result).__name__}]"
                    self.display.print_error(f"Warning: Result from {tool_name} is not JSON serializable, using string representation")
                    
                self.display.print_tool_result(results[key])
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                results[key] = error_msg
                self.display.print_error(error_msg)
        
        # Store formatted results in memory
        if results:
            formatted = []
            for key, result in results.items():
                tool_name = key.split('_')[0]
                param_info = '_'.join(key.split('_')[1:]) if '_' in key else ''
                header = f"Tool: {tool_name}" + (f" ({param_info})" if param_info else "")
                formatted.append(f"{header}\nResult: {result}")
            
            self.memory.add_structured_entry("Results", "\n\n".join(formatted))
        
        # Safely convert results to JSON
        try:
            return json.dumps({"results": results})
        except TypeError:
            # If we still have serialization issues, create a safe version of the results
            safe_results = {}
            for key, value in results.items():
                try:
                    # Test if this specific value serializes correctly
                    json.dumps(value)
                    safe_results[key] = value
                except TypeError:
                    # If not, use a string representation
                    safe_results[key] = str(value)
            
            return json.dumps({"results": safe_results})

    def observation_step(self, results: str, prompt: str, step_num: int = None) -> str:
        """
        Process the results of the actions and generate an observation.

        Args:
            results (str): The results of the action step.
            prompt (str): The original prompt.
            step_num (int): Current step number for display purposes.

        Returns:
            str: The observation generated by the model.
        """
        self.display.print_step_header("OBSERVATION", step_num)
            
        compiled_prompt = "\n".join([
            prompt,
            specifications,
            observation_prompt,
            self.memory_prompt(),
            f"Results: {results}",
        ])
        
        response = get_inference(compiled_prompt)
        parsed_response = self.parse_response(response)
        
        if "Observation" in parsed_response:
            observation = parsed_response["Observation"]
            self.memory.add_structured_entry("Observation", observation)
            self.display.print_observation(observation)
        
        return response

    def run(self, prompt: str) -> str:
        """
        Runs the agent's reasoning and action loop.

        Args:
            prompt (str): The initial prompt to start the reasoning process.

        Returns:
            str: The final answer after reasoning and actions.
        """
        step = 0
        prompt = self.persistent_prompt + prompt
        self.initialize_step(prompt=prompt)
        
        while step < self.max_steps:
            step += 1
            
            # Thinking step
            thoughts_actions = self.thinking_step(prompt, step)
            parsed_response = self.parse_response(thoughts_actions)
            
            # Action step
            if "Action" in parsed_response:
                results = self.action_step(parsed_response["Action"], step)
                
                # Observation step
                observation = self.observation_step(results, prompt, step)
                parsed_response = self.parse_response(observation)

                # if the model has a final answer, return it and stop
                if "Final_Answer" in parsed_response:
                    final_answer = parsed_response["Final_Answer"]
                    self.memory.add_structured_entry("Final_Answer", final_answer)
                    
                    self.display.print_step_header("FINAL ANSWER")
                    self.display.print_final_answer(final_answer)
                        
                    return final_answer

        self.display.print_max_steps_reached()
        print(f"\n{Colors.BRIGHT_BLACK}Memory dump:{Colors.RESET}")
        print(self.display.format_content(self.memory.get_all()))
            
        raise ValueError("Max steps reached without finding a final answer.") 

    def contains_final_answer(self, response: str) -> bool:
        """
        Check if the response contains a final answer.

        Args:
            response (str): The model's response.

        Returns:
            bool: True if a final answer is found, False otherwise.
        """
        return "Final_Answer" in response
    
    def parse_response(self, response: str) -> dict:
        """
        Parse the model's response to extract all matches for action, plan, thought, observation, or final answer.

        Args:
            response (str): The model's response.

        Returns:
            dict: A dictionary where keys are the types (Plan, Thought, Action, Observation, Final_Answer) 
                    and values are the corresponding content.
        """
        parsed_response = {}
        
        # Extract different components from the response
        parsed_response.update(self._extract_text_components(response))
        parsed_response.update(self._extract_action_component(response))
        
        if not parsed_response:
            raise ValueError("No valid patterns found in the response.")

        return parsed_response

    def _extract_text_components(self, response: str) -> dict:
        """
        Extract text components (Plan, Thought, Observation, Final_Answer) from the response.
        
        Args:
            response (str): The model's response.
            
        Returns:
            dict: Dictionary of extracted text components
        """
        components = {}
        patterns = {
            "Plan": r"Plan:?\s*\{?(.*?)\}?(?=\n\n|$)",
            "Thought": r"Thought:?\s*\{?(.*?)\}?(?=\n\n|Action:|$)",
            "Observation": r"Observation:?\s*\{?(.*?)\}?(?=\n\n|$)",
            "Final_Answer": r"Final_Answer:?\s*\{?(.*?)\}?(?=\n\n|$)"
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, response, re.DOTALL)
            if match:
                components[key] = match.group(1).strip()
        
        return components

    def _extract_action_component(self, response: str) -> dict:
        """
        Extract and parse the Action component from the response.
        
        Args:
            response (str): The model's response.
            
        Returns:
            dict: Dictionary with the Action key if found
        """
        components = {}
        pattern = r"Action:?\s*(\{.*\})"
        match = re.search(pattern, response, re.DOTALL)
        
        if match:
            content = match.group(1).strip()
            try:
                action_json = content
                components["Action"] = self._normalize_action_json(action_json)
            except json.JSONDecodeError as e:
                self.display.print_error(f"JSON parsing error: {e}")
                self.display.print_error(f"Content: {content}")
                raise ValueError(f"Invalid JSON format in the Action response. Error: {str(e)}")
        
        return components

    def _normalize_action_json(self, action_json: str) -> dict:
        """
        Normalize and parse the action JSON string.
        
        Args:
            action_json (str): The JSON string to normalize and parse.
            
        Returns:
            dict: The parsed JSON object.
        """
        # Check if the JSON structure is correct
        parsed_json = json.loads(action_json)
        
        if "actions" not in parsed_json:
            # Try to fix the structure if "Actions" is used instead of "actions"
            action_json = action_json.replace('"Actions"', '"actions"')
            action_json = action_json.replace('"ACTIONS"', '"actions"')
            # Handle cases where quote marks are added on the sides of keys
            action_json = action_json.replace("'actions'", '"actions"')
            action_json = action_json.replace("'tool'", '"tool"')
            action_json = action_json.replace("'args'", '"args"')
            parsed_json = json.loads(action_json)
            
        return parsed_json