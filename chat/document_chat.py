# chat/document_chat.py
from chat.context_manager import ContextManager
from chat.rephraser import Rephraser
from search.search_engine import SmartSearcher
from search.summarizer import DocumentSummarizer
from feedback.feedback_handler import FeedbackHandler

class DocumentChatEngine:
    def __init__(self, model, searcher: SmartSearcher):
        self.context = ContextManager()
        self.rephraser = Rephraser(model)
        self.searcher = searcher
        self.summarizer = DocumentSummarizer(model)
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

    def summarize_search_results(self, search_results, query, length=None):
        """Summarize search results using dedicated summarizer"""
        return self.summarizer.summarize_search_results(search_results, query, length)

    def summarize_context(self, context_lines, query, length=None):
        """Summarize document content using dedicated summarizer"""
        return self.summarizer.summarize_document_content(context_lines, query, length)

    def rephrase_line(self, line, tone="formal"):
        return self.rephraser.rephrase(line, tone)

    def get_available_summary_lengths(self):
        """Get available summary length options"""
        return self.summarizer.get_available_lengths()

    def set_summary_length(self, length):
        """Set default summary length"""
        return self.summarizer.set_summary_length(length)