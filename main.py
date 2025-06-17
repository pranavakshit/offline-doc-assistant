# main.py - Fixed version with full functionality
import os
import sys
import traceback
from search.search_engine import SmartSearcher
from llama_cpp import Llama

# Try to import chat engine, but continue without it if it fails
try:
    from chat.document_chat import DocumentChatEngine

    CHAT_ENGINE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Warning: DocumentChatEngine not available: {e}")
    print("💡 Continuing without chat features...")
    CHAT_ENGINE_AVAILABLE = False

# Try to import progress utils, but use simple alternatives if not available
try:
    from utils.progress_utils import (
        loading_progress,
        rephrasing_progress,
        summarizing_progress,
        search_progress
    )

    PROGRESS_UTILS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Warning: Progress utils not available: {e}")
    print("💡 Using simple progress indicators...")
    PROGRESS_UTILS_AVAILABLE = False

    # Simple context managers as fallbacks
    from contextlib import contextmanager


    @contextmanager
    def loading_progress():
        print("⏳ Loading...")
        yield
        print("✅ Done")


    @contextmanager
    def rephrasing_progress():
        print("⏳ Rephrasing...")
        yield
        print("✅ Done")


    @contextmanager
    def summarizing_progress():
        print("⏳ Summarizing...")
        yield
        print("✅ Done")


    @contextmanager
    def search_progress():
        print("⏳ Searching...")
        yield
        print("✅ Done")

# Suppress llama.cpp verbose output
os.environ['LLAMA_CPP_LOG_LEVEL'] = '0'
if hasattr(sys.stderr, 'close'):
    original_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
else:
    original_stderr = None


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
        context = result.get('context', result.get('line', 'N/A'))
        print(context)
        print("-" * 40)
        print()


def collect_feedback(searcher, query, results):
    """Collect user feedback on search results"""
    if not hasattr(searcher, 'save_user_feedback') or not searcher.feedback_handler:
        print("💬 Feedback system not available in this session")
        return

    print("💬 Provide feedback on the results:")
    print("   Type the result number to mark it as RELEVANT.")
    print("   Prefix it with '-' to mark as IRRELEVANT.")
    print("   Press Enter when done.\n")

    try:
        feedback_input = input("Enter feedback (e.g., 1 -2 3): ").strip().split()
        for item in feedback_input:
            if item.startswith('-') and item[1:].isdigit():
                idx = int(item[1:]) - 1
                if 0 <= idx < len(results):
                    searcher.save_user_feedback(query, results[idx]['line'], False)
                    print(f"✅ Marked result {idx + 1} as irrelevant")
            elif item.isdigit():
                idx = int(item) - 1
                if 0 <= idx < len(results):
                    searcher.save_user_feedback(query, results[idx]['line'], True)
                    print(f"✅ Marked result {idx + 1} as relevant")
    except Exception as e:
        print(f"⚠️ Error collecting feedback: {e}")


def initialize_system():
    """Initialize the search system and LLM with progress tracking and error handling"""
    print("🚀 Starting AI-Based Local Document Search System...")

    # Initialize searcher with progress tracking
    print("📚 Loading documents and building search index...")
    try:
        with loading_progress():
            searcher = SmartSearcher()
        print("✅ Search system initialized successfully")
    except Exception as e:
        print(f"❌ Error initializing search system: {e}")
        print("🔍 Full error:")
        traceback.print_exc()
        raise

    # Initialize LLM
    llm = None
    chat_engine = None

    model_path = "models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"

    if os.path.exists(model_path):
        print("🤖 Loading AI language model...")
        try:
            with loading_progress():
                llm = Llama(
                    model_path=model_path,
                    n_ctx=4096,
                    n_threads=8,
                    n_gpu_layers=35,
                    use_mlock=True,
                    verbose=False
                )
            print("✅ Language model loaded successfully")

            # Initialize chat engine if available
            if CHAT_ENGINE_AVAILABLE:
                print("🔧 Initializing chat engine...")
                try:
                    chat_engine = DocumentChatEngine(model=llm, searcher=searcher)
                    print("✅ Chat engine initialized successfully")
                except Exception as e:
                    print(f"⚠️ Warning: Chat engine initialization failed: {e}")
                    print("💡 Continuing without advanced features...")
                    chat_engine = None
            else:
                print("⚠️ Chat engine not available - some features will be disabled")

        except Exception as e:
            print(f"⚠️ Warning: LLM initialization failed: {e}")
            print("💡 Continuing with search-only functionality...")
            llm = None
            chat_engine = None
    else:
        print(f"⚠️ Warning: Model file not found at {model_path}")
        print("💡 Continuing with search-only functionality...")

    print("✅ System initialization complete!\n")
    return searcher, chat_engine, llm


def perform_search(searcher, query, context_mode="lines"):
    """Perform search with progress tracking"""
    with search_progress():
        return searcher.search(query, context_mode=context_mode)


