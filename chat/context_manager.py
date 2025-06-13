class ContextManager:
    def __init__(self):
        self.chat_history = []

    def add_turn(self, user_input, response):
        self.chat_history.append({
            "user": user_input,
            "assistant": response
        })

    def get_history(self):
        return self.chat_history

    def clear_history(self):
        self.chat_history = []
