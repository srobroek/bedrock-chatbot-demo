import os

import boto3
import streamlit as st
import uuid
import time
import logging
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

bedrock_agent_runtime = boto3.client('bedrock-agent-runtime',  region_name=os.environ.get('AWS_REGION', 'us-east-1'))
# Initialize session state for session ID if it doesn't exist
if "session_id" not in st.session_state:
    # Generate a unique session ID combining timestamp and UUID
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    st.session_state.session_id = f"{timestamp}-{unique_id}"

    # Log when a new session is created
    logger.info(
        "New session created",
        extra={
            "session_id": st.session_state.session_id,
            "timestamp": datetime.now().isoformat()
        }
    )

# Your existing session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = []

def invoke_agent(prompt: str) -> str:
    """
    Invoke the Bedrock agent with the given prompt
    """
    try:
        logger.info(
            "Invoking Bedrock agent",
            extra={
                "session_id": st.session_state.session_id,
                "prompt_length": len(prompt)
            }
        )

        response = bedrock_agent_runtime.invoke_agent(
            agentId=os.environ['BEDROCK_AGENT_ID'],
            agentAliasId=os.environ['BEDROCK_AGENT_ALIAS_ID'],
            sessionId=st.session_state.session_id,  # Use the persistent session ID
            inputText=prompt
        )

        # Process response...
        completion = ""
        if 'completion' in response:
            for event in response['completion']:
                chunk = event['chunk']['bytes'].decode('utf-8')
                if chunk:
                    completion += chunk



        logger.info(
            "Agent response received",
            extra={
                "session_id": st.session_state.session_id,
                "response_length": len(completion)
            }
        )

        return completion

    except Exception as e:
        logger.error(
            "Error in agent invocation",
            extra={
                "session_id": st.session_state.session_id,
                "error": str(e)
            }
        )
        st.error(f"Error invoking Bedrock agent: {str(e)}")
        return "I encountered an error processing your request."

# Optional: Display session information in a sidebar or expander
with st.expander("Session Information", expanded=False):
    st.text(f"Session ID: {st.session_state.session_id}")


with st.expander("User Data to use in demos", expanded=False):
    st.text(f"User ID 1: bb0884d7-4d61-46bb-850f-493fa45e1080 - john.doe@example.com")
    st.text(f"User ID 2: 434d928d-328a-422c-b6e9-9d888acbf698 - bob@amazon.com")



# Your existing Streamlit UI code
st.title("ISP Helpdesk Assistant Demo")
st.markdown("Welcome to the ISP Helpdesk Assistant Demo. Try asking me to fix your problems, or ask me if you can help me with my tickets")

# Chat interface
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("How can I help you?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get and display assistant response
    with st.chat_message("assistant"):
        response = invoke_agent(prompt)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.markdown(response)
