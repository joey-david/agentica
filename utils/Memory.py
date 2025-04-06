class Memory:
    """
    A simple memory class to store and retrieve key-value pairs to more easily manage agents memory.
    """

    def __init__(self, history_length: int = 25):
        """
        Initialize the memory with a specified history length.
        Args:
            history_length (int): The maximum number of messages to keep in history.
        """
        self.memory = {}
        self.history_length = history_length
        self.history = []
        self.message_count = 0

    def get_history(self):
        return "\n".join(self.history)
            
    def add_to_history(self, message: str):
        """
        Add a message to the history.
        """
        self.history.append("(" + str(self.message_count) + ".) " + message)
        self.message_count += 1
        # Replace the oldest message with an ellipsis that we forgot some of the earlier actions
        if len(self.history) > self.history_length:
            self.history.pop(0)
            self.history[0] = "..."

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
        Retrieve all key-value pairs from the memory, and append them to a string.
        """
        memory_str = ""
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