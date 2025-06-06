from collections import defaultdict
import json
import os

class FeedbackHandler:
    def __init__(self, save_path="feedback/feedback.json"):
        self.save_path = save_path
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        self.feedback_data = self._load_feedback()

    def _load_feedback(self):
        if os.path.exists(self.save_path):
            with open(self.save_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return defaultdict(lambda: defaultdict(int))

    def save_feedback(self, query, matched_line, is_relevant):
        query = query.strip().lower()
        line_key = matched_line.strip().lower()

        if query not in self.feedback_data:
            self.feedback_data[query] = {}

        if line_key not in self.feedback_data[query]:
            self.feedback_data[query][line_key] = 0

        self.feedback_data[query][line_key] += 1 if is_relevant else -1

        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(self.feedback_data, f, indent=2)

    def get_feedback_scores(self, query):
        query = query.strip().lower()
        return self.feedback_data.get(query, {})
