import asyncio
import os
import requests
from langchain.agents import AgentExecutor, create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

def send_whatsapp_message(args):
    """Send a WhatsApp message via REST API."""
    try:
        # Handle both string and dictionary inputs
        if isinstance(args, str):
            # Check if the input is wrapped in markdown code blocks with ```json
            if args.strip().startswith('```json') and args.strip().endswith('```'):
                # Extract the JSON content between the backticks
                json_content = args.strip().replace('```json', '', 1)
                json_content = json_content.rsplit('```', 1)[0].strip()
                try:
                    args = json.loads(json_content)
                except json.JSONDecodeError:
                    return {"success": False, "message": "Invalid JSON format in code block"}
            else:
                # Try to parse as regular JSON string
                try:                
                    args = json.loads(args)
                except json.JSONDecodeError:
                    return {"success": False, "message": "Invalid JSON input"}
        
        # Extract recipient and message from args
        recipient = args.get("recipient")
        message = args.get("message")
        
        if not recipient or not message:
            return {"success": False, "message": "Both recipient and message are required"}
        
        # Send POST request to the WhatsApp API
        response = requests.post(
            "http://localhost:8000/api/send",
            json={"recipient": recipient, "message": message}
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            return {"success": True, "message": f"Message sent to {recipient}"}
        else:
            return {"success": False, "message": f"Failed to send message: {response.text}"}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

async def setup_tools():
    # Create a custom tool for sending WhatsApp messages
    send_message_tool = Tool(
        name="send_message",
        func=send_whatsapp_message,
        description="""Send a WhatsApp message to a person or group.
        Args:
            recipient: The recipient - either a phone number with country code but no + or other symbols,
                     or a JID (e.g., "123456789@s.whatsapp.net" or a group JID like "123456789@g.us")
            message: The message text to send
        """,
    )
    
    return [send_message_tool]

async def main():
    # Initialize the language model
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=os.getenv("GEMINI_API_KEY"))

    # Get tools
    tools = await setup_tools()

    # Create prompt template
    prompt = PromptTemplate.from_template(
        """You are a WhatsApp messaging assistant that helps users send messages.
        
        To accomplish your tasks, you have access to the following tools:
        {tools}
        
        Use the following format:
        Question: the input question you must answer
        Thought: you should always think about what to do
        Action: the action to take, should be one of [{tool_names}]
        Action Input: the input must be a valid JSON object with the required parameters
        Observation: the result of the action
        Thought: If the message was sent successfully, proceed to Final Answer. If not, try to fix the error.
        Final Answer: Confirm whether the message was sent successfully or explain why it failed.
        
        Remember: 
        - When using send_message, format the Action Input as a JSON object with "recipient" and "message" fields
        - Stop after a successful message send or if an error cannot be resolved
        
        Begin!
        
        Question: {input}
        Thought:{agent_scratchpad}"""
    )

    # Create the agent with the tools and prompt
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=3)

    # Run the agent
    response = await agent_executor.ainvoke({"input": "Tell 212600311326 the weather is hot today"})
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
