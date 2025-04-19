class Memory:
    """
    A structured memory class to store and retrieve key-value pairs and manage agent's memory.
    """

    def __init__(self, history_length: int = 25):
        """
        Initialize the memory with a specified history length.
        Args:
            history_length (int): The maximum number of entries to keep in history.
        """
        self.memory = {}
        self.history_length = history_length
        self.structured_history = []
        self.step_counter = 0

    def get_history(self):
        """Returns a formatted string representation of the structured history."""
        return "\n".join([f"{entry['step']}. {entry['type']}: {entry['content']}" 
                          for entry in self.structured_history])
            
    def add_structured_entry(self, entry_type: str, content: str):
        """
        Add a structured entry to the history.
        
        Args:
            entry_type: The type of entry (Plan, Thought, Action, Results, Observation, Final_Answer)
            content: The content of the entry
        """
        entry = {
            "step": self.step_counter,
            "type": entry_type,
            "content": content
        }
        self.structured_history.append(entry)
        self.step_counter += 1
        
        # Maintain history length
        if len(self.structured_history) > self.history_length:
            self.structured_history = self.structured_history[-self.history_length:]
            # Add indicator that some history was truncated
            self.structured_history[0]["content"] = "(earlier history truncated) " + self.structured_history[0]["content"]

    def add(self, key: str, value):
        """
        Add a key-value pair to the memory.
        """
        self.memory[key] = value

    def get(self, key):
        """
        Retrieve a value by its key from the memory.
        """
        return self.memory.get(key, None)

    def get_all(self)->str:
        """
        Retrieve all key-value pairs from the memory, and format as a string.
        """
        memory_str = ""
        # First add structured history
        memory_str += "History:\n"
        for entry in self.structured_history:
            memory_str += f"{entry['step']}. {entry['type']}: {entry['content']}\n"
        
        # Then add other memory items
        memory_str += "\nMemory Items:\n"
        for key, value in self.memory.items():
            memory_str += f"{key}: {value}\n"
        return memory_str.strip()
    
    def update(self, key, value):
        """
        Update the value of an existing key in the memory.
        """
        if key in self.memory:
            self.memory[key] = value
        else:
            raise KeyError(f"Key '{key}' not found in memory.")

    def remove(self, key):
        """
        Remove a key-value pair from the memory.
        """
        if key in self.memory:
            del self.memory[key]