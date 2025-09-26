from pathlib import Path

from core.agent import ToolCallingAgent
from core.enhancedMemory import EnhancedMemory
from core.utils.config import load_agent_config
from agents.web_researcher.tools import (
    search_web,
    fetch_webpage_content,
    search_arxiv,
    download_pdf,
    summarize_text,
    persist_research,
)

# Load configuration
config = load_agent_config(agent_name="web_researcher")
NAME = config["name"]
DESCRIPTION = config["description"]

# Support both snake_case and legacy space-separated config keys.
PERSISTENT_PROMPT = (
    config.get("persistent_prompt")
    or config.get("persistent prompt")
    or ""
)
MAX_STEPS = config.get("max_steps", config.get("max steps", 40))

logging_config = config.get("logging", {})
VERBOSE = logging_config.get("verbose", True)

# Initialize with enhanced memory for better knowledge management
MEMORY_PATH = Path("agents/web_researcher/memory_store.json")
memory = EnhancedMemory(
    history_length=30,
    timeline_length=120,
    max_kb_items=200,
    storage_path=MEMORY_PATH,
)

Agent = ToolCallingAgent(
    [search_web, fetch_webpage_content, search_arxiv, download_pdf, summarize_text, persist_research],
    persistent_prompt=PERSISTENT_PROMPT,
    memory_instance=memory,
    max_steps=MAX_STEPS,
    debug=VERBOSE
)

def main():
    print(f"\n{'=' * 50}")
    print(f"📚 {NAME}")
    print(f"{'=' * 50}")
    print(DESCRIPTION)
    print(f"{'=' * 50}\n")
    
    # Get research topic from user
    topic = input("What topic would you like me to research? ")
    print("\nStarting comprehensive research. This may take some time...\n")
    
    # Run the agent
    results = Agent.run(topic)
    print("\n\n=== RESEARCH RESULTS ===\n")
    print(results)

if __name__ == "__main__":
    main()
