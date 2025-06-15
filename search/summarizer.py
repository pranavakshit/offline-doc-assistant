# search/summarizer.py
import yaml
from utils.progress_utils import dynamic_progress


class DocumentSummarizer:
    def __init__(self, model, config_path='config.yaml'):
        self.model = model
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.summary_length = self.config.get('summary_length', 'medium')

        # Define length parameters
        self.length_configs = {
            'short': {'max_tokens': 150, 'description': 'brief'},
            'medium': {'max_tokens': 300, 'description': 'concise'},
            'long': {'max_tokens': 500, 'description': 'detailed'}
        }

    def summarize_search_results(self, search_results, query, length=None):
        """Summarize search results based on query with progress tracking"""
        if not search_results:
            return "No search results to summarize."

        # Use provided length or fall back to config
        length = length or self.summary_length
        config = self.length_configs.get(length, self.length_configs['medium'])

        # Extract text from search results
        context_lines = [result['line'] for result in search_results]

        # Create document context with metadata
        context_with_metadata = []
        for result in search_results:
            doc_info = f"[{result['document']} - Page {result['page']}]"
            context_with_metadata.append(f"{doc_info}: {result['line']}")

        prompt = self._build_summary_prompt(context_with_metadata, query, config['description'])

        # Use progress bar for longer summaries or when processing many results
        progress_delay = 1.0 if len(search_results) > 3 or config['max_tokens'] > 300 else 0.5

        with dynamic_progress(
                desc=f"📋 Generating {config['description']} summary",
                delay=progress_delay
        ):
            response = self.model(
                prompt,
                max_tokens=config['max_tokens'],
                stop=["###", "</s>", "\n\n---"]
            )

        return response["choices"][0]["text"].strip()

    def summarize_document_content(self, context_lines, query=None, length=None):
        """Summarize general document content with progress tracking"""
        if not context_lines:
            return "No content to summarize."

        length = length or self.summary_length
        config = self.length_configs.get(length, self.length_configs['medium'])

        if query:
            prompt = self._build_query_based_summary_prompt(context_lines, query, config['description'])
        else:
            prompt = self._build_general_summary_prompt(context_lines, config['description'])

        # Determine progress delay based on content length and summary complexity
        content_length = sum(len(line) for line in context_lines)
        progress_delay = 1.5 if content_length > 2000 or config['max_tokens'] > 400 else 1.0

        desc = f"📋 Summarizing document content ({config['description']})"
        if query:
            desc = f"📋 Creating query-based summary ({config['description']})"

        with dynamic_progress(desc=desc, delay=progress_delay):
            response = self.model(
                prompt,
                max_tokens=config['max_tokens'],
                stop=["###", "</s>", "\n\n---"]
            )

        return response["choices"][0]["text"].strip()

    def batch_summarize(self, multiple_contexts, queries=None, length=None):
        """Summarize multiple document contexts with progress tracking"""
        if not multiple_contexts:
            return []

        length = length or self.summary_length
        config = self.length_configs.get(length, self.length_configs['medium'])

        summaries = []

        # Use tqdm for batch processing
        from tqdm import tqdm

        progress_bar = tqdm(
            multiple_contexts,
            desc=f"📋 Batch summarizing ({config['description']})",
            unit="doc",
            ncols=80,
            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
        )

        for i, context in enumerate(progress_bar):
            query = queries[i] if queries and i < len(queries) else None

            # Update progress description for current document
            progress_bar.set_description(f"📋 Summarizing document {i + 1}/{len(multiple_contexts)}")

            if query:
                summary = self.summarize_document_content(context, query, length)
            else:
                summary = self.summarize_document_content(context, length=length)

            summaries.append(summary)

        progress_bar.close()
        return summaries

    def _build_summary_prompt(self, context_with_metadata, query, length_desc):
        """Build prompt for search results summary"""
        return (
            f"You are an AI assistant providing a {length_desc} summary of document search results.\n"
            f"Focus on information relevant to the user's query.\n\n"
            f"### User Query:\n{query}\n\n"
            f"### Search Results:\n{chr(10).join(context_with_metadata)}\n\n"
            f"### {length_desc.title()} Summary:\n"
            f"Based on the search results above, provide a {length_desc} summary that directly addresses the user's query:"
        )

    def _build_query_based_summary_prompt(self, context_lines, query, length_desc):
        """Build prompt for query-based document summary"""
        return (
            f"You are an AI assistant summarizing document excerpts based on a user query.\n"
            f"Provide a {length_desc} summary focusing on information relevant to the query.\n\n"
            f"### User Query:\n{query}\n\n"
            f"### Document Content:\n{chr(10).join(context_lines)}\n\n"
            f"### {length_desc.title()} Summary:"
        )

    def _build_general_summary_prompt(self, context_lines, length_desc):
        """Build prompt for general document summary"""
        return (
            f"You are an AI assistant providing a {length_desc} summary of document content.\n"
            f"Identify the main topics, key points, and important information.\n\n"
            f"### Document Content:\n{chr(10).join(context_lines)}\n\n"
            f"### {length_desc.title()} Summary:"
        )

    def get_available_lengths(self):
        """Return available summary lengths"""
        return list(self.length_configs.keys())

    def set_summary_length(self, length):
        """Set default summary length"""
        if length in self.length_configs:
            self.summary_length = length
            return True
        return False