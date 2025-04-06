# agent.py

from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import os
from typing import List, Dict
from whatsapp_tool import WhatsAppTool  # Import the WhatsAppTool

# Load environment variables
load_dotenv()

# Initialize Gemini Pro
llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro-exp-03-25", api_key=os.getenv("GOOGLE_API_KEY"))

class OrderManagementAgent:
    def __init__(self, mcp_server_url: str):
        self.whatsapp_tool = WhatsAppTool(mcp_server_url)
        self.tools = self._create_tools()
        self.agent = self._create_agent()
        self.agent_executor = AgentExecutor.from_agent_and_tools(
            agent=self.agent,
            tools=self.tools,
            verbose=True
        )

    def _create_tools(self) -> List[Tool]:
        tools = [
            Tool(
                name="database_query",
                func=self._query_database,
                description="Use this tool to query the PostgreSQL database for order information."
            ),
            Tool(
                name="generate_report",
                func=self._generate_pdf_report,
                description="Use this tool to generate PDF reports from order data."
            ),
            Tool(
                name="send_whatsapp_message",
                func=self.whatsapp_tool.send_message,
                description="Use this tool to send messages via WhatsApp."
            ),
            Tool(
                name="send_whatsapp_file",
                func=self.whatsapp_tool.send_file,
                description="Use this tool to send files via WhatsApp."
            )
        ]
        return tools

    def _create_agent(self):
        prompt = PromptTemplate.from_template(
            """You are an order management assistant that helps users get information about orders.
            You can query the database, generate reports, and send WhatsApp messages.

            To accomplish your tasks, you have access to the following tools:
            {tools}

            Use these tools to help answer the user's question: {input}

            Take these steps:
            1. Understand the user's request.
            2. Query the necessary data.
            3. Generate reports if needed.
            4. Send the information via WhatsApp.

            Remember to handle errors gracefully and provide clear feedback to the user."""
        )
        return create_react_agent(llm, self.tools, prompt)

    def _query_database(self, query: str) -> Dict:
        # Implementation for querying the PostgreSQL database
        pass

    def _generate_pdf_report(self, data: Dict) -> str:
        # Implementation for generating PDF reports
        pass

    def run(self, user_input: str):
        return self.agent_executor.run(user_input)

if __name__ == "__main__":
    mcp_server_url = "http://localhost:8080"  # Replace with your actual MCP server URL
    agent = OrderManagementAgent(mcp_server_url)
    # Example usage
    # result = agent.run("Give me a report of all delayed orders.")
