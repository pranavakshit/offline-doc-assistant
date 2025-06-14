# 🧠 Offline AI-Powered Document Assistant

A powerful offline AI assistant for documents. Supports chatting with files, OCR-based search, summarization, rephrasing, learning from feedback, and more. Built for secure enterprise environments like Indian Oil Corporation Limited (IOCL).

---

## 🚀 Features

1. **Chat with Document** – Ask questions and get answers from a document's content  
2. **Context Isolation** – Multiple unrelated documents handled independently  
3. **OCR** – Optical Character Recognition for scanned PDFs and image-based documents  
4. **Smart Search** – Tolerant of typos, abbreviations, and scanned PDFs via OCR  
5. **Feedback-Based Learning** – Remembers user choices to improve future relevance  
6. **Ranked Results** – Combines fuzzy match, semantic similarity, and feedback scores  
7. **Summarization** – Provides concise or detailed summaries of full or partial documents
8. **Rephrasing** – Reword content into different tones like formal, simplified, bullet, etc.  

---

## 🧩 Supported Formats
- .pdf (including scanned/image-based)
- .docx
- .txt

---

## 🛠️ Tech Stack

| Component            | Library/Tool                  |
|----------------------|------------------------------|
| OCR                  | Tesseract / EasyOCR          |
| Embedding            | sentence-transformers        |
| LLM                  | Mistral 7B Instruct (llama.cpp) |
| Summarization        | t5-small or bart             |
| Feedback Store       | Local JSON / SQLite          |
| UI                   | CLI or Tkinter (optional)    |

---

## ⚙️ Configuration

Configurable via config.yaml including paths, OCR, models, feedback.

---

## 🔐 Offline & Private

Fully local processing, no cloud.

---

## 📦 Usage

1. Clone repo  
   `git clone https://github.com/your-org/offline-doc-assistant.git`  
   `cd offline-doc-assistant`  

2. Install dependencies  
   `pip install -r requirements.txt`  

3. Put files in docs/  

4. Run  
   `python main.py`  

---

## 👥 Authors

- Pranav Akshit – Chat, Context Isolation, OCR  
- Ananya Rana – Smart Search, Feedback Learning, Summarization, Rephrasing