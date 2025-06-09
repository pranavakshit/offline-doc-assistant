# main.py
from search.search_engine import SmartSearcher

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
    print("📁 AI-Based Local Document Search\n")

    while True:
        query = input("🔎 Enter your search query (or type 'exit' to quit): ").strip()
        if query.lower() == 'exit':
            break
        results = searcher.search(query)
        print_results(results)
        collect_feedback(searcher, query, results)

if __name__ == "__main__":
    main()
