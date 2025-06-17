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
from tqdm import tqdm

# Add debug imports
import traceback
import sys


class SmartSearcher:
    def __init__(self, config_path='config.yaml'):
        print("🔧 Loading configuration...")
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            print("✅ Configuration loaded successfully")
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            raise

        # Initialize OCR with debug info
        if self.config.get('ocr_enabled', False):
            langs = self.config.get('ocr_languages', ['en'])
            if not isinstance(langs, (list, tuple)):
                langs = [langs]
            print(f"🔧 Initializing OCR engine for languages: {langs}")
            try:
                self.reader = easyocr.Reader(langs)
                print("✅ OCR engine initialized successfully")
            except Exception as e:
                print(f"❌ Error initializing OCR: {e}")
                print("📝 OCR will be disabled")
                self.reader = None
        else:
            print("ℹ️ OCR is disabled in config")
            self.reader = None

        # Initialize embedding model with debug info
        embedding_model = self.config.get('embedding_model', 'all-mpnet-base-v2')
        print(f"🧠 Loading embedding model: {embedding_model}")
        try:
            self.embedder = SentenceTransformer(embedding_model)
            print("✅ Embedding model loaded successfully")
        except Exception as e:
            print(f"❌ Error loading embedding model: {e}")
            traceback.print_exc()
            raise

        # Initialize other attributes
        self.abbr_map = self.config.get('abbreviation_mapping', {})
        self.threshold = self.config.get('fuzzy_match_threshold', 80)
        self.docs_folder = self.config.get('input_folder', 'documents')

        print(f"📁 Documents folder: {self.docs_folder}")
        print(f"🎯 Fuzzy match threshold: {self.threshold}")

        # Context settings
        self.context_lines_before = self.config.get('context_lines_before', 2)
        self.context_lines_after = self.config.get('context_lines_after', 2)
        self.max_context_chars = self.config.get('max_context_chars', 500)

        # Initialize feedback handler (with error handling)
        try:
            from feedback.feedback_handler import FeedbackHandler
            self.feedback_handler = FeedbackHandler(self.config.get('feedback_storage', 'results/feedback.json'))
            print("✅ Feedback handler initialized")
        except ImportError as e:
            print(f"⚠️ Warning: Could not import FeedbackHandler: {e}")
            self.feedback_handler = None

        # Load documents with debug info
        print("📚 Starting document loading process...")
        self.load_documents()

    def load_documents(self):
        """Load documents with enhanced debugging"""
        print("📚 Scanning document folder...")

        # Check if docs folder exists
        if not os.path.exists(self.docs_folder):
            print(f"❌ Documents folder '{self.docs_folder}' does not exist!")
            print("📝 Creating empty document list")
            self.doc_data = []
            return

        # Get list of files in directory
        try:
            all_files = os.listdir(self.docs_folder)
            print(f"📄 Found {len(all_files)} total files: {all_files}")
        except Exception as e:
            print(f"❌ Error reading documents folder: {e}")
            self.doc_data = []
            return

        # Filter supported files
        supported_extensions = ('.txt', '.docx', '.pdf')
        supported_files = []
        for fname in all_files:
            if fname.lower().endswith(supported_extensions):
                supported_files.append(fname)
                print(f"  ✅ {fname} - supported")
            else:
                print(f"  ⏭️ {fname} - skipped (unsupported extension)")

        if not supported_files:
            print("⚠️ No supported documents found in the docs folder")
            print(f"   Supported formats: {supported_extensions}")
            self.doc_data = []
            return

        print(f"📄 Processing {len(supported_files)} supported documents")

        self.doc_data = []
        total_lines_processed = 0

        for i, fname in enumerate(supported_files, 1):
            print(f"\n📖 Processing file {i}/{len(supported_files)}: {fname}")
            fpath = os.path.join(self.docs_folder, fname)

            try:
                # Check file size
                file_size = os.path.getsize(fpath)
                print(f"   📏 File size: {file_size} bytes")

                if file_size == 0:
                    print(f"   ⚠️ Warning: {fname} is empty, skipping")
                    continue

                line_info = []

                if fname.lower().endswith('.txt'):
                    print("   📝 Processing as text file")
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        print(f"   ✅ Read {len(lines)} lines")
                        for idx, line in enumerate(lines):
                            if line.strip():  # Only add non-empty lines
                                line_info.append({'text': line.strip(), 'page': 1, 'line_num': idx + 1})
                    except UnicodeDecodeError:
                        print("   ⚠️ UTF-8 failed, trying latin-1 encoding")
                        with open(fpath, 'r', encoding='latin-1') as f:
                            lines = f.readlines()
                        for idx, line in enumerate(lines):
                            if line.strip():
                                line_info.append({'text': line.strip(), 'page': 1, 'line_num': idx + 1})

                elif fname.lower().endswith('.docx'):
                    print("   📄 Processing as Word document")
                    doc = Document(fpath)
                    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                    print(f"   ✅ Found {len(paragraphs)} paragraphs")
                    for idx, paragraph in enumerate(paragraphs):
                        line_info.append({'text': paragraph.strip(), 'page': 1, 'line_num': idx + 1})

                elif fname.lower().endswith('.pdf'):
                    print("   📋 Processing as PDF document")
                    try:
                        reader = PdfReader(fpath)
                        print(f"   📖 PDF has {len(reader.pages)} pages")

                        for pageno, page in enumerate(reader.pages, start=1):
                            print(f"   📄 Processing page {pageno}")
                            text = page.extract_text()

                            if not text or text.isspace():
                                if self.reader:
                                    print(f"   👁️ No text found, using OCR for page {pageno}")
                                    ocr_lines = self.extract_text_with_ocr(fpath, pageno)
                                    for lineno, line in enumerate(ocr_lines, start=1):
                                        if line.strip():
                                            line_info.append({'text': line.strip(), 'page': pageno, 'line_num': lineno})
                                else:
                                    print(f"   ⚠️ No text found on page {pageno} and OCR is disabled")
                            else:
                                lines = text.split('\n')
                                valid_lines = [line.strip() for line in lines if line.strip()]
                                print(f"   ✅ Extracted {len(valid_lines)} lines from page {pageno}")
                                for lineno, line in enumerate(valid_lines, start=1):
                                    line_info.append({'text': line, 'page': pageno, 'line_num': lineno})
                    except Exception as pdf_error:
                        print(f"   ❌ Error processing PDF: {pdf_error}")
                        continue

                # Generate embeddings for this document
                all_lines = [entry['text'] for entry in line_info if entry['text'].strip()]
                print(f"   🧠 Generating embeddings for {len(all_lines)} lines")

                if all_lines:
                    try:
                        embeddings = self.embedder.encode(all_lines, convert_to_tensor=True)
                        print(f"   ✅ Generated embeddings with shape: {embeddings.shape}")
                        total_lines_processed += len(all_lines)
                    except Exception as embed_error:
                        print(f"   ❌ Error generating embeddings: {embed_error}")
                        embeddings = None
                else:
                    print("   ⚠️ No valid lines found, skipping embeddings")
                    embeddings = None

                self.doc_data.append({
                    'name': fname,
                    'lines': line_info,
                    'embeddings': embeddings
                })

                print(f"   ✅ Successfully processed {fname}")

            except Exception as e:
                print(f"   ❌ Error processing {fname}: {e}")
                print(f"   🔍 Error details: {traceback.format_exc()}")
                continue

        print(f"\n✅ Document loading complete!")
        print(f"📊 Summary:")
        print(f"   - Processed: {len(self.doc_data)} documents")
        print(f"   - Total lines: {total_lines_processed}")

        # Print document details
        for doc in self.doc_data:
            line_count = len([l for l in doc['lines'] if l['text'].strip()])
            embedding_status = "✅" if doc['embeddings'] is not None else "❌"
            print(f"   - {doc['name']}: {line_count} lines {embedding_status}")

    def extract_text_with_ocr(self, pdf_path, page_number):
        """Extract text using OCR with debugging"""
        try:
            print(f"     🖼️ Converting PDF page {page_number} to image")
            pages = convert_from_path(pdf_path)
            if page_number > len(pages):
                print(f"     ❌ Page {page_number} not found in PDF")
                return []

            print(f"     👁️ Running OCR on page {page_number}")
            result = self.reader.readtext(pages[page_number - 1])
            text = ' '.join([x[1] for x in result])
            lines = text.split('\n')
            print(f"     ✅ OCR extracted {len(lines)} lines")
            return lines
        except Exception as e:
            print(f"     ❌ OCR error: {e}")
            return []

    # ... (rest of the methods remain the same)
    def expand_abbreviations(self, text):
        for abbr, full in self.abbr_map.items():
            pattern = r'\b' + re.escape(abbr) + r'\b'
            text = re.sub(pattern, full, text, flags=re.IGNORECASE)
        return text

    def save_user_feedback(self, query, matched_line, is_relevant):
        if self.feedback_handler and self.config.get('feedback_enabled', True):
            self.feedback_handler.save_feedback(query, matched_line, is_relevant)

    def search(self, query, top_k=5, context_mode='lines'):
        """Basic search implementation for testing"""
        print(f"🔍 Searching for: '{query}'")
        print(f"📊 Available documents: {len(self.doc_data)}")

        if not self.doc_data:
            print("❌ No documents available for search")
            return []

        # Simple implementation for testing
        results = []
        for doc in self.doc_data:
            if not doc['lines']:
                continue

            # Simple text matching for debugging
            for i, line_info in enumerate(doc['lines']):
                if query.lower() in line_info['text'].lower():
                    results.append({
                        'document': doc['name'],
                        'line': line_info['text'],
                        'context': line_info['text'],  # Simple context for now
                        'page': line_info['page'],
                        'line_num': line_info['line_num'],
                        'score': 1.0
                    })

        print(f"✅ Found {len(results)} matches")
        return results[:top_k]