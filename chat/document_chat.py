# chat/document_chat.py
from chat.context_manager import ContextManager
from chat.rephraser import Rephraser
from search.search_engine import SmartSearcher
from feedback.feedback_handler import FeedbackHandler

class DocumentChatEngine:
    def __init__(self, model, searcher: SmartSearcher):
        self.context = ContextManager()
        self.rephraser = Rephraser(model)
        self.searcher = searcher
        self.feedback_handler = FeedbackHandler()
        self.model = model

    def chat(self, user_input, tone="formal"):
        raw_results = self.searcher.search(user_input)
        rephrased = self.rephraser.rephrase("\n".join([r['line'] for r in raw_results]), tone=tone)
        self.context.add_turn(user_input, rephrased)
        return rephrased

    def get_history(self):
        return self.context.get_history()

    def add_feedback(self, feedback_text):
        self.feedback_handler.handle_feedback(feedback_text)

    def summarize_context(self, context_lines, query):
        prompt = (
            "You are an assistant summarizing document excerpts based on a user query.\n"
            f"### Context:\n{chr(10).join(context_lines)}\n\n"
            f"### Query:\n{query}\n\n"
            "### Summary:"
        )
        response = self.model(prompt, max_tokens=300, stop=["###", "</s>"])
        return response["choices"][0]["text"].strip()

    def rephrase_line(self, line, tone="formal"):
        return self.rephraser.rephrase(line, tone)
