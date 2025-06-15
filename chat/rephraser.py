# chat/rephraser.py
from utils.progress_utils import dynamic_progress


class Rephraser:
    def __init__(self, model):
        self.model = model

        # Define tone-specific settings
        self.tone_configs = {
            'formal': {'description': 'formal and professional', 'max_tokens': 300},
            'casual': {'description': 'casual and conversational', 'max_tokens': 250},
            'technical': {'description': 'technical and precise', 'max_tokens': 350},
            'simplified': {'description': 'simple and easy to understand', 'max_tokens': 300},
            'assertive': {'description': 'confident and assertive', 'max_tokens': 280},
            'persuasive': {'description': 'persuasive and compelling', 'max_tokens': 320},
            'empathetic': {'description': 'empathetic and understanding', 'max_tokens': 290},
            'poetic': {'description': 'poetic and eloquent', 'max_tokens': 350},
            'bullet': {'description': 'bullet points and structured', 'max_tokens': 280},
            'conversational': {'description': 'natural and conversational', 'max_tokens': 270}
        }

    def rephrase(self, text, tone='formal'):
        """
        Rephrase text with the given tone and progress tracking.
        """
        if not text or not text.strip():
            return "No text provided to rephrase."

        tone_config = self.tone_configs.get(tone.lower(), self.tone_configs['formal'])

        # Determine progress delay based on text length and complexity
        text_length = len(text)
        progress_delay = 1.5 if text_length > 500 else 1.0

        prompt = self._build_rephrase_prompt(text, tone, tone_config['description'])

        with dynamic_progress(
                desc=f"✏️ Rephrasing in {tone} tone",
                delay=progress_delay
        ):
            response = self.model(
                prompt,
                max_tokens=tone_config['max_tokens'],
                stop=["###", "</s>", "\n\nOriginal:"]
            )

        return response["choices"][0]["text"].strip()

    def batch_rephrase(self, texts, tones=None, default_tone='formal'):
        """Rephrase multiple texts with progress tracking"""
        if not texts:
            return []

        if tones is None:
            tones = [default_tone] * len(texts)
        elif len(tones) != len(texts):
            # Extend or truncate tones list to match texts
            tones = (tones * ((len(texts) // len(tones)) + 1))[:len(texts)]

        rephrased_texts = []

        # Use tqdm for batch processing
        from tqdm import tqdm

        progress_bar = tqdm(
            zip(texts, tones),
            desc="✏️ Batch rephrasing",
            unit="text",
            total=len(texts),
            ncols=80,
            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
        )

        for i, (text, tone) in enumerate(progress_bar):
            progress_bar.set_description(f"✏️ Rephrasing text {i + 1}/{len(texts)} ({tone})")

            rephrased = self.rephrase(text, tone)
            rephrased_texts.append(rephrased)

        progress_bar.close()
        return rephrased_texts

    def compare_tones(self, text, tones_to_compare=None):
        """Generate the same text in multiple tones for comparison"""
        if tones_to_compare is None:
            tones_to_compare = ['formal', 'casual', 'technical', 'simplified']

        comparisons = {}

        from tqdm import tqdm

        progress_bar = tqdm(
            tones_to_compare,
            desc="✏️ Comparing tones",
            unit="tone",
            ncols=80,
            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
        )

        for tone in progress_bar:
            progress_bar.set_description(f"✏️ Generating {tone} version")
            comparisons[tone] = self.rephrase(text, tone)

        progress_bar.close()
        return comparisons

    def _build_rephrase_prompt(self, text, tone, tone_description):
        """Build an optimized prompt for rephrasing"""
        return (
            f"You are an expert writer skilled in adapting text to different tones and styles.\n"
            f"Rephrase the following text to be {tone_description}.\n"
            f"Maintain the original meaning while adapting the style and tone.\n\n"
            f"### Original Text:\n{text}\n\n"
            f"### Rephrased ({tone.title()} Tone):"
        )

    def get_available_tones(self):
        """Return list of available tones"""
        return list(self.tone_configs.keys())

    def get_tone_description(self, tone):
        """Get description for a specific tone"""
        return self.tone_configs.get(tone.lower(), {}).get('description', 'standard tone')