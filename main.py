# main.py
from search.search_engine import SmartSearcher
from llama_cpp import Llama
from chat.document_chat import DocumentChatEngine


def print_results(results):
    print("\n🔍 Top Search Results:\n")
    for idx, result in enumerate(results, 1):
        print(f"{idx}. [Doc: {result.get('document', 'N/A')}]")
        print(f"   Page: {result.get('page', 'N/A')} | Line: {result.get('line_num', 'N/A')}")
        print(f"   Text: {result.get('line', 'N/A')}")
        score = result.get('score', None)
        try:
            print(f"   Score: {float(score):.3f}\n")
        except (TypeError, ValueError):
            print(f"   Score: {score}\n")


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


def main():
    searcher = SmartSearcher()

    llm = Llama(
        model_path="models/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        n_ctx=4096,
        n_threads=8,
        n_gpu_layers=35,
        use_mlock=True
    )

    chat_engine = DocumentChatEngine(model=llm, searcher=searcher)

    print("📁 AI-Based Local Document Search\n")
    print(f"Available summary lengths: {', '.join(chat_engine.get_available_summary_lengths())}")
    print()

    while True:
        query = input("🔎 Enter your search query (or type 'exit' to quit): ").strip()
        if query.lower() == 'exit':
            break

        results = searcher.search(query)
        print_results(results)
        collect_feedback(searcher, query, results)

        # Ask if user wants to rephrase a specific result
        select_input = input("✏️ Enter the result number to rephrase (or 'skip'): ").strip().lower()
        if select_input.isdigit():
            idx = int(select_input) - 1
            if 0 <= idx < len(results):
                tone = input(
                    "🎯 Enter desired tone (e.g., formal, casual, assertive, technical, persuasive, poetic, empathetic): ").strip().lower()
                rephrased = chat_engine.rephrase_line(results[idx]['line'], tone=tone)
                print("\n🗣️ Rephrased Result:")
                print(rephrased)

        summarize = input("🧠 Would you like a summary of the search results? (yes/no): ").strip().lower()
        if summarize in ['yes', 'y']:
            # Ask for summary length
            length = input(
                f"📏 Summary length ({'/'.join(chat_engine.get_available_summary_lengths())}) [default: medium]: ").strip().lower()
            if not length:
                length = None

            summary = chat_engine.summarize_search_results(results, query, length)
            print("\n📋 Summary:")
            print(summary)


if __name__ == "__main__":
    main()