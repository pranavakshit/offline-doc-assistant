# rephraser.py
class Rephraser:
    def __init__(self, model):
        self.model = model

    def rephrase(self, text, tone='formal'):
        """
        Rephrase text with the given tone.
        Progress tracking is handled by the calling function using context managers.
        """
        prompt = (
            f"Rephrase the following text in a {tone} tone:\n\n"
            f"{text}\n\nRephrased:"
        )

        # The actual model call - progress bar will show during this operation
        response = self.model(prompt, max_tokens=300, stop=["###", "</s>"])
        return response["choices"][0]["text"].strip()