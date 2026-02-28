class Memory:
    def __init__(self, system_prompt="You are a helpful assistant."):
        self.history = [{"role": "system", "content": system_prompt}]

    def add_message(self, role, content):
        self.history.append({"role": role, "content": content})

    def get_history(self):
        return self.history

    def clear(self):
        self.history = [self.history[0]]
