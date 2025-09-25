import streamlit as st
import random
import time

from agent import orchestrator
from agents import Runner
import asyncio

from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        
st.title("Simple chat")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("What is up?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
        
    main_agent = asyncio.run(Runner.run(orchestrator, prompt))
    ai_reply = main_agent.final_output

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        response = st.write(ai_reply)
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "agent", "content": response})
