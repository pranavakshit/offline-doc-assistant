import os
import re
import yaml
from collections import defaultdict
import traceback

from sentence_transformers import SentenceTransformer, util
from fuzzywuzzy import fuzz
import easyocr
from PyPDF2 import PdfReader
from docx import Document
from pdf2image import convert_from_path
from tqdm import tqdm

# Try to import feedback handler, but continue without it if not available
try:
    from feedback.feedback_handler import FeedbackHandler

    FEEDBACK_AVAILABLE = True
except ImportError:
    print("⚠️ Warning: FeedbackHandler not available - feedback features disabled")
    FEEDBACK_AVAILABLE = False

# Try to import progress utils, but use tqdm fallback if not available
try:
    from utils.progress_utils import ProgressBarManager, ocr_progress

    PROGRESS_UTILS_AVAILABLE = True
except ImportError:
    print("⚠️ Warning: Custom progress utils not available - using tqdm")
    PROGRESS_UTILS_AVAILABLE = False

    # Fallback context manager
    from contextlib import contextmanager


    @contextmanager
    def ocr_progress():
        print("👁️ Running OCR...")
        yield
        print("✅ OCR complete")


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

        # Initialize OCR if enabled
        if self.config.get('ocr_enabled', False):
            langs = self.config.get('ocr_languages', ['en'])
            if not isinstance(langs, (list, tuple)):
                langs = [langs]
            print(f"🔧 Initializing OCR engine for languages: {langs}")
            try:
                self.reader = easyocr.Reader(langs)
                print("✅ OCR engine initialized")
            except Exception as e:
                print(f"⚠️ Warning: OCR initialization failed: {e}")
                print("💡 OCR features will be disabled")
                self.reader = None
        else:
            self.reader = None

        print("🧠 Loading embedding model...")
        embedding_model = self.config.get('embedding_model', 'all-mpnet-base-v2')
        try:
            self.embedder = SentenceTransformer(embedding_model)
            print("✅ Embedding model loaded successfully")
        except Exception as e:
            print(f"❌ Error loading embedding model: {e}")
            raise

        # Initialize other attributes
        self.abbr_map = self.config.get('abbreviation_mapping', {})
        self.threshold = self.config.get('fuzzy_match_threshold', 80)
        self.docs_folder = self.config.get('input_folder', 'documents')

        # Context settings
        self.context_lines_before = self.config.get('context_lines_before', 2)
        self.context_lines_after = self.config.get('context_lines_after', 2)
        self.max_context_chars = self.config.get('max_context_chars', 500)

        # Initialize feedback handler if available
        if FEEDBACK_AVAILABLE and self.config.get('feedback_enabled', True):
            try:
                feedback_path = self.config.get('feedback_storage', 'results/feedback.json')
                # Ensure results directory exists
                os.makedirs(os.path.dirname(feedback_path), exist_ok=True)
                self.feedback_handler = FeedbackHandler(feedback_path)
                print("✅ Feedback system initialized")
            except Exception as e:
                print(f"⚠️ Warning: Feedback handler initialization failed: {e}")
                self.feedback_handler = None
        else:
            self.feedback_handler = None

        # Load documents
        self.load_documents()

    def load_documents(self):
        """Load documents with enhanced error handling and progress tracking"""
        print("📚 Scanning document folder...")

        # Check if docs folder exists
        if not os.path.exists(self.docs_folder):
            print(f"❌ Documents folder '{self.docs_folder}' does not exist!")
            print("📝 Creating empty document list")
            self.doc_data = []
            return

        # Get list of supported files
        try:
            all_files = os.listdir(self.docs_folder)
        except Exception as e:
            print(f"❌ Error reading documents folder: {e}")
            self.doc_data = []
            return

        supported_files = []
        for fname in all_files:
            if fname.lower().endswith(('.txt', '.docx', '.pdf')):
                supported_files.append(fname)

        if not supported_files:
            print("⚠️ No supported documents found in the docs folder")
            print("   Supported formats: .txt, .docx, .pdf")
            self.doc_data = []
            return

        print(f"📄 Found {len(supported_files)} documents to process")

        # Initialize document loading progress bar
        if PROGRESS_UTILS_AVAILABLE:
            doc_progress = ProgressBarManager.document_loading_progress(total_docs=len(supported_files))
        else:
            doc_progress = tqdm(
                supported_files,
                desc="📚 Loading documents",
                unit="doc",
                ncols=80
            )

        self.doc_data = []
        total_lines_processed = 0

        for fname in supported_files:
            fpath = os.path.join(self.docs_folder, fname)

            if PROGRESS_UTILS_AVAILABLE:
                doc_progress.set_description(f"📚 Loading {fname}")
            else:
                doc_progress.set_description(f"📚 Loading {fname}")

            line_info = []

            try:
                # Check file size
                file_size = os.path.getsize(fpath)
                if file_size == 0:
                    print(f"   ⚠️ Warning: {fname} is empty, skipping")
                    if not PROGRESS_UTILS_AVAILABLE:
                        doc_progress.update(1)
                    continue

                if fname.lower().endswith('.txt'):
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                    except UnicodeDecodeError:
                        # Try alternative encoding
                        with open(fpath, 'r', encoding='latin-1') as f:
                            lines = f.readlines()

                    for idx, line in enumerate(lines):
                        if line.strip():  # Only add non-empty lines
                            line_info.append({'text': line.strip(), 'page': 1, 'line_num': idx + 1})

                elif fname.lower().endswith('.docx'):
                    doc = Document(fpath)
                    lines = [p.text for p in doc.paragraphs if p.text.strip()]
                    for idx, line in enumerate(lines):
                        line_info.append({'text': line.strip(), 'page': 1, 'line_num': idx + 1})

                elif fname.lower().endswith('.pdf'):
                    reader = PdfReader(fpath)
                    for pageno, page in enumerate(reader.pages, start=1):
                        text = page.extract_text()
                        if (not text or text.isspace()) and self.reader:
                            # Use OCR with progress indication
                            if PROGRESS_UTILS_AVAILABLE:
                                doc_progress.set_description(f"👁️ OCR processing {fname} (page {pageno})")
                            ocr_lines = self.extract_text_with_ocr(fpath, pageno)
                            for lineno, line in enumerate(ocr_lines, start=1):
                                if line.strip():
                                    line_info.append({'text': line.strip(), 'page': pageno, 'line_num': lineno})
                        else:
                            lines = text.split('\n') if text else []
                            for lineno, line in enumerate(lines, start=1):
                                if line.strip():
                                    line_info.append({'text': line.strip(), 'page': pageno, 'line_num': lineno})

                # Generate embeddings for this document
                all_lines = [entry['text'] for entry in line_info if entry['text'].strip()]
                if all_lines:
                    if PROGRESS_UTILS_AVAILABLE:
                        doc_progress.set_description(f"🧠 Generating embeddings for {fname}")
                    else:
                        doc_progress.set_description(f"🧠 Embeddings: {fname}")

                    try:
                        embeddings = self.embedder.encode(all_lines, convert_to_tensor=True)
                        total_lines_processed += len(all_lines)
                    except Exception as e:
                        print(f"   ⚠️ Warning: Failed to generate embeddings for {fname}: {e}")
                        embeddings = None
                else:
                    embeddings = None

                self.doc_data.append({
                    'name': fname,
                    'lines': line_info,
                    'embeddings': embeddings
                })

                if PROGRESS_UTILS_AVAILABLE:
                    doc_progress.update(1)

            except Exception as e:
                print(f"\n❌ Error processing {fname}: {e}")
                if PROGRESS_UTILS_AVAILABLE:
                    doc_progress.update(1)
                continue

        if PROGRESS_UTILS_AVAILABLE:
            doc_progress.close()
        else:
            doc_progress.close()

        print(f"✅ Successfully processed {len(self.doc_data)} documents ({total_lines_processed} lines total)")

    def extract_text_with_ocr(self, pdf_path, page_number):
        """Extract text using OCR with progress indication"""
        try:
            with ocr_progress():
                pages = convert_from_path(pdf_path)
                if page_number > len(pages):
                    return []

                result = self.reader.readtext(pages[page_number - 1])
                text = ' '.join([x[1] for x in result])
                return text.split('\n')
        except Exception as e:
            print(f"   ⚠️ OCR error for page {page_number}: {e}")
            return []

    def expand_abbreviations(self, text):
        """Expand abbreviations based on mapping"""
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
        """Save user feedback if feedback system is available"""
        if self.feedback_handler and self.config.get('feedback_enabled', True):
            try:
                self.feedback_handler.save_feedback(query, matched_line, is_relevant)
            except Exception as e:
                print(f"⚠️ Warning: Failed to save feedback: {e}")

    def search(self, query, top_k=5, context_mode='lines'):
        """
        Search with enhanced context display and error handling
        context_mode options:
        - 'lines': Show surrounding lines (default)
        - 'paragraph': Show full paragraph
        - 'snippet': Show matched line only (original behavior)
        """
        if not self.doc_data:
            print("❌ No documents available for search")
            return []

        try:
            query_expanded = self.expand_abbreviations(query)
            query_embedding = self.embedder.encode(query_expanded, convert_to_tensor=True)
            results = []

            # Show progress for search if there are many documents
            if len(self.doc_data) > 5:
                search_progress = tqdm(
                    self.doc_data,
                    desc="🔍 Searching documents",
                    unit="doc",
                    leave=False,
                    ncols=80
                )
            else:
                search_progress = self.doc_data

            for doc in search_progress:
                if not doc['lines'] or doc['embeddings'] is None:
                    continue

                try:
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
                        try:
                            if context_mode == 'paragraph':
                                context_text = self.get_paragraph_context(doc['lines'], idx)
                            elif context_mode == 'lines':
                                context_text = self.get_context_around_line(doc['lines'], idx, page)
                            else:  # snippet
                                context_text = text
                        except Exception as e:
                            print(f"⚠️ Warning: Context generation failed: {e}")
                            context_text = text

                        results.append({
                            'document': doc['name'],
                            'line': text,
                            'context': context_text,
                            'page': page,
                            'line_num': line_num,
                            'score': data['score']
                        })

                except Exception as e:
                    print(f"⚠️ Warning: Error processing document {doc['name']}: {e}")
                    continue

            # Close progress bar if it was created
            if hasattr(search_progress, 'close'):
                search_progress.close()

            # Sort all results by score and return top_k
            results.sort(key=lambda x: x['score'], reverse=True)
            return results[:top_k]

        except Exception as e:
            print(f"❌ Error during search: {e}")
            traceback.print_exc()
            return []

    def advanced_search(self, query, filters=None, top_k=5, context_mode='lines'):
        """
        Advanced search with filters and enhanced ranking

        filters can include:
        - 'documents': list of document names to search in
        - 'pages': list of page numbers to search in
        - 'min_score': minimum similarity score threshold
        - 'date_range': for future implementation
        """
        if not self.doc_data:
            print("❌ No documents available for search")
            return []

        filters = filters or {}

        try:
            query_expanded = self.expand_abbreviations(query)
            query_embedding = self.embedder.encode(query_expanded, convert_to_tensor=True)
            results = []

            # Filter documents if specified
            docs_to_search = self.doc_data
            if 'documents' in filters:
                docs_to_search = [doc for doc in self.doc_data if doc['name'] in filters['documents']]

            print(f"🔍 Searching {len(docs_to_search)} documents with filters: {filters}")

            for doc in docs_to_search:
                if not doc['lines'] or doc['embeddings'] is None:
                    continue

                # Apply page filters if specified
                lines_to_search = doc['lines']
                if 'pages' in filters:
                    lines_to_search = [line for line in doc['lines'] if line['page'] in filters['pages']]

                if not lines_to_search:
                    continue

                try:
                    # Get embeddings for filtered lines
                    line_texts = [entry['text'] for entry in lines_to_search]
                    line_indices = [doc['lines'].index(entry) for entry in lines_to_search]

                    # Get corresponding embeddings
                    filtered_embeddings = doc['embeddings'][line_indices]

                    # Calculate semantic similarity
                    scores = util.pytorch_cos_sim(query_embedding, filtered_embeddings)[0]

                    # Combine with fuzzy matching
                    for i, (score, entry) in enumerate(zip(scores, lines_to_search)):
                        fuzz_score = fuzz.partial_ratio(query_expanded.lower(), entry['text'].lower()) / 100.0
                        combined_score = float(score) * 0.7 + fuzz_score * 0.3  # Weighted combination

                        # Apply minimum score filter
                        if 'min_score' in filters and combined_score < filters['min_score']:
                            continue

                        # Generate context
                        original_idx = line_indices[i]
                        try:
                            if context_mode == 'paragraph':
                                context_text = self.get_paragraph_context(doc['lines'], original_idx)
                            elif context_mode == 'lines':
                                context_text = self.get_context_around_line(doc['lines'], original_idx, entry['page'])
                            else:  # snippet
                                context_text = entry['text']
                        except Exception as e:
                            print(f"⚠️ Warning: Context generation failed: {e}")
                            context_text = entry['text']

                        results.append({
                            'document': doc['name'],
                            'line': entry['text'],
                            'context': context_text,
                            'page': entry['page'],
                            'line_num': entry['line_num'],
                            'score': combined_score,
                            'semantic_score': float(score),
                            'fuzzy_score': fuzz_score
                        })

                except Exception as e:
                    print(f"⚠️ Warning: Error processing document {doc['name']}: {e}")
                    continue

            # Sort by combined score and return top results
            results.sort(key=lambda x: x['score'], reverse=True)
            return results[:top_k]

        except Exception as e:
            print(f"❌ Error during advanced search: {e}")
            traceback.print_exc()
            return []

    def get_document_stats(self):
        """Get statistics about loaded documents"""
        if not self.doc_data:
            return {"total_documents": 0, "total_lines": 0, "documents": []}

        stats = {
            "total_documents": len(self.doc_data),
            "total_lines": 0,
            "documents": []
        }

        for doc in self.doc_data:
            doc_lines = len([l for l in doc['lines'] if l['text'].strip()])
            stats["total_lines"] += doc_lines

            # Get page range
            pages = set(l['page'] for l in doc['lines'])
            page_range = f"{min(pages)}-{max(pages)}" if len(pages) > 1 else str(min(pages))

            stats["documents"].append({
                "name": doc['name'],
                "lines": doc_lines,
                "pages": len(pages),
                "page_range": page_range,
                "has_embeddings": doc['embeddings'] is not None
            })

        return stats

    def search_within_document(self, query, document_name, top_k=5, context_mode='lines'):
        """Search within a specific document"""
        doc = next((d for d in self.doc_data if d['name'] == document_name), None)
        if not doc:
            print(f"❌ Document '{document_name}' not found")
            return []

        # Use advanced search with document filter
        filters = {'documents': [document_name]}
        return self.advanced_search(query, filters, top_k, context_mode)

    def reload_documents(self):
        """Reload all documents (useful for development/testing)"""
        print("🔄 Reloading documents...")
        self.load_documents()
        print("✅ Documents reloaded successfully")