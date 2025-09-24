import os
import sys
import argparse
import importlib.util
from pathlib import Path
import yaml
from core.utils.display import Colors

def load_agent_module(agent_path):
    """Dynamically load an agent module from path."""
    spec = importlib.util.spec_from_file_location("agent_module", agent_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {agent_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def get_available_agents():
    """Get all available agents from the agents directory."""
    agents = {}
    agents_dir = Path("agents")
    
    if not agents_dir.exists():
        print(f"{Colors.RED}Error: 'agents' directory not found!{Colors.RESET}")
        return {}
    
    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue
            
        agent_name = agent_dir.name
        agent_path = agent_dir / "agent.py"
        config_path = agent_dir / "config.yaml"
        
        if agent_path.exists():
            # Get description from config if available
            description = "No description available"
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                        if config and 'description' in config:
                            description = config['description']
                except Exception:
                    pass
            
            agents[agent_name] = {
                "name": agent_name,
                "path": str(agent_path),
                "description": description
            }
    
    return agents

def print_banner():
    """Print the ASCII banner for Agentica."""
    banner = r"""
    █████╗  ██████╗ ███████╗███╗   ██╗████████╗██╗ ██████╗ █████╗ 
   ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██║██╔════╝██╔══██╗
   ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║██║     ███████║
   ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║██║     ██╔══██║
   ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ██║╚██████╗██║  ██║
   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝ ╚═════╝╚═╝  ╚═╝
   """
    print(f"{Colors.BRIGHT_CYAN}{banner}{Colors.RESET}")
    print(f"{Colors.BRIGHT_BLUE}A collection of LLM agents for various tasks{Colors.RESET}")
    print(f"{Colors.BRIGHT_BLACK}https://github.com/joey-david/agentica{Colors.RESET}")
    print("\n" + "=" * 70 + "\n")

def display_logo(agent_name):
    """Display agent ASCII logo if available."""
    config_path = Path(f"agents/{agent_name}/config.yaml")
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                # Look for either 'logo' or 'ascii_logo' key
                logo = config.get('logo', config.get('ascii_logo', ''))
                if logo:
                    print(f"{Colors.BRIGHT_CYAN}{logo}{Colors.RESET}")
                else:
                    print(f"{Colors.BRIGHT_BLACK}(No ASCII logo found in config.yaml){Colors.RESET}")
        except Exception:
            pass

def print_agents_menu(agents):
    """Print available agents menu."""
    if not agents:
        print(f"{Colors.RED}No agents found in the 'agents' directory.{Colors.RESET}")
        return 0
        
    print(f"{Colors.BRIGHT_GREEN}Available Agents:{Colors.RESET}\n")
    
    for i, (name, details) in enumerate(sorted(agents.items()), 1):
        print(f"{Colors.BRIGHT_WHITE}{i}. {name}{Colors.RESET}")
        print(f"   {Colors.BRIGHT_BLACK}{details['description']}{Colors.RESET}")
        print()
    
    return len(agents)

def run_agent(agent_name, prompt=None, debug_llm=True):
    """Run the specified agent."""
    agents = get_available_agents()
    if agent_name not in agents:
        print(f"{Colors.RED}Error: Agent '{agent_name}' not found!{Colors.RESET}")
        return
    
    agent_path = agents[agent_name]["path"]
    
    try:
        # Add parent dir to path for imports
        sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(agent_path))))
        
        # Load agent module
        agent_module = load_agent_module(agent_path)
        
        print(f"\n{Colors.BRIGHT_BLUE}Running {agent_name.upper()} Agent{Colors.RESET}")
        display_logo(agent_name)
        
        # Run agent
        if hasattr(agent_module, 'Agent'):
            # Ensure debug output is always enabled
            agent_module.Agent.debug_llm = True
            if getattr(agent_module.Agent, "display", None) is not None:
                agent_module.Agent.display.debug = True
            
            if prompt:
                result = agent_module.Agent.run(prompt)
                print(f"\n{Colors.GREEN}Result:{Colors.RESET}")
                print(result)
            elif hasattr(agent_module, 'main'):
                # Call main function if it exists
                agent_module.main()
            elif "__main__" in agent_module.__dict__:
                # Run the script directly
                sys.argv = [agent_path]
                exec(open(agent_path).read())
            else:
                print(f"{Colors.YELLOW}Warning: Agent '{agent_name}' doesn't define a main entrypoint.{Colors.RESET}")
                # Default behavior - run with empty prompt
                result = agent_module.Agent.run("Help me use this agent")
                print(result)
        else:
            print(f"{Colors.RED}Error: '{agent_name}' doesn't define an 'Agent' object.{Colors.RESET}")
            
    except Exception as e:
        print(f"{Colors.RED}Error running agent '{agent_name}': {e}{Colors.RESET}")

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Agentica - A collection of LLM agents")
    parser.add_argument("--agent", "-a", help="Run a specific agent by name")
    parser.add_argument("--list", "-l", action="store_true", help="List all available agents")
    parser.add_argument("--prompt", "-p", help="Provide a prompt for the agent")
    parser.add_argument("--debug", "-d", action="store_true", default=True, help="Enable debug mode to show all LLM inputs and outputs")
    
    args = parser.parse_args()
    print_banner()
    agents = get_available_agents()
    
    if args.list:
        print_agents_menu(agents)
        return
    if args.agent:
        run_agent(args.agent, args.prompt, args.debug)
        return
    
    # Interactive menu
    if not agents:
        print(f"{Colors.RED}No agents found!{Colors.RESET}")
        return
        
    num_agents = print_agents_menu(agents)
    
    try:
        choice = input(f"\n{Colors.BRIGHT_BLUE}Select an agent (1-{num_agents}) or 'q' to quit: {Colors.RESET}")
        
        if choice.lower() == 'q':
            return
            
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < num_agents:
                agent_name = list(sorted(agents.keys()))[choice_idx]
                run_agent(agent_name, debug_llm=args.debug)
            else:
                print(f"{Colors.RED}Invalid selection. Enter 1-{num_agents}.{Colors.RESET}")
        except (ValueError, IndexError):
            print(f"{Colors.RED}Invalid selection. Enter 1-{num_agents}.{Colors.RESET}")
    except KeyboardInterrupt:
        print(f"\n{Colors.GREEN}Operation cancelled.{Colors.RESET}")

if __name__ == '__main__':
    main()
