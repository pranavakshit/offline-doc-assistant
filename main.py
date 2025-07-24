# main.py
from search.search_engine import SmartSearcher
from llama_cpp import Llama
from chat.document_chat import DocumentChatEngine


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
    print("Context modes: lines (surrounding lines), paragraph (full paragraph), snippet (matched line only)")
    print()

    # Default context mode
    context_mode = "lines"

    def list_documents():
        docs_dir = "docs"
        docs = [f for f in os.listdir(docs_dir) if f.lower().endswith((".pdf", ".docx", ".txt"))]
        print("\n� Indexed Documents:")
        for i, doc in enumerate(docs, 1):
            print(f"{i}. {doc}")
        return docs

    def remove_document():
        docs = list_documents()
        idx = input("Enter the number of the document to remove (or 'cancel'): ").strip()
        if idx.isdigit():
            idx = int(idx) - 1
            if 0 <= idx < len(docs):
                os.remove(os.path.join("docs", docs[idx]))
                print(f"✅ Removed: {docs[idx]}")
        else:
            print("Cancelled.")

    def reindex_documents():
        print("🔄 Reindexing all documents...")
        # Call your chunking/indexing logic here
        from utils.file_loader import load_files
        load_files("docs")
        print("✅ Reindexing complete!")

    import os

    while True:
        print("\nOptions:")
        print("1. Search documents")
        print("2. List indexed documents")
        print("3. Remove a document")
        print("4. Reindex all documents")
        print("5. Change context mode")
        print("6. Exit")
        choice = input("Select an option (1-6): ").strip()

        if choice == "6":
            break
        elif choice == "2":
            list_documents()
        elif choice == "3":
            remove_document()
        elif choice == "4":
            reindex_documents()
        elif choice == "5":
            mode = input("Enter context mode (lines/paragraph/snippet): ").strip().lower()
            if mode in ["lines", "paragraph", "snippet"]:
                context_mode = mode
                print(f"✅ Context mode set to: {context_mode}")
            else:
                print("❌ Invalid context mode. Use: lines, paragraph, or snippet")
        elif choice == "1":
            query = input("🔎 Enter your search query (or type 'back' to return): ").strip()
            if query.lower() == "back":
                continue
            results = searcher.search(query, context_mode=context_mode)
            print_results(results)
            collect_feedback(searcher, query, results)

            # Ask if user wants to rephrase a specific result
            select_input = input("✏️ Enter the result number to rephrase (or 'skip'): ").strip().lower()
            if select_input.isdigit():
                idx = int(select_input) - 1
                if 0 <= idx < len(results):
                    tone = input(
                        "🎯 Enter desired tone (e.g., formal, casual, assertive, technical, persuasive, poetic, empathetic): ").strip().lower()
                    text_to_rephrase = results[idx].get('context', results[idx]['line'])
                    rephrased = chat_engine.rephrase_line(text_to_rephrase, tone=tone)
                    print("\n🗣️ Rephrased Result:")
                    print(rephrased)

            summarize = input("🧠 Would you like a summary of the search results? (yes/no): ").strip().lower()
            if summarize in ['yes', 'y']:
                length = input(
                    f"📏 Summary length ({'/'.join(chat_engine.get_available_summary_lengths())}) [default: medium]: ").strip().lower()
                if not length:
                    length = None

                summary = chat_engine.summarize_search_results(results, query, length)
                print("\n📋 Summary:")
                print(summary)

            print(
                f"\n💡 Tip: Type 'context:paragraph' or 'context:lines' or 'context:snippet' to change how much text is shown")


if __name__ == "__main__":
    main()