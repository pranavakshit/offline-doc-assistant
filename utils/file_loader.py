import os
from PyPDF2 import PdfReader
from docx import Document

def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i + chunk_size]
        chunks.append(" ".join(chunk))
        i += chunk_size - overlap
    return chunks

class FileLoader:
    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.supported_extensions = ['.txt', '.pdf', '.docx']

    def _load_txt(self, file_path):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def _load_pdf(self, file_path):
        reader = PdfReader(file_path)
        text = ''
        for page in reader.pages:
            text += page.extract_text() or ''
        return text

    def _load_docx(self, file_path):
        doc = Document(file_path)
        return '\n'.join([para.text for para in doc.paragraphs])

    def load_documents(self):
        chunks = []
        for root, _, files in os.walk(self.folder_path):
            for file in files:
                ext = os.path.splitext(file)[-1].lower()
                if ext in self.supported_extensions:
                    file_path = os.path.join(root, file)
                    try:
                        if ext == '.txt':
                            text = self._load_txt(file_path)
                        elif ext == '.pdf':
                            text = self._load_pdf(file_path)
                        elif ext == '.docx':
                            text = self._load_docx(file_path)
                        else:
                            continue
                        file_chunks = chunk_text(text)
                        for chunk in file_chunks:
                            chunks.append((file, chunk))
                    except Exception as e:
                        print(f"❌ Failed to process {file_path}: {e}")
        return chunks
