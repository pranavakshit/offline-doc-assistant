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
            line_info = []

            if fname.endswith('.txt'):
                with open(fpath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                for idx, line in enumerate(lines):
                    line_info.append({'text': line.strip(), 'page': 1, 'line_num': idx + 1})

            elif fname.endswith('.docx'):
                doc = Document(fpath)
                lines = [p.text for p in doc.paragraphs if p.text.strip()]
                for idx, line in enumerate(lines):
                    line_info.append({'text': line.strip(), 'page': 1, 'line_num': idx + 1})

            elif fname.endswith('.pdf'):
                reader = PdfReader(fpath)
                for pageno, page in enumerate(reader.pages, start=1):
                    text = page.extract_text()
                    if (not text or text.isspace()) and self.reader:
                        ocr_lines = self.extract_text_with_ocr(fpath, pageno)
                        for lineno, line in enumerate(ocr_lines, start=1):
                            line_info.append({'text': line.strip(), 'page': pageno, 'line_num': lineno})
                    else:
                        lines = text.split('\n') if text else []
                        for lineno, line in enumerate(lines, start=1):
                            line_info.append({'text': line.strip(), 'page': pageno, 'line_num': lineno})
            else:
                continue

            all_lines = [entry['text'] for entry in line_info]
            embeddings = self.embedder.encode(all_lines, convert_to_tensor=True) if all_lines else None

            self.doc_data.append({
                'name': fname,
                'lines': line_info,
                'embeddings': embeddings
            })

    def extract_text_with_ocr(self, pdf_path, page_number):
        pages = convert_from_path(pdf_path)
        result = self.reader.readtext(pages[page_number - 1])
        text = ' '.join([x[1] for x in result])
        return text.split('\n')

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

            all_lines = [entry['text'] for entry in doc['lines']]
            scores = util.pytorch_cos_sim(query_embedding, doc['embeddings'])[0]
            ranked = sorted(zip(scores, doc['lines']), key=lambda x: x[0], reverse=True)
            top_semantic = [(float(s), l) for s, l in ranked[:top_k]]

            fuzzy_scores = []
            for entry in doc['lines']:
                fuzz_score = fuzz.partial_ratio(query_expanded.lower(), entry['text'].lower())
                if fuzz_score >= self.threshold:
                    fuzzy_scores.append((fuzz_score / 100.0, entry))

            combined = {}
            for s, entry in top_semantic + fuzzy_scores:
                key = (entry['text'], entry['page'], entry['line_num'])
                if key in combined:
                    combined[key] = max(combined[key], s)
                else:
                    combined[key] = s

            ranked_combined = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:top_k]

            for (text, page, line_num), score in ranked_combined:
                results.append({
                    'document': doc['name'],
                    'line': text,
                    'page': page,
                    'line_num': line_num,
                    'score': score
                })

        return sorted(results, key=lambda x: x['score'], reverse=True)[:top_k]
