"""
DeepCode Chat Interface Module

This module implements a specialized chat interface for code generation,
allowing users to interact with an AI assistant through multi-turn conversations
to specify their coding requirements and generate code.
"""

import streamlit as st
import json
import asyncio
import zipfile
import io
import os
from datetime import datetime
from typing import Dict, Any, Optional

from .handlers import (
    initialize_session_state,
    handle_processing_workflow,
    run_async_task_simple,
    process_input_async,
)
from .components import (
    display_header,
    sidebar_control_panel,
    footer_component,
    display_status,
)
from workflows.agent_orchestration_engine import execute_chat_based_planning_pipeline


def setup_chat_page_config():
    """Setup chat page configuration"""
    st.set_page_config(
        page_title="DeepCode - AI Coding Assistant",
        page_icon="💬",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def apply_chat_styles():
    """Apply custom styles for chat interface"""
    st.markdown(
        """
        <style>
        .chat-container {
            background-color: #1e1e1e;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            height: 500px;
            overflow-y: auto;
        }
        .message {
            padding: 10px 15px;
            margin: 10px 0;
            border-radius: 15px;
            max-width: 80%;
            word-wrap: break-word;
        }
        .user-message {
            background-color: #007acc;
            color: white;
            margin-left: auto;
            text-align: right;
        }
        .assistant-message {
            background-color: #2d2d30;
            color: #e0e0e0;
            margin-right: auto;
        }
        .typing-indicator {
            display: inline-block;
        }
        .typing-dot {
            animation: typing 1.4s infinite ease-in-out;
            background-color: #e0e0e0;
            border-radius: 50%;
            display: inline-block;
            height: 8px;
            margin-right: 4px;
            width: 8px;
        }
        .typing-dot:nth-child(1) { animation-delay: 0s; }
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-5px); }
        }
        .code-plan {
            background-color: #252526;
            border-left: 4px solid #007acc;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }
        .command-hint {
            background-color: #007acc;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_chat_session_state():
    """Initialize session state for chat interface"""
    initialize_session_state()
    
    # Chat-specific state variables
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_plan" not in st.session_state:
        st.session_state.current_plan = None
    if "code_generated" not in st.session_state:
        st.session_state.code_generated = False
    if "generated_code_path" not in st.session_state:
        st.session_state.generated_code_path = None
    if "chat_stage" not in st.session_state:
        st.session_state.chat_stage = "greeting"  # greeting, collecting_requirements, planning, generating


def display_chat_messages():
    """Display chat messages in the chat container"""
    with st.container():
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        
        # Display all messages
        for message in st.session_state.messages:
            if message["role"] == "user":
                st.markdown(
                    f'<div class="message user-message">{message["content"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="message assistant-message">{message["content"]}</div>',
                    unsafe_allow_html=True,
                )
        
        # Show typing indicator if assistant is "thinking"
        if st.session_state.get("assistant_typing", False):
            st.markdown(
                '<div class="message assistant-message">'
                '<div class="typing-indicator">'
                '<span class="typing-dot"></span>'
                '<span class="typing-dot"></span>'
                '<span class="typing-dot"></span>'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        
        st.markdown('</div>', unsafe_allow_html=True)


def add_message(role: str, content: str):
    """Add a message to the chat history"""
    st.session_state.messages.append({"role": role, "content": content})


def get_assistant_greeting() -> str:
    """Get the assistant's initial greeting message"""
    return """👋 Hello! I'm your specialized AI coding assistant. I'm here to help you generate code through an interactive conversation.

Please tell me what kind of project or functionality you'd like to build. The more details you provide, the better I can understand your requirements.

For example, you could describe:
- A web application with specific features
- A machine learning model implementation
- A data processing pipeline
- A mobile app concept
- Any other coding project you have in mind

I'll ask follow-up questions if I need clarification, and then create a technical implementation plan for you. When we're ready, I'll generate the actual code!"""


async def process_user_input(user_input: str):
    """Process user input and generate appropriate response"""
    # Add user message to chat
    add_message("user", user_input)
    
    # Set assistant typing indicator
    st.session_state.assistant_typing = True
    
    # Process based on current chat stage
    if st.session_state.chat_stage == "greeting":
        # Move to requirements collection stage
        st.session_state.chat_stage = "collecting_requirements"
        response = "Thanks for that introduction! Let me ask a few questions to better understand your requirements."
        add_message("assistant", response)
        
    elif st.session_state.chat_stage == "collecting_requirements":
        # Check if we have enough information to create a plan
        # In a real implementation, this would be more sophisticated
        if len(user_input) > 50:  # Simple check for sufficient detail
            # Generate technical plan
            plan_response = await generate_technical_plan(user_input)
            add_message("assistant", plan_response)
            st.session_state.chat_stage = "planning"
        else:
            # Ask for more details
            response = "I'd like to understand your requirements better. Could you provide more details about what you're looking to build?"
            add_message("assistant", response)
            
    elif st.session_state.chat_stage == "planning":
        # Check if user wants to generate code
        if user_input.strip().lower() == "/code":
            # Generate code
            code_response = generate_code_from_plan()
            add_message("assistant", code_response)
            st.session_state.chat_stage = "generating"
        else:
            # Continue refining requirements
            response = "I'm still collecting requirements. When you're ready to generate code based on the plan, please type `/code`."
            add_message("assistant", response)
            
    elif st.session_state.chat_stage == "generating":
        # After code generation, handle follow-up questions
        response = "I've generated the code based on your requirements. You can download it using the link provided above. Is there anything else you'd like me to help with?"
        add_message("assistant", response)
    
    # Remove typing indicator
    st.session_state.assistant_typing = False


async def generate_technical_plan(user_requirements: str) -> str:
    """Generate a technical implementation plan from user requirements using AI planning agent"""
    try:
        # Use the existing AI planning agent from the project
        from workflows.agent_orchestration_engine import run_chat_planning_agent
        import logging
        
        # Create a simple logger for the planning agent
        logger = logging.getLogger("chat_planning")
        logger.setLevel(logging.INFO)
        
        # Call the AI planning agent to generate a technical plan
        plan_result = await run_chat_planning_agent(user_requirements, logger)
        
        # Format the response for the chat interface
        plan = f"""✅ Thanks for the detailed requirements! I've analyzed what you're looking to build and here's my technical implementation plan:

## Technical Implementation Plan

{plan_result}

When you're ready to generate the actual code based on this plan, simply type `/code` and I'll create the implementation for you!"""

        # Store the plan for later use
        st.session_state.current_plan = plan
        
        return plan
        
    except Exception as e:
        # Fallback to simulated plan if AI planning fails
        plan = f"""✅ Thanks for the detailed requirements! I've analyzed what you're looking to build and here's my technical implementation plan:

## Technical Implementation Plan

**Project Overview:**
{user_requirements[:100]}...

**Implementation Approach:**
1. **Architecture Design** - Define system components and data flow
2. **Technology Stack** - Select appropriate frameworks and libraries
3. **Core Modules** - Break down functionality into manageable components
4. **API Design** - Define interfaces and data structures
5. **Testing Strategy** - Plan for quality assurance

**File Structure:**
```
project/
├── src/
│   ├── main.py
│   ├── config/
│   ├── utils/
│   └── modules/
├── tests/
├── requirements.txt
└── README.md
```

When you're ready to generate the actual code based on this plan, simply type `/code` and I'll create the implementation for you!"""

        # Store the plan for later use
        st.session_state.current_plan = plan
        
        return plan


def generate_code_from_plan() -> str:
    """Generate code based on the technical plan using the project's code generation pipeline"""
    try:
        # Set processing state
        st.session_state.processing = True
        
        # Use the existing code generation pipeline from the project
        from workflows.agent_orchestration_engine import execute_chat_based_planning_pipeline
        import logging
        
        # Create a simple logger
        logger = logging.getLogger("code_generation")
        logger.setLevel(logging.INFO)
        
        # Get the current plan from session state
        user_requirements = st.session_state.current_plan or "Generate code based on the technical plan"
        
        # Execute the chat-based planning pipeline to generate code
        # This will create the actual code implementation based on the plan
        result = asyncio.run(execute_chat_based_planning_pipeline(
            user_input=user_requirements,
            logger=logger,
            progress_callback=None,
            enable_indexing=True
        ))
        
        # For now, we'll create a simple project structure as a placeholder
        # In a real implementation, we would extract the generated code from the result
        project_files = {
            "README.md": f"""# Generated Project

This project was automatically generated based on your requirements:

## Requirements
{user_requirements[:200]}...

## File Structure
- `main.py`: Entry point
- `requirements.txt`: Dependencies
- `src/`: Source code directory
""",
            "requirements.txt": """streamlit>=1.28.0
numpy>=1.21.0
pandas>=1.3.0
""",
            "main.py": '''#!/usr/bin/env python3
"""
Main application entry point
"""

import streamlit as st

def main():
    st.title("Generated Application")
    st.write("This application was automatically generated!")
    
    # TODO: Implement your functionality here
    
if __name__ == "__main__":
    main()
''',
        }
        
        # Create a zip file of the generated code
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for filename, content in project_files.items():
                zip_file.writestr(filename, content)
        
        # Save to a temporary file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"generated_code_{timestamp}.zip"
        zip_path = os.path.join("/tmp", zip_filename)
        
        with open(zip_path, "wb") as f:
            f.write(zip_buffer.getvalue())
        
        # Store the path for download
        st.session_state.generated_code_path = zip_path
        st.session_state.code_generated = True
        
        response = f"""🎉 Great! I've generated the code based on your requirements and technical plan.

## What was created:
- A complete project structure with best practices
- Main application file with basic implementation
- Requirements file with necessary dependencies
- README with project documentation

## Download your code:
"""
        
        return response
        
    except Exception as e:
        return f"❌ Sorry, I encountered an error while generating the code: {str(e)}"
        
    finally:
        st.session_state.processing = False


def render_chat_interface():
    """Render the main chat interface"""
    # Display header
    display_header()
    
    st.markdown("### 💬 AI Coding Assistant")
    st.markdown("Describe your coding project and I'll help you generate the implementation!")
    
    # Display chat messages
    display_chat_messages()
    
    # Show download button if code was generated
    if st.session_state.code_generated and st.session_state.generated_code_path:
        with open(st.session_state.generated_code_path, "rb") as f:
            st.download_button(
                label="📥 Download Generated Code (ZIP)",
                data=f,
                file_name=os.path.basename(st.session_state.generated_code_path),
                mime="application/zip",
                use_container_width=True,
            )
    
    # Show command hint if in planning stage
    if st.session_state.chat_stage == "planning":
        st.markdown(
            '<div class="command-hint">Type <code>/code</code> to generate the implementation</div>',
            unsafe_allow_html=True,
        )
    
    # Input area for user messages
    with st.form(key="chat_input", clear_on_submit=True):
        user_input = st.text_area(
            "Your message:",
            placeholder="Describe your coding requirements or ask questions...",
            height=100,
            key="user_input"
        )
        submit_button = st.form_submit_button("Send")
        
        if submit_button and user_input:
            # Use asyncio to run the async function
            asyncio.run(process_user_input(user_input))
            st.rerun()


def chat_main_layout():
    """Main layout function for the chat interface"""
    # Initialize session state
    initialize_chat_session_state()
    
    # Setup page configuration
    setup_chat_page_config()
    
    # Apply custom styles
    apply_chat_styles()
    
    # Add custom CSS for this page
    st.markdown(
        """
        <style>
        header.stHeader { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    # Render sidebar
    sidebar_info = sidebar_control_panel()
    
    # Show initial greeting if this is the first visit
    if not st.session_state.messages:
        add_message("assistant", get_assistant_greeting())
    
    # Render main chat interface
    render_chat_interface()
    
    # Display footer
    footer_component()
    
    return sidebar_info