# search/search_engine.py
import os
import re
import yaml
import json
from collections import defaultdict

from sentence_transformers import SentenceTransformer, util
from fuzzywuzzy import fuzz
import easyocr
from PyPDF2 import PdfReader
from docx import Document
from pdf2image import convert_from_path

from feedback.feedback_handler import FeedbackHandler


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

        self.embedder = SentenceTransformer(self.config['embedding_model'])
        self.abbr_map = self.config['abbreviation_mapping']
        self.threshold = self.config['fuzzy_match_threshold']
        self.docs_folder = self.config['input_folder']

        self.feedback_handler = FeedbackHandler(self.config.get('feedback_storage', 'results/feedback.json'))
        self.load_documents()

    def load_documents(self):
        self.doc_data = []
        for fname in os.listdir(self.docs_folder):
            fpath = os.path.join(self.docs_folder, fname)
            if fname.endswith('.txt'):
                with open(fpath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            elif fname.endswith('.docx'):
                doc = Document(fpath)
                lines = [p.text for p in doc.paragraphs if p.text.strip()]
            elif fname.endswith('.pdf'):
                reader = PdfReader(fpath)
                lines = []
                for page in reader.pages:
                    text = page.extract_text()
                    if (not text or text.isspace()) and self.reader:
                        ocr_text = self.extract_text_with_ocr(fpath)
                        lines += ocr_text
                    else:
                        lines += text.split('\n') if text else []
            else:
                continue

            embeddings = self.embedder.encode(lines, convert_to_tensor=True) if lines else None

            self.doc_data.append({
                'name': fname,
                'lines': lines,
                'embeddings': embeddings
            })

    def extract_text_with_ocr(self, pdf_path):
        pages = convert_from_path(pdf_path)
        lines = []
        for p in pages:
            result = self.reader.readtext(p)
            text = ' '.join([x[1] for x in result])
            lines += text.split('\n')
        return lines

    def expand_abbreviations(self, text):
        for abbr, full in self.abbr_map.items():
            pattern = r'\b' + re.escape(abbr) + r'\b'
            text = re.sub(pattern, full, text, flags=re.IGNORECASE)
        return text

    def save_user_feedback(self, query, matched_line, is_relevant):
        if self.config.get('feedback_enabled', True):
            self.feedback_handler.save_feedback(query, matched_line, is_relevant)

    def search(self, query, top_k=5):
        query_expanded = self.expand_abbreviations(query)
        query_embedding = self.embedder.encode(query_expanded, convert_to_tensor=True)
        results = []

        for doc in self.doc_data:
            if not doc['lines'] or doc['embeddings'] is None:
                continue

            scores = util.pytorch_cos_sim(query_embedding, doc['embeddings'])[0]
            ranked = sorted(zip(scores, doc['lines']), key=lambda x: x[0], reverse=True)
            top_semantic = [(float(s), l) for s, l in ranked[:top_k]]

            fuzzy_scores = []
            for line in doc['lines']:
                fuzz_score = fuzz.partial_ratio(query_expanded.lower(), line.lower())
                if fuzz_score >= self.threshold:
                    fuzzy_scores.append((fuzz_score / 100.0, line))

            combined = {l: max(s1, s2) for s1, l in top_semantic for s2, l2 in fuzzy_scores if l == l2}
            for s, l in top_semantic + fuzzy_scores:
                if l not in combined:
                    combined[l] = s

            ranked_combined = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:top_k]

            for score, line in ranked_combined:
                results.append({
                    'document': doc['name'],
                    'line': line,
                    'score': score
                })

        # Optionally sort all results by score and take top_k
        return sorted(results, key=lambda x: x['score'], reverse=True)[:top_k]
