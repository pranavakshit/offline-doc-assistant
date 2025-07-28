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
    # --- Modern UI CSS inspired by the provided website, but only for real app features ---
    st.markdown(
        '''
        <style>
            body, .stApp {
                background: linear-gradient(90deg, #bfc9ec 0%, #f7fbff 100%) !important;
            }
            .hero-bg {
                min-height: 420px;
                display: flex;
                align-items: center;
                justify-content: flex-start;
                position: relative;
                margin-bottom: 2rem;
            }
            .hero-overlay {
                background: rgba(255,255,255,0.0);
                padding: 2.5rem 2.5rem 2rem 2.5rem;
                border-radius: 8px;
                max-width: 700px;
                box-shadow: none;
                margin-left: 3vw;
            }
            .hero-title {
                font-size: 3.2rem;
                font-weight: 700;
                color: #fff;
                margin-bottom: 0.5rem;
                letter-spacing: -1px;
                font-family: 'Georgia', serif;
                text-shadow: 0 2px 8px rgba(0,0,0,0.12);
            }
            .hero-desc {
                font-size: 1.5rem;
                color: #fff;
                margin-bottom: 1.5rem;
                text-shadow: 0 2px 8px rgba(0,0,0,0.10);
            }
            .custom-header { color: #1d3557 !important; font-size: 1.7rem; font-weight: 700; letter-spacing: -1px; }
            .custom-sub { color: #457b9d !important; font-size: 1.1rem; }
            .custom-card { background: #fff; border-radius: 10px; padding: 16px; margin-bottom: 10px; color: #22223b !important; box-shadow: 0 2px 12px 0 rgba(0,0,0,0.04); }
            .custom-chat { background: #e2eeff; border-radius: 10px; padding: 12px; margin-bottom: 8px; color: #22223b !important; }
            .stButton>button { color: #fff !important; background-color: #ff8200 !important; border: none !important; font-weight: 600; border-radius: 4px !important; padding: 0.5rem 1.2rem !important; }
            .stButton>button:hover { background-color: #e76f00 !important; color: #fff !important; }
            .stTextInput>div>div>input, .stTextArea>div>textarea, .stSelectbox>div>div>div>div { background-color: #fff !important; color: #22223b !important; border-radius: 4px !important; }
            .stCaption, .stSidebar .stCaption { color: #1d3557 !important; }
            .stAlert, .stAlert p, .stAlert span, .stAlert div { color: #22223b !important; }
            textarea, .stTextArea textarea { color: #22223b !important; background-color: #fff !important; }
        </style>
        ''', unsafe_allow_html=True)

# --- Modern Hero Section (inspired by the image, but only for real app) ---
def hero_section():
    import base64, os
    img_path = os.path.join(os.path.dirname(__file__), 'ConverSeek.png')
    img_base64 = ""
    try:
        with open(img_path, "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode()
    except Exception:
        img_base64 = ""
    hero_bg_style = f"background: url('data:image/png;base64,{img_base64}') center center/cover no-repeat; min-height: 420px; width: 100%;" if img_base64 else "background: linear-gradient(90deg, #bfc9ec 0%, #f7fbff 100%); min-height: 420px; width: 100%;"
    st.markdown(
        f'''
        <div class="hero-bg" style="{hero_bg_style}"></div>
        ''', unsafe_allow_html=True)

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

# --- Modern Hero Section ---
hero_section()

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
