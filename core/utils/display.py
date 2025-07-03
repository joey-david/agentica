import json
import textwrap
from datetime import datetime

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

class Display:
    def __init__(self, debug: bool = True):
        self.debug = debug
    
    def print_banner(self, text):
        """Print a stylish banner with the given text"""
        if not self.debug:
            return
            
        width = len(text) + 4
        border = "┌" + "─" * width + "┐"
        content = "│  " + text + "  │"
        bottom = "└" + "─" * width + "┘"
        
        print(f"\n{Colors.BOLD}{Colors.BLUE}{border}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{content}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{bottom}{Colors.RESET}\n")

    def print_step_header(self, step_type, step_num=None):
        """Print a step header with the given step type and number"""
        if not self.debug:
            return
            
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

    def print_memory_update(self, op, text):
        """Print a memory update with the given operation and text"""
        if not self.debug:
            return
        
        color = {
            "STORE": Colors.BG_BLUE + Colors.WHITE,
            "RETRIEVE": Colors.BG_CYAN + Colors.BLACK,
            "DELETE": Colors.BG_RED + Colors.WHITE,
        }.get(op.upper(), Colors.BG_WHITE + Colors.BLACK)
        
        print(f"\n{color} {op.upper()} {Colors.RESET} {text}\n")

    def print_llm_input(self, prompt):
        """Print the LLM input prompt"""
        if not self.debug:
            return
        
        self.print_step_header("LLM INPUT")
        print(self.format_content(prompt))

    def print_llm_output(self, response):
        """Print the LLM output response"""
        if not self.debug:
            return
        
        self.print_step_header("LLM OUTPUT")
        print(self.format_content(response))

    def print_no_tool_call(self):
        """Print a message when no tool call is made"""
        if not self.debug:
            return
        print(f"{Colors.BOLD}{Colors.YELLOW}No tool call was made in this step.{Colors.RESET}")

    def format_content(self, content, indent=0, width=100):
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

    def print_json(self, data, title=None):
        """Print JSON data with syntax highlighting"""
        if not self.debug:
            return
            
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
            
    def print_error(self, message):
        """Print an error message"""
        if not self.debug:
            return
        print(f"{Colors.RED}{message}{Colors.RESET}")
    
    def print_thought(self, thought):
        """Print a thought with proper formatting"""
        if not self.debug:
            return
        print(f"{Colors.BRIGHT_MAGENTA}THINKING:{Colors.RESET}")
        print(f"{Colors.MAGENTA}{self.format_content(thought, indent=2)}{Colors.RESET}\n")
    
    def print_tool_call(self, tool_name, args_str):
        """Print a tool call with proper formatting"""
        if not self.debug:
            return
        print(f"{Colors.BRIGHT_GREEN}CALLING:{Colors.RESET} {Colors.GREEN}{tool_name}({args_str}){Colors.RESET}")
    
    def print_tool_result(self, result):
        """Print a tool result with proper formatting"""
        if not self.debug:
            return
        print(f"{Colors.BRIGHT_CYAN}RESULT:{Colors.RESET}")
        print(f"{Colors.CYAN}{self.format_content(result, indent=2)}{Colors.RESET}\n")
    
    def print_observation(self, observation):
        """Print an observation with proper formatting"""
        if not self.debug:
            return
        print(f"{Colors.BRIGHT_YELLOW}OBSERVATION:{Colors.RESET}")
        print(f"{Colors.YELLOW}{self.format_content(observation, indent=2)}{Colors.RESET}")
    
    def print_memory_operation(self, message: str) -> None:
        """Print memory operation message with appropriate formatting."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n {Colors.CYAN}MEMORY ({timestamp}){Colors.RESET} - {message}")
    
    def print_final_answer(self, answer):
        """Print a final answer with proper formatting"""
        if not self.debug:
            return
        print(f"{Colors.GREEN}{self.format_content(answer)}{Colors.RESET}\n")
    
    def print_max_steps_reached(self):
        """Print a message indicating that the maximum number of steps was reached"""
        if not self.debug:
            return
        print(f"\n{Colors.RED}MAX STEPS REACHED WITHOUT FINAL ANSWER{Colors.RESET}")