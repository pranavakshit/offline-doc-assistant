import os
import re
import yaml
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

    def get_context_around_line(self, doc_lines, target_index, page_num):
        """Get context lines around a target line"""
        start_idx = max(0, target_index - self.context_lines_before)
        end_idx = min(len(doc_lines), target_index + self.context_lines_after + 1)

        context_lines = []
        for i in range(start_idx, end_idx):
            # Only include lines from the same page
            if doc_lines[i]['page'] == page_num:
                prefix = ">>> " if i == target_index else "    "
                context_lines.append(f"{prefix}{doc_lines[i]['text']}")

        context_text = '\n'.join(context_lines)

        # Truncate if too long
        if len(context_text) > self.max_context_chars:
            context_text = context_text[:self.max_context_chars] + "..."

        return context_text

    def get_paragraph_context(self, doc_lines, target_index):
        """Get the full paragraph containing the target line"""
        # Find paragraph boundaries (empty lines or significant text breaks)
        start_idx = target_index
        end_idx = target_index

        # Go backwards to find paragraph start
        while start_idx > 0:
            if not doc_lines[start_idx - 1]['text'].strip() or len(doc_lines[start_idx - 1]['text']) < 10:
                break
            start_idx -= 1

        # Go forwards to find paragraph end
        while end_idx < len(doc_lines) - 1:
            if not doc_lines[end_idx + 1]['text'].strip() or len(doc_lines[end_idx + 1]['text']) < 10:
                break
            end_idx += 1

        # Combine paragraph lines
        paragraph_lines = []
        for i in range(start_idx, end_idx + 1):
            if doc_lines[i]['text'].strip():
                prefix = ">>> " if i == target_index else "    "
                paragraph_lines.append(f"{prefix}{doc_lines[i]['text']}")

        paragraph_text = '\n'.join(paragraph_lines)

        # Truncate if too long
        if len(paragraph_text) > self.max_context_chars:
            paragraph_text = paragraph_text[:self.max_context_chars] + "..."

        return paragraph_text

    def save_user_feedback(self, query, matched_line, is_relevant):
        if self.config.get('feedback_enabled', True):
            self.feedback_handler.save_feedback(query, matched_line, is_relevant)

    def search(self, query, top_k=5, context_mode='lines'):
        """
        Search with enhanced context display
        context_mode options:
        - 'lines': Show surrounding lines (default)
        - 'paragraph': Show full paragraph
        - 'snippet': Show matched line only (original behavior)
        """
        query_expanded = self.expand_abbreviations(query)
        query_embedding = self.embedder.encode(query_expanded, convert_to_tensor=True)
        results = []

        for doc in self.doc_data:
            if not doc['lines'] or doc['embeddings'] is None:
                continue

            all_lines = [entry['text'] for entry in doc['lines']]
            scores = util.pytorch_cos_sim(query_embedding, doc['embeddings'])[0]
            ranked = sorted(zip(scores, enumerate(doc['lines'])), key=lambda x: x[0], reverse=True)
            top_semantic = [(float(s), idx, l) for s, (idx, l) in ranked[:top_k]]

            fuzzy_scores = []
            for idx, entry in enumerate(doc['lines']):
                fuzz_score = fuzz.partial_ratio(query_expanded.lower(), entry['text'].lower())
                if fuzz_score >= self.threshold:
                    fuzzy_scores.append((fuzz_score / 100.0, idx, entry))

            combined = {}
            for s, idx, entry in top_semantic + fuzzy_scores:
                key = (entry['text'], entry['page'], entry['line_num'])
                if key in combined:
                    if combined[key]['score'] < s:
                        combined[key] = {'score': s, 'index': idx, 'entry': entry}
                else:
                    combined[key] = {'score': s, 'index': idx, 'entry': entry}

            ranked_combined = sorted(combined.items(), key=lambda x: x[1]['score'], reverse=True)[:top_k]

            for (text, page, line_num), data in ranked_combined:
                entry = data['entry']
                idx = data['index']

                # Generate context based on mode
                if context_mode == 'paragraph':
                    context_text = self.get_paragraph_context(doc['lines'], idx)
                elif context_mode == 'lines':
                    context_text = self.get_context_around_line(doc['lines'], idx, page)
                else:  # snippet
                    context_text = text

                results.append({
                    'document': doc['name'],
                    'line': text,  # Original matched line
                    'context': context_text,  # Extended context
                    'page': page,
                    'line_num': line_num,
                    'score': data['score']
                })

        return sorted(results, key=lambda x: x['score'], reverse=True)[:top_k]