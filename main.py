# main.py
import os
import sys
from search.search_engine import SmartSearcher
from llama_cpp import Llama
from chat.document_chat import DocumentChatEngine
from utils.progress_utils import (
    loading_progress,
    rephrasing_progress,
    summarizing_progress,
    search_progress
)

# Suppress llama.cpp verbose output
os.environ['LLAMA_CPP_LOG_LEVEL'] = '0'  # Set to 0 to disable logging
sys.stderr = open(os.devnull, 'w')  # Redirect stderr to suppress performance prints


def print_results(results):
    print("\n🔍 Top Search Results:\n")
    for idx, result in enumerate(results, 1):
        print(f"{'=' * 60}")
        print(f"Result {idx}: [Doc: {result.get('document', 'N/A')}]")
        print(f"Page: {result.get('page', 'N/A')} | Line: {result.get('line_num', 'N/A')}")
        score = result.get('score', None)
        try:
            print(f"Score: {float(score):.3f}")
        except (TypeError, ValueError):
            print(f"Score: {score}")

        print(f"\n📄 Context:")
        print("-" * 40)
        # Display the enhanced context instead of just the single line
        context = result.get('context', result.get('line', 'N/A'))
        print(context)
        print("-" * 40)
        print()


def collect_feedback(searcher, query, results):
    print("💬 Provide feedback on the results:")
    print("   Type the result number to mark it as RELEVANT.")
    print("   Prefix it with '-' to mark as IRRELEVANT.")
    print("   Press Enter when done.\n")

    feedback_input = input("Enter feedback (e.g., 1 -2 3): ").strip().split()
    for item in feedback_input:
        if item.startswith('-') and item[1:].isdigit():
            idx = int(item[1:]) - 1
            if 0 <= idx < len(results):
                searcher.save_user_feedback(query, results[idx]['line'], False)
        elif item.isdigit():
            idx = int(item) - 1
            if 0 <= idx < len(results):
                searcher.save_user_feedback(query, results[idx]['line'], True)


def initialize_system():
    """Initialize the search system and LLM with progress tracking"""
    print("🚀 Starting AI-Based Local Document Search System...")

    # Initialize searcher with progress tracking
    print("📚 Loading documents and building search index...")
    with loading_progress():
        searcher = SmartSearcher()

    print("🤖 Loading AI language model...")
    with loading_progress():
        llm = Llama(
            model_path="models/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
            n_ctx=4096,
            n_threads=8,
            n_gpu_layers=35,
            use_mlock=True,
            verbose=False  # Disable verbose output
        )

    print("🔧 Initializing chat engine...")
    chat_engine = DocumentChatEngine(model=llm, searcher=searcher)

    print("✅ System initialization complete!\n")
    return searcher, chat_engine


def perform_search(searcher, query, context_mode="lines"):
    """Perform search with progress tracking"""
    with search_progress():
        return searcher.search(query, context_mode=context_mode)


def rephrase_text(chat_engine, text, tone):
    """Rephrase text with progress tracking"""
    with rephrasing_progress():
        return chat_engine.rephrase_line(text, tone=tone)


def generate_summary(chat_engine, results, query, length=None):
    """Generate summary with progress tracking"""
    with summarizing_progress():
        return chat_engine.summarize_search_results(results, query, length)


def main():
    # Initialize system with progress bars
    searcher, chat_engine = initialize_system()

    print("📁 AI-Based Local Document Search\n")
    print(f"Available summary lengths: {', '.join(chat_engine.get_available_summary_lengths())}")
    print("Context modes: lines (surrounding lines), paragraph (full paragraph), snippet (matched line only)")
    print("💡 Tip: Progress bars will appear automatically for longer operations")
    print()

    # Default context mode
    context_mode = "lines"

    while True:
        query = input("🔎 Enter your search query (or type 'exit' to quit): ").strip()
        if query.lower() == 'exit':
            break

        # Check if user wants to change context mode
        if query.lower().startswith('context:'):
            mode = query.split(':', 1)[1].strip().lower()
            if mode in ['lines', 'paragraph', 'snippet']:
                context_mode = mode
                print(f"✅ Context mode set to: {context_mode}")
                continue
            else:
                print("❌ Invalid context mode. Use: lines, paragraph, or snippet")
                continue

        # Perform search with progress tracking
        results = perform_search(searcher, query, context_mode)
        print_results(results)
        collect_feedback(searcher, query, results)

        # Ask if user wants to rephrase a specific result
        select_input = input("✏️ Enter the result number to rephrase (or 'skip'): ").strip().lower()
        if select_input.isdigit():
            idx = int(select_input) - 1
            if 0 <= idx < len(results):
                tone = input(
                    "🎯 Enter desired tone (e.g., formal, casual, assertive, technical, persuasive, poetic, empathetic): ").strip().lower()
                # Use the context for rephrasing instead of just the single line
                text_to_rephrase = results[idx].get('context', results[idx]['line'])

                # Rephrase with progress tracking
                rephrased = rephrase_text(chat_engine, text_to_rephrase, tone)
                print("\n🗣️ Rephrased Result:")
                print(rephrased)

        summarize = input("🧠 Would you like a summary of the search results? (yes/no): ").strip().lower()
        if summarize in ['yes', 'y']:
            # Ask for summary length
            length = input(
                f"📏 Summary length ({'/'.join(chat_engine.get_available_summary_lengths())}) [default: medium]: ").strip().lower()
            if not length:
                length = None

            # Generate summary with progress tracking
            summary = generate_summary(chat_engine, results, query, length)
            print("\n📋 Summary:")
            print(summary)

        print(
            f"\n💡 Tip: Type 'context:paragraph' or 'context:lines' or 'context:snippet' to change how much text is shown")


if __name__ == "__main__":
    main()