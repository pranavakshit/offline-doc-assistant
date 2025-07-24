import streamlit as st
from llama_cpp import Llama
from search.search_engine import SmartSearcher
from chat.document_chat import DocumentChatEngine
import os

st.set_page_config(page_title="Offline Document Assistant", layout="wide")

# --- Theme and Mode Persistence ---
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "light"

def set_theme(mode):
    st.session_state.theme_mode = mode

# --- Custom CSS for Light/Dark Mode ---
def inject_theme_css(mode):
    if mode == "light":
        st.markdown(
            """
            <style>
                color: #22223b !important;
            }
            .stCaption, .stSidebar .stCaption { color: #1d3557 !important; }
            body, .stApp { background-color: #ffffe3 !important; }
            .stTextInput>div>div>input, .stTextArea>div>textarea, .stSelectbox>div>div>div>div { background-color: #fff !important; color: #22223b !important; }
            .custom-card { background: linear-gradient(90deg, #ffdef2 0%, #f2e2ff 25%, #e2eeff 50%, #ddfffc 75%, #ffffe3 100%); border-radius: 10px; padding: 16px; margin-bottom: 10px; color: #22223b !important; }
            .custom-chat { background: #e2eeff; border-radius: 10px; padding: 12px; margin-bottom: 8px; color: #22223b !important; }
            .custom-header { color: #1d3557 !important; }
            .custom-sub { color: #457b9d !important; }
            .stButton>button { color: #22223b !important; background-color: #fff !important; border: 1px solid #e2eeff !important; }
            .stButton>button:hover { background-color: #e2eeff !important; color: #1d3557 !important; }
            .stAlert, .stAlert p, .stAlert span, .stAlert div { color: #22223b !important; }
            textarea, .stTextArea textarea { color: #22223b !important; background-color: #fff !important; }
            </style>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <style>
                color: #e4e6eb !important;
            }
            .stCaption, .stSidebar .stCaption { color: #a8daf9 !important; }
            body, .stApp { background-color: #18191a !important; }
            .stTextInput>div>div>input, .stTextArea>div>textarea, .stSelectbox>div>div>div>div { background-color: #23272f !important; color: #e4e6eb !important; }
            .custom-card { background: #23272f; border-radius: 10px; padding: 16px; margin-bottom: 10px; color: #e4e6eb !important; }
            .custom-chat { background: #23272f; border-radius: 10px; padding: 12px; margin-bottom: 8px; color: #e4e6eb !important; }
            .custom-header { color: #e4e6eb !important; }
            .custom-sub { color: #a8daf9 !important; }
            </style>
            """,
            unsafe_allow_html=True
        )

inject_theme_css(st.session_state.theme_mode)

# --- Theme Switch ---
with st.sidebar:
    st.markdown("---")
    if st.button(f"Switch to {'Dark' if st.session_state.theme_mode == 'light' else 'Light'} Mode", key="theme_toggle_btn"):
        set_theme("dark" if st.session_state.theme_mode == "light" else "light")
        st.rerun()