def rephrase_text(chat_engine, text, tone):
    """Rephrase text with progress tracking"""
    if not chat_engine:
        print("❌ Rephrasing not available - chat engine not initialized")
        return None

    try:
        with rephrasing_progress():
            return chat_engine.rephrase_line(text, tone=tone)
    except Exception as e:
        print(f"❌ Error during rephrasing: {e}")
        return None


def generate_summary(chat_engine, results, query, length=None):
    """Generate summary with progress tracking"""
    if not chat_engine:
        print("❌ Summarization not available - chat engine not initialized")
        return None

    try:
        with summarizing_progress():
            return chat_engine.summarize_search_results(results, query, length)
    except Exception as e:
        print(f"❌ Error during summarization: {e}")
        return None


def create_simple_summary(results, query):
    """Create a simple text-based summary when AI is not available"""
    if not results:
        return "No results to summarize."

    summary_parts = [f"Search Results Summary for: '{query}'", "=" * 50]

    for i, result in enumerate(results[:5], 1):
        doc_name = result.get('document', 'Unknown')
        page = result.get('page', 'N/A')
        line = result.get('line', '')[:100] + ('...' if len(result.get('line', '')) > 100 else '')
        summary_parts.append(f"{i}. {doc_name} (Page {page}): {line}")

    if len(results) > 5:
        summary_parts.append(f"... and {len(results) - 5} more results")

    return '\n'.join(summary_parts)


def main():
    # Initialize system with progress bars and error handling
    try:
        searcher, chat_engine, llm = initialize_system()
    except Exception as e:
        print(f"❌ Critical error during initialization: {e}")
        print("🔧 Please check your configuration and try again")
        return

    print("📁 AI-Based Local Document Search\n")

    # Show available features
    features = []
    if chat_engine:
        if hasattr(chat_engine, 'get_available_summary_lengths'):
            summary_lengths = chat_engine.get_available_summary_lengths()
            features.append(f"Summary lengths: {', '.join(summary_lengths)}")
        features.append("✅ Rephrasing")
        features.append("✅ AI Summarization")
    else:
        features.append("⚠️ Rephrasing (disabled - no chat engine)")
        features.append("⚠️ AI Summarization (disabled - basic summary available)")

    if searcher.feedback_handler:
        features.append("✅ Feedback collection")
    else:
        features.append("⚠️ Feedback collection (disabled)")

    print("Available features:")
    for feature in features:
        print(f"  {feature}")

    print("\nContext modes: lines (surrounding lines), paragraph (full paragraph), snippet (matched line only)")
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
        try:
            results = perform_search(searcher, query, context_mode)
            print_results(results)

            if results:
                # Collect feedback
                collect_feedback(searcher, query, results)

                # Ask if user wants to rephrase a specific result
                if chat_engine:
                    select_input = input("✏️ Enter the result number to rephrase (or 'skip'): ").strip().lower()
                    if select_input.isdigit():
                        idx = int(select_input) - 1
                        if 0 <= idx < len(results):
                            tone = input(
                                "🎯 Enter desired tone (e.g., formal, casual, assertive, technical, persuasive, poetic, empathetic): ").strip().lower()
                            text_to_rephrase = results[idx].get('context', results[idx]['line'])

                            rephrased = rephrase_text(chat_engine, text_to_rephrase, tone)
                            if rephrased:
                                print("\n🗣️ Rephrased Result:")
                                print(rephrased)
                else:
                    print("⚠️ Rephrasing feature not available (chat engine not initialized)")

                # Ask for summary
                summarize = input("🧠 Would you like a summary of the search results? (yes/no): ").strip().lower()
                if summarize in ['yes', 'y']:
                    if chat_engine:
                        # Ask for summary length
                        try:
                            available_lengths = chat_engine.get_available_summary_lengths()
                            length = input(
                                f"📏 Summary length ({'/'.join(available_lengths)}) [default: medium]: ").strip().lower()
                            if not length:
                                length = None

                            summary = generate_summary(chat_engine, results, query, length)
                            if summary:
                                print("\n📋 AI Summary:")
                                print(summary)
                        except Exception as e:
                            print(f"⚠️ AI summary failed: {e}")
                            print("\n📋 Basic Summary:")
                            print(create_simple_summary(results, query))
                    else:
                        print("\n📋 Basic Summary:")
                        print(create_simple_summary(results, query))
            else:
                print("No results found for your query.")

        except Exception as e:
            print(f"❌ Error during search: {e}")
            print("🔍 Please try a different query or check your setup")

        print(
            f"\n💡 Tip: Type 'context:paragraph' or 'context:lines' or 'context:snippet' to change how much text is shown")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()
    finally:
        # Restore stderr if we redirected it
        if 'original_stderr' in locals() and original_stderr:
            sys.stderr.close()
            sys.stderr = original_stderr