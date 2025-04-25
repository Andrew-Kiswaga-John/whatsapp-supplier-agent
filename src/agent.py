import asyncio
import os
import json
import requests
import time
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

async def query_database(state: AgentState) -> AgentState:
    """Process the database query using the PostgreSQL agent."""
    query = state["input"]
    errors = []
    db_results = ""
    
    try: 
        # Reset tracker for each new query
        db_session.reset_tracker()      

        # Create the database agent
        db_agent = await create_db_agent()
        
        # Execute the query using the agent
        result = await db_agent.ainvoke({"input": query})
        
        # Extract the response
        db_results = result.get("output", "")
        # Add heading with bold text (WhatsApp supports markdown-like formatting)
        response = "*Response From Angela*\n\n" + db_results
        
    except Exception as e:
        error_msg = f"Error processing database query: {str(e)}"
        errors.append(error_msg)
        db_results = error_msg
        # Add heading with bold text even for error messages
        response = f"*Response From Angela*\n\nSorry, I encountered an error while processing your query: {error_msg}"
    
    # Update state with query results
    return {
        **state,
        "db_results": db_results,
        "response": response,
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
    
    # Add the START edge
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

# Send introduction message
def send_introduction(phone_number: str) -> None:
    """Send an introduction message when the user says 'Hello Angela'."""
    introduction = (
        "*Response From Angela*\n\n"
        "Hello! I'm Angela, your database assistant. I can help you query the database "
        "and provide information and insights from it.\n\n"
        "Just ask me any question about the database, and I'll do my best to answer it.\n\n"
        "When you're done, just say 'Bye Angela' to end our conversation."
    )
    
    send_whatsapp_message({
        "recipient": phone_number,
        "message": introduction
    })

# Send goodbye message
def send_goodbye(phone_number: str) -> None:
    """Send a goodbye message when the user says 'Bye Angela'."""
    goodbye = (
        "*Response From Angela*\n\n"
        "Thank you for using my services! If you need database assistance again, "
        "just say 'Hello Angela' and I'll be ready to help.\n\n"
        "Have a great day!"
    )
    
    send_whatsapp_message({
        "recipient": phone_number,
        "message": goodbye
    })

# Listen for messages and handle conversation flow
async def listen_for_messages(phone_number: str) -> None:
    """Listen for messages from a specific phone number and handle the conversation flow."""
    print(f"Starting to listen for messages from {phone_number}...")
    
    # Track conversation state
    active_conversation = False
    last_message_time = None
    
    # Record the time when the agent starts
    agent_start_time = time.time()
    print(f"Agent started at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(agent_start_time))}")
    
    # Flag to indicate if we've seen the keep-alive message
    seen_keep_alive = False
    
    # Flag to indicate if we're currently processing a message
    processing_message = False
    
    try:
        # Set up a persistent connection to the endpoint
        print(f"Establishing persistent connection to: http://localhost:8000/api/listen?phone={phone_number}")
        
        # Using requests.get with stream=True for a persistent connection
        with requests.get(f"http://localhost:8000/api/listen?phone={phone_number}", stream=True) as response:
            print(f"Connection established with status code: {response.status_code}")
            
            if response.status_code == 200:
                # Process the streaming response
                for line in response.iter_lines():
                    # Skip processing if we're currently handling a message
                    if processing_message:
                        print("Skipping incoming data - currently processing a message")
                        continue
                        
                    if line:
                        try:
                            # Decode the line and parse as JSON
                            line_text = line.decode('utf-8')
                            print(f"Received data stream: {line_text}")
                            
                            # Check for keep-alive message
                            if ": keep-alive" in line_text:
                                print("Detected keep-alive message, now processing new messages only")
                                seen_keep_alive = True
                                continue
                            
                            # Skip processing until we've seen the keep-alive message
                            if not seen_keep_alive:
                                print("Skipping message - waiting for keep-alive signal")
                                continue
                            
                            # Check if the line starts with "data: " (common in SSE)
                            if line_text.startswith('data: '):
                                line_text = line_text[6:]  # Remove the "data: " prefix
                            
                            # Parse the JSON data
                            data = json.loads(line_text)
                            print(f"Parsed JSON data: {data}")
                            
                            # Check if there's a message in the expected format
                            if "Time" in data and "Sender" in data and "Content" in data:
                                # Get the message details
                                message_time = data["Time"]
                                sender = data["Sender"]
                                message_text = data["Content"]
                                
                                # Try to parse the message time
                                try:
                                    # Parse ISO format time string to timestamp
                                    message_datetime = time.strptime(message_time, "%Y-%m-%dT%H:%M:%S%z")
                                    message_timestamp = time.mktime(message_datetime)
                                    
                                    # Skip messages that were sent before the agent started
                                    if message_timestamp < agent_start_time:
                                        print(f"Skipping message - sent before agent started (message time: {message_time})")
                                        continue
                                except (ValueError, TypeError) as e:
                                    # If we can't parse the time, just continue with processing
                                    print(f"Warning: Could not parse message time: {message_time}, error: {e}")
                                
                                print(f"Message details - Time: {message_time}, Sender: {sender}, Content: {message_text}")
                                
                                # Skip if we've already processed this message
                                if last_message_time == message_time:
                                    print(f"Skipping message - already processed (last_message_time: {last_message_time})")
                                    continue
                                
                                # Update last message time
                                print(f"Updating last_message_time from {last_message_time} to {message_time}")
                                last_message_time = message_time
                                
                                # Skip messages that are responses from Angela
                                if message_text.startswith("*Response From Angela*"):
                                    print(f"Skipping message - starts with 'Response From Angela'")
                                    continue
                                
                                # Check for trigger words
                                if message_text.strip().lower() == "hello angela":
                                    print(f"Trigger word detected from {sender}")
                                    active_conversation = True
                                    print(f"Setting active_conversation to {active_conversation}")
                                    print(f"Sending introduction message to {sender}")
                                    send_introduction(sender)
                                
                                elif message_text.strip().lower() == "bye angela":
                                    print(f"End conversation trigger detected from {sender}")
                                    active_conversation = False
                                    print(f"Setting active_conversation to {active_conversation}")
                                    print(f"Sending goodbye message to {sender}")
                                    send_goodbye(sender)
                                
                                # Process database query if conversation is active
                                elif active_conversation:
                                    print(f"Processing query from {sender}: {message_text}")
                                    print(f"Calling handle_whatsapp_message with message: {message_text}, sender: {sender}")
                                    
                                    # Set the processing flag to true to pause listening
                                    processing_message = True
                                    print("Pausing message listening while processing query...")
                                    
                                    try:
                                        # Process the message synchronously (wait for it to complete)
                                        result = await handle_whatsapp_message(message_text, sender)
                                        print(f"Query processing completed: {result}")
                                    except Exception as e:
                                        print(f"Error processing query: {str(e)}")
                                    finally:
                                        # Resume listening regardless of success or failure
                                        processing_message = False
                                        print("Resuming message listening...")
                                else:
                                    print(f"Ignoring message - conversation not active (active_conversation: {active_conversation})")
                            else:
                                print(f"Message format not recognized. Expected 'Time', 'Sender', and 'Content' fields.")
                                print(f"Available fields: {list(data.keys())}")
                        except json.JSONDecodeError as json_err:
                            print(f"Error decoding JSON from stream: {json_err}")
                            print(f"Raw line content: {line_text if 'line_text' in locals() else line}")
                        except Exception as e:
                            print(f"Error processing message: {str(e)}")
                            import traceback
                            print(f"Traceback: {traceback.format_exc()}")
            else:
                print(f"Error response from API: {response.status_code} - {response.text}")
    
    except Exception as e:
        print(f"Connection error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        print("Attempting to reconnect in 5 seconds...")
        await asyncio.sleep(5)
        # Recursively call the function to reconnect
        await listen_for_messages(phone_number)

# Main function
async def main():
    # Phone number to listen for
    phone_number = os.getenv("PHONE_NUMBER")
    
    # Start listening for messages
    await listen_for_messages(phone_number)

if __name__ == "__main__":
    asyncio.run(main())