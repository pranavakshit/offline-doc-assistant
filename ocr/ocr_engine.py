import easyocr
from pdf2image import convert_from_path
from PIL import Image
import pytesseract

class OCREngine:
    def __init__(self, languages=['en']):
        self.languages = languages
        self.reader = easyocr.Reader(languages)

    def image_to_text_easyocr(self, image):
        """
        Extract text from a PIL Image using EasyOCR.
        """
        result = self.reader.readtext(image)
        return ' '.join([x[1] for x in result])

    def image_to_text_tesseract(self, image):
        """
        Extract text from a PIL Image using pytesseract.
        """
        return pytesseract.image_to_string(image, lang='+'.join(self.languages))

    def pdf_page_to_text(self, pdf_path, page_number, method='easyocr'):
        """
        Convert a specific page of a PDF to text using OCR.
        method: 'easyocr' or 'tesseract'
        """
        pages = convert_from_path(pdf_path)
        if page_number < 1 or page_number > len(pages):
            raise ValueError("Invalid page number")
        image = pages[page_number - 1]
        if method == 'easyocr':
            return self.image_to_text_easyocr(image)
        else:
            return self.image_to_text_tesseract(image)

    def pdf_to_text(self, pdf_path, method='easyocr'):
        """
        Extract text from all pages of a PDF using OCR.
        Returns a list of text strings, one per page.
        """
        pages = convert_from_path(pdf_path)
        texts = []
        for image in pages:
            if method == 'easyocr':
                texts.append(self.image_to_text_easyocr(image))
            else:
                texts.append(self.image_to_text_tesseract(image))
        return texts
