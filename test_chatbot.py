# test_chatbot.py
"""
Test script for DocumentChatEngine chatbot functionality.
"""
from llama_cpp import Llama
from search.search_engine import SmartSearcher
from chat.document_chat import DocumentChatEngine

if __name__ == "__main__":
    # Initialize backend components
    searcher = SmartSearcher()
    llm = Llama(
        model_path="models/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        n_ctx=4096,
        n_threads=8,
        n_gpu_layers=35,
        use_mlock=True
    )
    chatbot = DocumentChatEngine(model=llm, searcher=searcher)

    print("\n🤖 Offline Document Chatbot Test\nType 'exit' to quit.\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "exit":
            break
        response = chatbot.chat(user_input)
        print(f"Bot: {response}\n")