# --- Session State Initialization ---
import json
search_history_path = os.path.join("results", "search_history.json")
chat_history_path = os.path.join("results", "chat_history.json")
def load_history(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []
def save_history(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

if "chat_engine" not in st.session_state:
    searcher = SmartSearcher()
    llm = Llama(
        model_path="models/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        n_ctx=4096,
        n_threads=8,
        n_gpu_layers=35,
        use_mlock=True
    )
    st.session_state.chat_engine = DocumentChatEngine(model=llm, searcher=searcher)
    st.session_state.context_mode = "lines"
    st.session_state.last_results = []
    st.session_state.last_query = ""
    st.session_state.search_history_search = load_history(search_history_path)
    st.session_state.search_history_chat = load_history(chat_history_path)
    st.session_state.active_section = "Search, Summarize & Rephrase"
    st.session_state.chat_history = []

chat_engine = st.session_state.chat_engine

# --- Sidebar ---
import os

with st.sidebar:
    st.markdown("<h2 class='custom-header'>📚 Doc Assistant</h2>", unsafe_allow_html=True)
    section = st.radio(
        "Main Menu",
        options=["Search, Summarize & Rephrase", "Chat"],
        index=["Search, Summarize & Rephrase", "Chat"].index(st.session_state.active_section),
        key="sidebar_section"
    )
    st.session_state.active_section = section

    st.markdown("---")
    # --- Document Management ---
    st.subheader("Document Management")
    docs_dir = "docs"
    try:
        # Upload
        uploaded_file = st.file_uploader("Upload Document", type=["pdf", "docx", "txt"], key="sidebar_upload")
        if uploaded_file is not None:
            file_path = os.path.join(docs_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"Uploaded: {uploaded_file.name}")
            st.rerun()
        # List
        docs = [f for f in os.listdir(docs_dir) if f.lower().endswith((".pdf", ".docx", ".txt"))]
        st.markdown("**Indexed Documents:**")
        if docs:
            for doc in docs:
                st.write(doc)
        else:
            st.caption("No documents indexed.")
        # Remove
        remove_doc = st.selectbox("Remove Document", ["None"] + docs, key="sidebar_remove")
        if remove_doc != "None":
            if st.button(f"Remove {remove_doc}", key="sidebar_remove_btn"):
                os.remove(os.path.join(docs_dir, remove_doc))
                st.success(f"Removed: {remove_doc}")
                st.rerun()
        # Reindex
        if st.button("🔄 Reindex All Documents", key="sidebar_reindex"):
            from utils.file_loader import FileLoader
            loader = FileLoader(docs_dir)
            loader.refresh_cache()
            st.success("Reindexing complete!")
        # Context mode
        context_mode = st.selectbox(
            "Context Mode",
            options=["lines", "paragraph", "snippet"],
            index=["lines", "paragraph", "snippet"].index(st.session_state.context_mode),
            key="sidebar_context_mode"
        )
        st.session_state.context_mode = context_mode
    except Exception as e:
        st.warning(f"Sidebar error: {e}")
    st.markdown("---")
    # --- Search/Chat History ---
    col_search, col_chat = st.columns(2)
    with col_search:
        st.markdown("<b class='custom-sub'>Search History</b>", unsafe_allow_html=True)
        history_list = st.session_state.search_history_search
        history_key_prefix = "history_search_"
        if history_list:
            for i, q in enumerate(reversed(history_list[-7:]), 1):
                if st.button(q, key=f"{history_key_prefix}{i}"):
                    st.session_state["pending_query"] = q
                    st.session_state.active_section = "Search, Summarize & Rephrase"
                    st.rerun()
        else:
            st.caption("No search history yet.")
    with col_chat:
        st.markdown("<b class='custom-sub'>Chat History</b>", unsafe_allow_html=True)
        history_list = st.session_state.search_history_chat
        history_key_prefix = "history_chat_"
        if history_list:
            for i, q in enumerate(reversed(history_list[-7:]), 1):
                if st.button(q, key=f"{history_key_prefix}{i}"):
                    st.session_state["pending_query"] = q
                    st.session_state.active_section = "Chat"
                    st.rerun()
        else:
            st.caption("No chat history yet.")

    st.markdown("---")
    st.caption("Offline. All data stays on your device.")

# --- Main UI ---
st.markdown("<h1 class='custom-header'>Welcome to Offline Document Assistant</h1>", unsafe_allow_html=True)
st.markdown("<p class='custom-sub'>Search, chat, summarize, and rephrase your documents – all offline.</p>", unsafe_allow_html=True)

if st.session_state.active_section == "Search, Summarize & Rephrase":
    # Set query_input from pending_query before widget is created
    if "pending_query" in st.session_state:
        st.session_state["query_input"] = st.session_state["pending_query"]
        del st.session_state["pending_query"]

    with st.container():
        st.markdown("#### 🔎 Search Documents")
        cols = st.columns([3, 1])
        with cols[0]:
            query = st.text_input("Enter your search query:", value=st.session_state.get("query_input", ""), key="query_input")
        with cols[1]:
            context_mode = st.selectbox(
                "Context mode:",
                options=["lines", "paragraph", "snippet"],
                index=["lines", "paragraph", "snippet"].index(st.session_state.context_mode)
            )
            st.session_state.context_mode = context_mode

        if st.button("Search", use_container_width=True) and query.strip():
            results = chat_engine.searcher.search(query, context_mode=context_mode)
            st.session_state.last_results = results
            st.session_state.last_query = query
            if query not in st.session_state.search_history_search:
                st.session_state.search_history_search.append(query)
                save_history(search_history_path, st.session_state.search_history_search)

    # Results Card
    if st.session_state.last_results:
        st.markdown("#### 📄 Top Search Results")
        for idx, result in enumerate(st.session_state.last_results, 1):
            with st.container():
                st.markdown(
                    f"<div class='custom-card'>"
                    f"<b class='custom-header'>Result {idx}:</b> <span class='custom-sub'>[Doc: {result.get('document', 'N/A')}]</span><br>"
                    f"<span class='custom-sub'>Page:</span> {result.get('page', 'N/A')} | "
                    f"<span class='custom-sub'>Line:</span> {result.get('line_num', 'N/A')} | "
                    f"<span class='custom-sub'>Score:</span> {result.get('score', 0):.3f}"
                    f"</div>",
                    unsafe_allow_html=True
                )
                st.code(result.get('context', result.get('line', 'N/A')), language="markdown")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"👍 Relevant {idx}", key=f"relevant_{idx}"):
                        chat_engine.searcher.save_user_feedback(st.session_state.last_query, result['line'], True)
                        st.success("Marked as relevant!")
                with col2:
                    if st.button(f"👎 Irrelevant {idx}", key=f"irrelevant_{idx}"):
                        chat_engine.searcher.save_user_feedback(st.session_state.last_query, result['line'], False)
                        st.warning("Marked as irrelevant.")

                st.markdown("**✏️ Rephrase Result:**")
                tone = st.selectbox(
                    "Select tone:",
                    options=["formal", "casual", "assertive", "technical", "persuasive", "poetic", "empathetic"],
                    key=f"tone_{idx}"
                )
                if st.button(f"Rephrase {idx}", key=f"rephrase_{idx}"):
                    text_to_rephrase = result.get('context', result.get('line'))
                    rephrased = chat_engine.rephrase_line(text_to_rephrase, tone=tone)
                    st.text_area("Rephrased Result", value=rephrased, height=100, key=f"rephrased_{idx}")

                st.markdown("<hr style='border:1px solid #e9ecef;'>", unsafe_allow_html=True)

    # Summary Card
    if st.session_state.last_results:
        with st.expander("🧠 Summarize Search Results"):
            available_lengths = chat_engine.get_available_summary_lengths()
            length = st.selectbox("Summary length:", options=available_lengths, key="summary_length")
            if st.button("Summarize"):
                summary = chat_engine.summarize_search_results(
                    st.session_state.last_results, st.session_state.last_query, length
                )
                st.text_area("Summary", value=summary, height=150)

    # Chat history for search section
    with st.expander("💬 Chat History"):
        history = chat_engine.get_history()
        for turn in history:
            st.markdown(f"**You:** {turn['user']}")
            st.markdown(f"**Assistant:** {turn['assistant']}")

elif st.session_state.active_section == "Chat":
    st.markdown("#### 💬 Document Chat")
    if "pending_chat_input" in st.session_state:
        st.session_state["chat_input"] = st.session_state["pending_chat_input"]
        del st.session_state["pending_chat_input"]

    with st.container():
        user_input = st.text_input("Type your message:", key="chat_input")
        if st.button("Send", key="send_chat") and user_input.strip():
            response = chat_engine.chat(user_input)
            st.session_state.chat_history.append({"user": user_input, "assistant": response})
            if user_input not in st.session_state.search_history_chat:
                st.session_state.search_history_chat.append(user_input)
            st.session_state["pending_chat_input"] = ""
            st.rerun()

    # Display chat history in a card-like style
    st.markdown("#### 🗂️ Conversation History")
    for turn in st.session_state.chat_history:
        with st.container():
            st.markdown(
                f"<div class='custom-chat'>"
                f"<b class='custom-header'>You:</b> {turn['user']}<br>"
                f"<b class='custom-sub'>Assistant:</b> {turn['assistant']}"
                f"</div>",
                unsafe_allow_html=True
            )

st.markdown("<br>", unsafe_allow_html=True)
st.info("All processing is done locally. No data leaves your machine.")
