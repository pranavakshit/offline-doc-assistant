import os
import re
import yaml
from collections import defaultdict
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from feedback.feedback_handler import FeedbackHandler
from sentence_transformers import SentenceTransformer, util
from fuzzywuzzy import fuzz
import easyocr
from PyPDF2 import PdfReader
from docx import Document
from pdf2image import convert_from_path
from utils.file_loader import FileLoader  # chunk_text no longer needed


class SmartSearcher:
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        if self.config.get('ocr_enabled', False):
            langs = self.config.get('ocr_languages', ['en'])
            if not isinstance(langs, (list, tuple)):
                langs = [langs]
            self.reader = easyocr.Reader(langs)
        else:
            self.reader = None

        self.embedder = SentenceTransformer(self.config['embedding_model'], local_files_only=True)

        # Ensure abbreviation map exists
        self.abbr_map = self.config.get('abbreviation_mapping', {})

        self.threshold = self.config.get('fuzzy_match_threshold', 80)
        self.docs_folder = self.config.get('input_folder', 'documents')

        # Context settings
        self.context_lines_before = self.config.get('context_lines_before', 2)
        self.context_lines_after = self.config.get('context_lines_after', 2)
        self.max_context_chars = self.config.get('max_context_chars', 500)

        self.feedback_handler = FeedbackHandler(self.config.get('feedback_storage', 'results/feedback.json'))
        self.load_documents()

    def load_documents(self):
        # Use FileLoader to load and chunk documents with metadata
        file_loader = FileLoader(self.docs_folder)
        doc_chunks = file_loader.load_documents()  # List of (filename, chunk_text, page, line_num) tuples

        self.doc_data = []
        if not doc_chunks:
            return

        # Group chunks by document
        doc_map = defaultdict(list)
        for fname, chunk_text, page, line_num in doc_chunks:
            doc_map[fname].append({"text": chunk_text, "page": page, "line_num": line_num})

        for fname, chunks in doc_map.items():
            embeddings = self.embedder.encode([c["text"] for c in chunks], convert_to_tensor=True) if chunks else None
            chunk_info = []
            for idx, chunk in enumerate(chunks):
                chunk_info.append({
                    'chunk': chunk["text"],
                    'chunk_num': idx + 1,
                    'page': chunk["page"],
                    'line_num': chunk["line_num"]
                })
            self.doc_data.append({
                'name': fname,
                'chunks': chunk_info,
                'embeddings': embeddings
            })

    def expand_abbreviations(self, text):
        for abbr, full in self.abbr_map.items():
            pattern = r'\b' + re.escape(abbr) + r'\b'
            text = re.sub(pattern, full, text, flags=re.IGNORECASE)
        return text

    def extract_best_lines(self, chunk_text, query, top_n=1):
        """
        Return the most relevant line(s) from the chunk for display.
        """
        lines = [l.strip() for l in chunk_text.split('\n') if l.strip()]
        if not lines:
            lines = [l.strip() for l in chunk_text.split('. ') if l.strip()]
        if not lines:
            return chunk_text  # fallback: return the whole chunk

        # Use fuzzy matching to find the best matching line(s)
        scored = [(fuzz.partial_ratio(query.lower(), line.lower()), line) for line in lines]
        scored.sort(reverse=True)
        return "\n".join([line for _, line in scored[:top_n]])

    def search(self, query, top_k=5, context_mode='chunk'):
        """
        Search over document chunks for efficiency.
        context_mode: 'chunk' (returns the chunk), or future modes.
        """
        query_expanded = self.expand_abbreviations(query)
        query_embedding = self.embedder.encode(query_expanded, convert_to_tensor=True)
        results = []
        query_keywords = set(query_expanded.lower().split())

        for doc in self.doc_data:
            if not doc['chunks'] or doc['embeddings'] is None:
                continue

            all_chunks = [entry['chunk'] for entry in doc['chunks']]
            scores = util.pytorch_cos_sim(query_embedding, doc['embeddings'])[0]
            ranked = sorted(zip(scores, enumerate(doc['chunks'])), key=lambda x: x[0], reverse=True)
            top_semantic = [(float(s), idx, l) for s, (idx, l) in ranked[:top_k]]

            fuzzy_scores = []
            for idx, entry in enumerate(doc['chunks']):
                fuzz_score = fuzz.partial_ratio(query_expanded.lower(), entry['chunk'].lower())
                if fuzz_score >= self.threshold:
                    fuzzy_scores.append((fuzz_score / 100.0, idx, entry))

            combined = {}
            for s, idx, entry in top_semantic + fuzzy_scores:
                key = (entry['chunk'], entry['chunk_num'])

                # --- Keyword match boost ---
                chunk_text_lower = entry['chunk'].lower()
                keyword_boost = 0.0
                for word in query_keywords:
                    if word in chunk_text_lower:
                        keyword_boost += 0.2  # You can tune this value

                boosted_score = s + keyword_boost
                # --- End keyword match boost ---

                if key in combined:
                    if combined[key]['score'] < boosted_score:
                        combined[key] = {'score': boosted_score, 'index': idx, 'entry': entry}
                else:
                    combined[key] = {'score': boosted_score, 'index': idx, 'entry': entry}

            ranked_combined = sorted(combined.items(), key=lambda x: x[1]['score'], reverse=True)[:top_k]

            for (chunk_text, chunk_num), data in ranked_combined:
                entry = data['entry']
                idx = data['index']

                # Extract only the best matching line(s) from the chunk for context
                best_lines = self.extract_best_lines(chunk_text, query, top_n=2)

                results.append({
                    'document': doc['name'],
                    'line': best_lines[:80] + ("..." if len(best_lines) > 80 else ""),  # Preview
                    'context': best_lines,
                    'chunk_num': chunk_num,
                    'score': data['score'],
                    'page': entry.get('page', 'N/A'),
                    'line_num': entry.get('line_num', 'N/A')
                })

        from search.ranker import rank_results
        return rank_results(results)[:top_k]

    def save_user_feedback(self, query, matched_line, is_relevant):
        """
        Save user feedback for a given query and matched line.
        """
        if self.config.get('feedback_enabled', True):
            self.feedback_handler.save_feedback(query, matched_line, is_relevant)