import json
import os
import asyncio
import subprocess
import re

from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies.termination.termination_strategy import TerminationStrategy
from semantic_kernel.agents.strategies.selection.kernel_function_selection_strategy import (
    KernelFunctionSelectionStrategy,
)
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.kernel import Kernel
from dotenv import load_dotenv 
import logging
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.functions import KernelFunctionFromPrompt
from semantic_kernel.contents.chat_history import ChatHistory

# <env_var>
load_dotenv()

deployment_name = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
api_version = os.getenv("AZURE_OPENAI_API_VERSION")

# </env_var>

class ApprovalTerminationStrategy(TerminationStrategy):
    """A strategy for determining when an agent should terminate."""
 
    async def should_agent_terminate(self, agent, history):
        """Check if the agent should terminate."""
        for message in reversed(history):
            role = getattr(message, "role", None) or getattr(message, "name", None)
            if role and role == AuthorRole.USER:
                if hasattr(message, 'content') and message.content:
                    if "APPROVED" in message.content.upper():
                        await self._extract_and_save_html(history)
                        await self._push_to_github()
                        return True
        return False

    async def _extract_and_save_html(self, history):
        """Extract HTML code from SWE agent and save to index.html"""
        html_content = ""

        for message in reversed(history):
            name = getattr(message, "name", None)
            if name == "SoftwareEngineerAgent":
                if hasattr(message, 'content') and message.content:
                    html = re.findall(r'```html(.*?)```', message.content, re.DOTALL | re.IGNORECASE)
                    if html:
                        html_content = html[-1].strip()
                        break

        if html_content:
            with open('index.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
                logging.warning("Saved index.html")
        else:
            logging.warning("Didnot save index.html")

    async def _push_to_github(self):
        """Execute the push_to_github.sh script"""
        try:
            # Make sure the script is executable
            subprocess.run(
                ["C:\\Program Files\\Git\\bin\\bash.exe", "push_to_github.sh"],
                check=True
            )

            #result = subprocess.run(['bash', './push_to_github.sh'], check=True, capture_output=True, text=True)
            
            logging.warning("Successfully pushed to GitHub:")
            logging.warning(result.stdout)
            
        except subprocess.CalledProcessError as e:
            logging.warning(f"Error pushing to GitHub: {e}")
            logging.warning(f"Error output: {e.stderr}")
        except Exception as e:
            logging.warning(f"Unexpected error during GitHub push: {e}")

async def run_multi_agent(input: str):
    """Implement the multi-agent system."""

    # Init Semantic Kernel
    kernel = Kernel()

    # Add service - Azure OpenAI
    service_id = "chat-service"
    kernel.add_service(
        AzureChatCompletion(
            service_id=service_id,
            deployment_name=deployment_name,
            endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
    )

    # [settings] = kernel.get_prompt_execution_settings_from_service_id(service_id=service_id)
    settings = AzureChatPromptExecutionSettings()
    settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    # <Agents_creation>

    # 1. Business Analyst Persona
    business_analyst_agent = ChatCompletionAgent(
            kernel=kernel,
            name="BusinessAnalystAgent",
            instructions="You are a Business Analyst which will take the requirements from the user (also known as a 'customer') and create a project plan for creating the requested app. The Business Analyst understands the user requirements and creates detailed documents with requirements and costing. The documents should be usable by the SoftwareEngineer as a reference for implementing the required features, and by the Product Owner for reference to determine if the application delivered by the Software Engineer meets all of the user's requirements.",
    )

    # 2. Software Engineer Persona
    software_engineer_agent = ChatCompletionAgent(
            kernel=kernel,
            name="SoftwareEngineerAgent",
            instructions="You are a Software Engineer, and your goal is create a web app using HTML and JavaScript by taking into consideration all the requirements given by the Business Analyst. The application should implement all the requested features. Deliver the code to the Product Owner for review when completed. You can also ask questions of the BusinessAnalyst to clarify any requirements that are unclear.",
    )

    # 3. Product Owner Persona
    product_owner_agent = ChatCompletionAgent(
            kernel=kernel,
            name="ProductOwnerAgent",
            instructions="You are the Product Owner which will review the software engineer's code to ensure all user  requirements are completed. You are the guardian of quality, ensuring the final product meets all specifications. IMPORTANT: Verify that the Software Engineer has shared the HTML code using the format ```html [code] ```. This format is required for the code to be saved and pushed to GitHub. Once all client requirements are completed and the code is properly formatted, reply with 'READY FOR USER APPROVAL'. If there are missing features or formatting issues, you will need to send a request back to the SoftwareEngineer or BusinessAnalyst with details of the defect.",
    )

    # </Agents_creation>

    # <Agent_Group_Chat>

    termination_strategy = ApprovalTerminationStrategy(agents=[product_owner_agent], maximum_iterations=20)

    agents = [business_analyst_agent, software_engineer_agent, product_owner_agent]

    # ExecutionSettings with a TerminationStrategy set to an instance of ApprovalTerminationStrategy
    # history = ChatHistory()

    chat = AgentGroupChat(
        agents=agents,
        termination_strategy=termination_strategy,
    )
    # </Agent_Group_Chat>


    # Res
    await chat.add_chat_message(
        ChatMessageContent(
            role=AuthorRole.USER,
            content=input
        )
    )
    responses = []

    async for content in chat.invoke():
        #logging.warning(f"# {content.role} - {content.name or '*'}: '{content.content}'")
        responses.append(content)

    # Convert ChatMessageContent objects to dicts for Streamlit app
    messages = []
    for msg in responses:
        # Try to get the role
        role = getattr(msg, "name", None) or getattr(msg, "role", "assistant")
        content = getattr(msg, "inner_content", None)

        # If inner_content is a ChatCompletion, extract its message content
        if content and hasattr(content, "choices"):
            # Try to get the first choice's message content
            try:
                content = content.choices[0].message.content
            except Exception:
                content = str(content)

        # Fallback to .content if .inner_content is not present or not a string
        if not content and hasattr(msg, "content"):
            content = msg.content
        # If still not found, try to get text from items
        if not content and hasattr(msg, "items") and msg.items:
            content = getattr(msg.items[0], "text", None)
        # Fallback to string representation
        if not content:
            content = str(msg)
        messages.append({
            "role": role,
            "content": content
        })


    return {"messages": messages}

async def main():
    logging.warning("Start multi-agent system...")

    try:
        responses = await run_multi_agent("Create a contact form with fields for name, email, and a message box. Include a submit button that says 'Send Message'. APPROVED")
    except Exception as e:
        logging.warning(f"Error at line 108: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())