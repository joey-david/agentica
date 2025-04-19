import json
import yaml
from core.memory import Memory
from core.inference import get_inference
from core.tool import Tool, tool
import re
from datetime import datetime
import textwrap

# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

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
        self.debug = debug
        # Print welcome banner
        if self.debug:
            self._print_banner("AGENTICA TOOL AGENT INITIALIZED")

    def _print_banner(self, text):
        """Print a stylish banner with the given text"""
        width = len(text) + 4
        border = "┌" + "─" * width + "┐"
        content = "│  " + text + "  │"
        bottom = "└" + "─" * width + "┘"
        
        print(f"\n{Colors.BOLD}{Colors.BLUE}{border}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{content}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{bottom}{Colors.RESET}\n")

    def _print_step_header(self, step_type, step_num=None):
        """Print a step header with the given step type and number"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if step_num is not None:
            header = f" {step_type.upper()} (STEP {step_num}) - {timestamp} "
        else:
            header = f" {step_type.upper()} - {timestamp} "
        
        color = {
            "INITIALIZATION": Colors.BG_BLUE + Colors.WHITE,
            "THINKING": Colors.BG_MAGENTA + Colors.WHITE,
            "ACTION": Colors.BG_GREEN + Colors.BLACK,
            "RESULTS": Colors.BG_CYAN + Colors.BLACK,
            "OBSERVATION": Colors.BG_YELLOW + Colors.BLACK,
            "FINAL ANSWER": Colors.BG_GREEN + Colors.WHITE + Colors.BOLD
        }.get(step_type.upper(), Colors.BG_WHITE + Colors.BLACK)
        
        print(f"\n{color}{header}{Colors.RESET}\n")

    def _format_content(self, content, indent=0, width=100):
        """Format content with proper indentation and wrapping"""
        if isinstance(content, dict) or isinstance(content, list):
            formatted = json.dumps(content, indent=2)
        else:
            formatted = str(content)
            
        # Wrap text to specified width
        lines = formatted.split('\n')
        wrapped_lines = []
        for line in lines:
            if len(line) > width:
                wrapped = textwrap.wrap(line, width=width)
                wrapped_lines.extend(wrapped)
            else:
                wrapped_lines.append(line)
                
        # Apply indentation
        indented = [" " * indent + line for line in wrapped_lines]
        return "\n".join(indented)

    def _print_json(self, data, title=None):
        """Print JSON data with syntax highlighting"""
        if title:
            print(f"{Colors.BRIGHT_BLUE}{title}{Colors.RESET}")
            
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                pass
                
        if isinstance(data, dict) or isinstance(data, list):
            # Convert to string with indentation
            json_str = json.dumps(data, indent=2)
            
            # Syntax highlighting
            json_str = json_str.replace('"', f'{Colors.GREEN}"') \
                             .replace('": ', f'"{Colors.RESET}: {Colors.YELLOW}') \
                             .replace(',', f'{Colors.RESET},')
                             
            print(json_str + Colors.RESET)
        else:
            print(data)

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
        if self.debug:
            self._print_step_header("INITIALIZATION")
            
        compiled_prompt = "\n".join([
            prompt,
            specifications,
            initialization_prompt,
            self.tools_prompt()
        ])
        
        response = get_inference(compiled_prompt)
        
        # if self.debug:
        #     print(f"{Colors.BRIGHT_CYAN}LLM RESPONSE:{Colors.RESET}")
        #     print(self._format_content(response))
        
        parsed_response = self.parse_response(response)
        if "Plan" in parsed_response:
            plan = parsed_response["Plan"]
            self.memory.add_structured_entry("Plan", plan)
            
            if self.debug:
                print(f"\n{Colors.BRIGHT_GREEN}PLAN:{Colors.RESET}")
                print(self._format_content(plan, indent=2))
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
        if self.debug:
            self._print_step_header("THINKING", step_num)
            
        compiled_prompt = "\n".join([
            prompt,
            specifications,
            self.memory_prompt(),
            thinking_prompt,
            self.tools_prompt()
        ])
        
        response = get_inference(compiled_prompt)
        
        if self.debug:
            print(f"{Colors.BRIGHT_MAGENTA}THINKING:{Colors.RESET}")
            
        parsed_response = self.parse_response(response)
        
        # Display thought
        if "Thought" in parsed_response and self.debug:
            thought = parsed_response["Thought"]
            print(f"{Colors.MAGENTA}{self._format_content(thought, indent=2)}{Colors.RESET}\n")
            self.memory.add_structured_entry("Thought", thought)
        
        # Display action
        if "Action" in parsed_response and self.debug:
            action_obj = parsed_response["Action"]
            # print(f"{Colors.BRIGHT_GREEN}ACTION:{Colors.RESET}")
            # self._print_json(action_obj)
            
            # Store action in memory
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
        if self.debug:
            self._print_step_header("ACTION", step_num)
            
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
                if self.debug:
                    print(f"{Colors.RED}{error_msg}{Colors.RESET}")
                continue
                
            # Create unique key for this tool call
            count = tool_count.get(tool_name, 0)
            tool_count[tool_name] = count + 1
            key = f"{tool_name}_{count}" if count > 0 else tool_name
            
            # For location-based lookups, include location in key
            if "location" in tool_args:
                key = f"{tool_name}_{tool_args['location']}"
            
            # Call the tool
            if self.debug:
                args_str = ", ".join([f"{k}={repr(v)}" for k, v in tool_args.items()])
                print(f"{Colors.BRIGHT_GREEN}CALLING:{Colors.RESET} {Colors.GREEN}{tool_name}({args_str}){Colors.RESET}")
                
            try:
                result = self.tools[tool_name](**tool_args)
                results[key] = result
                if self.debug:
                    print(f"{Colors.BRIGHT_CYAN}RESULT:{Colors.RESET}")
                    print(f"{Colors.CYAN}{self._format_content(result, indent=2)}{Colors.RESET}\n")
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                results[key] = error_msg
                if self.debug:
                    print(f"{Colors.RED}{error_msg}{Colors.RESET}\n")
        
        # Store formatted results in memory
        if results:
            formatted = []
            for key, result in results.items():
                tool_name = key.split('_')[0]
                param_info = '_'.join(key.split('_')[1:]) if '_' in key else ''
                header = f"Tool: {tool_name}" + (f" ({param_info})" if param_info else "")
                formatted.append(f"{header}\nResult: {result}")
            
            self.memory.add_structured_entry("Results", "\n\n".join(formatted))
        
        # Return JSON results
        return json.dumps({"results": results})

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
        if self.debug:
            self._print_step_header("OBSERVATION", step_num)
            
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
            
            if self.debug:
                print(f"{Colors.BRIGHT_YELLOW}OBSERVATION:{Colors.RESET}")
                print(f"{Colors.YELLOW}{self._format_content(observation, indent=2)}{Colors.RESET}")
        
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
                    
                    if self.debug:
                        self._print_step_header("FINAL ANSWER")
                        print(f"{Colors.GREEN}{self._format_content(final_answer)}{Colors.RESET}\n")
                        
                    return final_answer

        if self.debug:
            print(f"\n{Colors.RED}MAX STEPS REACHED WITHOUT FINAL ANSWER{Colors.RESET}")
            print(f"\n{Colors.BRIGHT_BLACK}Memory dump:{Colors.RESET}")
            print(self._format_content(self.memory.get_all()))
            
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
                if self.debug:
                    print(f"{Colors.RED}JSON parsing error: {e}{Colors.RESET}")
                    print(f"{Colors.RED}Content: {content}{Colors.RESET}")
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


### OUTDATED
if __name__ == "__main__":
    raise("This is an outdated test script. Please refer to the test_agent.py file for updated tests.")
    # Import necessary components
    from Weather_Agent import get_weather
    
    # Create a test agent with just the weather tool
    test_agent = ToolCallingAgent(
        [get_weather],
        persistent_prompt="You are a weather assistant. You can provide weather information for any city, using the tools at your disposal. Make sure to follow the thought/action/observation loop.",
        max_steps=3
    )
    
    # Create a test action with multiple tool calls
    test_actions = {
        "actions": [
            {
                "tool": "get_weather",
                "args": {"location": "Tokyo"}
            },
            {
                "tool": "get_weather", 
                "args": {"location": "New York"}
            }
        ]
    }
    
    # Execute the actions
    print("Testing multiple tool calls in a single action...")
    results = test_agent.action_step(test_actions)
    print("\nRaw JSON results:")
    print(results)
    
    # Extract and print the formatted results from memory
    print("\nFormatted results from memory:")
    for entry in test_agent.memory.structured_history:
        if entry["type"] == "Results":
            print(entry["content"])
    