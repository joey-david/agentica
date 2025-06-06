from collections import deque

class Memory:
    """
    A structured memory class that handles data storage and retrieval for the agent.
    """
    def __init__(self, history_length=10):
        self.summaries = deque(maxlen=history_length)
        self.state: str = ""
        self.action_results: dict = {}
    
    # Summary of the last history_length steps (one sentence per step)
    
    def add_summary(self, sentence: str) -> None:
        self.summaries.append(sentence.strip())

    def get_summaries(self) -> str:
        lines = []
        for idx, summary in enumerate(reversed(self.summaries), 1):
            prefix = "Previous step" if idx == 1 else f"Step-{idx}"
            lines.append(f"{prefix}: {summary}")
        return "\n".join(lines)
    
    # State of the agent (e.g., current task, context, instructions for the next step)

    def set_state(self, text: str) -> None:
        self.state = text.strip()
    
    def get_state(self) -> str:
        return self.state
    
    # Action results - results of the last set of tool calls

    def set_action_results(self, results: dict) -> None:
        if not isinstance(results, dict):
            raise ValueError("Action results must be a dictionary.")
        self.action_results = results
    
    def get_action_results(self) -> str:
        if not self.action_results:
            return "No action results available."
        lines = [f"{key}: {value}" for key, value in self.action_results.items()]
        return "\n".join(lines)
        

if __name__ == "__main__":
    # Example usage
    memory = Memory(history_length=5)
    memory.add_summary("First summary")
    memory.add_summary("Second summary")
    memory.add_summary("Third summary")
    memory.set_state("Current state of the agent")

    print("Summaries:")
    print(memory.get_summaries())
    
    print("\nCurrent State:")
    print(memory.get_state())

    memory.set_action_results({"tool1": "result1", "tool2": "result2"})
    print("\nAction Results:")
    print(memory.get_action_results())