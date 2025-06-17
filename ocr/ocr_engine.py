# ocr/ocr_engine.py
import os
import yaml
from pdf2image import convert_from_path
import easyocr
import pytesseract
from PIL import Image
from tqdm import tqdm
from utils.progress_utils import dynamic_progress


class OCREngine:
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.ocr_enabled = self.config.get('ocr_enabled', True)
        self.languages = self.config.get('ocr_languages', ['en'])

        if not isinstance(self.languages, (list, tuple)):
            self.languages = [self.languages]

        # Initialize OCR engines with progress indication
        self.easyocr_reader = None
        self.tesseract_available = False

        if self.ocr_enabled:
            self._initialize_ocr_engines()

    def _initialize_ocr_engines(self):
        """Initialize OCR engines with progress tracking"""
        print("🔧 Initializing OCR engines...")

        # Initialize EasyOCR
        with dynamic_progress(desc="🔧 Loading EasyOCR model", delay=1.0):
            try:
                self.easyocr_reader = easyocr.Reader(self.languages, gpu=False)
                print("✅ EasyOCR initialized successfully")
            except Exception as e:
                print(f"❌ Failed to initialize EasyOCR: {e}")
                self.easyocr_reader = None

        # Check Tesseract availability
        with dynamic_progress(desc="🔧 Checking Tesseract availability", delay=0.5):
            try:
                pytesseract.get_tesseract_version()
                self.tesseract_available = True
                print("✅ Tesseract is available")
            except Exception as e:
                print(f"⚠️ Tesseract not available: {e}")
                self.tesseract_available = False

    def extract_text_from_pdf(self, pdf_path, use_easyocr=True, use_tesseract=False):
        """Extract text from PDF using OCR with progress tracking"""
        if not self.ocr_enabled:
            return []

        try:
            # Convert PDF to images
            print(f"📄 Converting PDF to images: {os.path.basename(pdf_path)}")
            with dynamic_progress(desc="📄 Converting PDF pages", delay=1.0):
                pages = convert_from_path(pdf_path)

            all_text = []

            # Process each page with progress bar
            page_progress = tqdm(
                pages,
                desc="👁️ Processing pages with OCR",
                unit="page",
                ncols=80,
                bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )

            for page_num, page_image in enumerate(page_progress, 1):
                page_progress.set_description(f"👁️ OCR processing page {page_num}/{len(pages)}")

                page_text = []

                # Try EasyOCR first
                if use_easyocr and self.easyocr_reader:
                    try:
                        results = self.easyocr_reader.readtext(page_image)
                        page_text = [result[1] for result in results if result[2] > 0.5]  # Confidence > 0.5
                    except Exception as e:
                        print(f"⚠️ EasyOCR failed on page {page_num}: {e}")

                # Fallback to Tesseract if EasyOCR failed or not available
                if not page_text and use_tesseract and self.tesseract_available:
                    try:
                        text = pytesseract.image_to_string(page_image, lang='+'.join(self.languages))
                        page_text = [line.strip() for line in text.split('\n') if line.strip()]
                    except Exception as e:
                        print(f"⚠️ Tesseract failed on page {page_num}: {e}")

                all_text.extend(page_text)

            page_progress.close()
            print(f"✅ OCR completed. Extracted {len(all_text)} text segments from {len(pages)} pages")
            return all_text

        except Exception as e:
            print(f"❌ Failed to process PDF {pdf_path}: {e}")
            return []

    def extract_text_from_image(self, image_path, use_easyocr=True, use_tesseract=False):
        """Extract text from a single image with progress tracking"""
        if not self.ocr_enabled:
            return []

        try:
            # Load image
            with dynamic_progress(desc=f"📸 Loading image", delay=0.5):
                image = Image.open(image_path)

            extracted_text = []

            # Try EasyOCR first
            if use_easyocr and self.easyocr_reader:
                with dynamic_progress(desc="👁️ Processing with EasyOCR", delay=1.0):
                    try:
                        results = self.easyocr_reader.readtext(image)
                        extracted_text = [result[1] for result in results if result[2] > 0.5]
                    except Exception as e:
                        print(f"⚠️ EasyOCR failed: {e}")

            # Fallback to Tesseract
            if not extracted_text and use_tesseract and self.tesseract_available:
                with dynamic_progress(desc="👁️ Processing with Tesseract", delay=1.0):
                    try:
                        text = pytesseract.image_to_string(image, lang='+'.join(self.languages))
                        extracted_text = [line.strip() for line in text.split('\n') if line.strip()]
                    except Exception as e:
                        print(f"⚠️ Tesseract failed: {e}")

            print(f"✅ Extracted {len(extracted_text)} text segments from image")
            return extracted_text

        except Exception as e:
            print(f"❌ Failed to process image {image_path}: {e}")
            return []

    def batch_process_images(self, image_paths, use_easyocr=True, use_tesseract=False):
        """Process multiple images with progress tracking"""
        if not self.ocr_enabled or not image_paths:
            return {}

        results = {}

        # Process with progress bar
        image_progress = tqdm(
            image_paths,
            desc="👁️ Batch OCR processing",
            unit="image",
            ncols=80,
            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
        )

        for image_path in image_progress:
            filename = os.path.basename(image_path)
            image_progress.set_description(f"👁️ Processing {filename}")

            text = self.extract_text_from_image(image_path, use_easyocr, use_tesseract)
            results[image_path] = text

        image_progress.close()
        return results

    def get_text_confidence_scores(self, image_path):
        """Get confidence scores for extracted text using EasyOCR"""
        if not self.easyocr_reader:
            return []

        try:
            with dynamic_progress(desc="👁️ Analyzing text confidence", delay=1.0):
                image = Image.open(image_path)
                results = self.easyocr_reader.readtext(image)

            confidence_data = []
            for bbox, text, confidence in results:
                confidence_data.append({
                    'text': text,
                    'confidence': confidence,
                    'bbox': bbox
                })

            return confidence_data

        except Exception as e:
            print(f"❌ Failed to analyze confidence scores: {e}")
            return []

    def is_ocr_available(self):
        """Check if OCR is available and properly configured"""
        return self.ocr_enabled and (self.easyocr_reader is not None or self.tesseract_available)

    def get_supported_languages(self):
        """Get list of supported languages"""
        return self.languages

    def set_languages(self, languages):
        """Update OCR languages (requires reinitialization)"""
        self.languages = languages if isinstance(languages, (list, tuple)) else [languages]
        if self.ocr_enabled:
            print("🔄 Reinitializing OCR with new languages...")
            self._initialize_ocr_engines()