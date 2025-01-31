import streamlit as st
import openai
import uuid
import time
import pandas as pd
import io
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()

# Your chosen model
MODEL = "gpt-4-1106-preview"

# Initialize session state variables
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "run" not in st.session_state:
    st.session_state.run = {"status": None}

if "messages" not in st.session_state:
    st.session_state.messages = []

if "retry_error" not in st.session_state:
    st.session_state.retry_error = 0

# Set up the page with UnconstrainED branding
primary_color = "#F28705"  # Orange
secondary_color = "#000000"  # White
st.set_page_config(page_title="UnconstrainED Chat", layout="wide")
st.markdown(f"""
    <style>
    .stApp {{
        background-color: {secondary_color};
    }}
    .st-bv {{
        color: {primary_color};
    }}
    </style>
    """, unsafe_allow_html=True)

# Displaying the UnconstrainED logo
st.sidebar.image("logo.png", width=150)
st.sidebar.link_button("UnconstrainED Website", "https://unconstrained.work")

# Assistant selection
assistant_choice = st.sidebar.selectbox(
    "Choose Your Assistant",
    ["InterVU", "3Ps Prompt Builder", "Educational Media Analyst"],
    index=1  # Default to "3Ps Prompt Builder"
)

# Map assistant names to secret keys
assistant_keys = {
    "InterVU": "InterVU_secret_key",
    "3Ps Prompt Builder": "PromptBuilder_secret_key",
    "Educational Media Analyst": "MediaAnalyst_secret_key"
}

# Set default assistant to "3Ps Prompt Builder"
default_assistant_key = "PromptBuilder_secret_key"
if "assistant" not in st.session_state:
    st.session_state.assistant = openai.beta.assistants.retrieve(st.secrets[default_assistant_key])

# Initialize OpenAI assistant thread
if "thread" not in st.session_state:
    openai.api_key = st.secrets["OPENAI_API_KEY"]
    st.session_state.thread = client.beta.threads.create(
        metadata={'session_id': st.session_state.session_id}
    )

# Update the assistant based on the choice
selected_assistant_key = assistant_keys[assistant_choice]
if selected_assistant_key != default_assistant_key:
    st.session_state.assistant = openai.beta.assistants.retrieve(st.secrets[selected_assistant_key])

# File uploader for CSV, XLS, XLSX, PDF, and Image files
uploaded_file = st.file_uploader("Upload your file", type=["csv", "xls", "xlsx", "pdf", "png", "jpg", "jpeg"])

if uploaded_file is not None:
    # Determine the file type
    file_type = uploaded_file.type

    try:
        # Read the file into a Pandas DataFrame or display PDF/Image
        if file_type in ["text/csv", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
            df = pd.read_csv(uploaded_file) if file_type == "text/csv" else pd.read_excel(uploaded_file)
            json_str = df.to_json(orient='records', indent=4)
            file_stream = io.BytesIO(json_str.encode())
            file_response = client.files.create(file=file_stream, purpose='answers')
            st.session_state.file_id = file_response.id
            st.text_area("JSON Output", json_str, height=300)
            st.download_button(label="Download JSON", data=json_str, file_name="converted.json", mime="application/json")
        elif file_type in ["application/pdf", "image/png", "image/jpeg"]:
            st.image(uploaded_file)
    except Exception as e:
        st.error(f"An error occurred: {e}")

# Display chat messages
if hasattr(st.session_state.run, 'status') and st.session_state.run.status == "completed":
    st.session_state.messages = client.beta.threads.messages.list(
        thread_id=st.session_state.thread.id
    )
    for message in reversed(st.session_state.messages.data):
        if message.role in ["user", "assistant"]:
            with st.chat_message(message.role):
                for content_part in message.content:
                    message_text = content_part.text.value
                    st.markdown(message_text)

# Chat input and message creation with file ID
if prompt := st.chat_input("How can I help you?"):
    with st.chat_message('user'):
        st.write(prompt)

    message_data = {
        "role": "user",
        "content": prompt,
        "thread_id": st.session_state.thread.id
    }

    # Include file ID in the request if available
    if "file_id" in st.session_state:
        message_data["file_ids"] = [st.session_state.file_id]

    st.session_state.messages = client.beta.threads.messages.create(**message_data)

    st.session_state.run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread.id,
        assistant_id=st.session_state.assistant.id,
    )
    if st.session_state.retry_error < 3:
        time.sleep(1)
        st.rerun()

# Handle run status
if hasattr(st.session_state.run, 'status'):
    if st.session_state.run.status == "running":
        with st.chat_message('assistant'):
            st.write("Thinking ......")
        if st.session_state.retry_error < 3:
            time.sleep(1)
            st.rerun()

    elif st.session_state.run.status == "failed":
        st.session_state.retry_error += 1
        with st.chat_message('assistant'):
            if st.session_state.retry_error < 3:
                st.write("Run failed, retrying ......")
                time.sleep(3)
                st.rerun()
            else:
                st.error("FAILED: The OpenAI API is currently processing too many requests. Please try again later ......")

    elif st.session_state.run.status != "completed":
        st.session_state.run = client.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread.id,
            run_id=st.session_state.run.id,
        )
        if st.session_state.retry_error < 3:
            time.sleep(3)
            st.rerun()
