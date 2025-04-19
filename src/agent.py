import asyncio
import os
import json
from typing import Dict, Any, List, TypedDict, Literal
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END, START
from pydantic import BaseModel

# Import from your existing modules
from postgresql_test import DatabaseSession
from test_whatsapp import send_whatsapp_message
from postgresql_test import create_db_agent

# Load environment variables
load_dotenv()

# Define state schema
class AgentState(TypedDict):
    # The input message from WhatsApp
    input: str
    # The sender's phone number or JID
    sender: str
    # Database query results
    db_results: str
    # Final response to send back
    response: str
    # Any errors that occurred
    errors: List[str]

# Initialize the language model
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=os.getenv("GEMINI_API_KEY"))

# Initialize database session from the PostgreSQL agent
db_session = DatabaseSession()

# Define nodes for the graph
async def parse_whatsapp_input(state: AgentState) -> AgentState:
    """Parse the incoming WhatsApp message to extract the database query."""
    input_message = state["input"]
    
    # You can add more sophisticated parsing here if needed
    query = input_message
    
    # Update state with the parsed query
    return {
        **state,
        "input": query
    }

# Replace the query_database function with this:

async def query_database(state: AgentState) -> AgentState:
    """Process the database query using the PostgreSQL agent."""
    query = state["input"]
    errors = []
    db_results = ""
    
    try:       
        # Create the database agent
        db_agent = await create_db_agent()
        
        # Execute the query using the agent
        result = await db_agent.ainvoke({"input": query})
        
        # Extract the response
        db_results = result.get("output", "")
        response = db_results  # Use the output directly as the response
        
    except Exception as e:
        error_msg = f"Error processing database query: {str(e)}"
        errors.append(error_msg)
        db_results = error_msg
        response = f"Sorry, I encountered an error while processing your query: {error_msg}"
    
    # Update state with query results
    return {
        **state,
        "db_results": db_results,
        "response":response,
        "errors": errors
    }

async def send_response(state: AgentState) -> AgentState:
    """Send the formatted response back to the user via WhatsApp."""
    response = state["response"]
    sender = state["sender"]
    
    # Send the response via WhatsApp using the WhatsApp agent's function
    send_result = send_whatsapp_message({
        "recipient": sender,
        "message": response
    })
    
    # Check if the message was sent successfully
    if not send_result.get("success", False):
        state["errors"].append(f"Failed to send WhatsApp response: {send_result.get('message', 'Unknown error')}")
    
    # Return the final state
    return state

# Create the graph
# Create the graph
def create_workflow() -> StateGraph:
    """Create the LangGraph workflow for the WhatsApp database query system."""
    # Initialize the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("parse_input", parse_whatsapp_input)
    workflow.add_node("query_database", query_database)
    workflow.add_node("send_response", send_response)
    
    # Add edges
    workflow.add_edge("parse_input", "query_database")
    workflow.add_edge("query_database", "send_response")
    workflow.add_edge("send_response", END)
    
    # Add the START edge - this is what's missing
    workflow.add_edge(START, "parse_input")
    
    # Compile the graph
    return workflow.compile()

# Function to handle incoming WhatsApp messages
async def handle_whatsapp_message(message: str, sender: str) -> Dict[str, Any]:
    """Process an incoming WhatsApp message, query the database, and send a response."""
    # Create the initial state
    initial_state: AgentState = {
        "input": message,
        "sender": sender,
        "db_results": "",
        "response": "",
        "errors": []
    }
    
    # Create and run the workflow
    workflow = create_workflow()
    final_state = await workflow.ainvoke(initial_state)
    
    return {
        "success": not final_state.get("errors", []),
        "response": final_state.get("response", ""),
        "errors": final_state.get("errors", [])
    }

# Create a webhook handler for WhatsApp messages
async def process_webhook_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process webhook data from WhatsApp and return a response."""
    try:
        # Extract message and sender information
        if "messages" in data and len(data["messages"]) > 0:
            message = data["messages"][0]
            
            if "text" in message and "body" in message["text"]:
                # Extract the message text
                message_text = message["text"]["body"]
                
                # Extract the sender's phone number
                sender = message["from"]
                
                # Process the message
                result = await handle_whatsapp_message(message_text, sender)
                return {"status": "success", "result": result}
        
        return {"status": "no_message"}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Example usage
async def main():
    # Example message and sender
    message = "Show me all suppliers with delayed orders and give me their emails ?"
    sender = "212600311326"  # Replace with actual sender number
    
    print(f"Processing message: '{message}' from {sender}")
    result = await handle_whatsapp_message(message, sender)
    
    if result["success"]:
        print(f"Successfully processed query and sent response")
    else:
        print(f"Errors occurred: {result['errors']}")

if __name__ == "__main__":
    asyncio.run(main())