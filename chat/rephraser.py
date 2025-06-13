# rephraser.py
class Rephraser:
    def __init__(self, model):
        self.model = model

    def rephrase(self, text, tone='formal'):
        prompt = (
            f"Rephrase the following text in a {tone} tone:\n\n"
            f"{text}\n\nRephrased:"
        )
        response = self.model(prompt, max_tokens=300, stop=["###", "</s>"])
        return response["choices"][0]["text"].strip()
