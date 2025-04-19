import asyncio
import os
import subprocess
import json
import time
from langchain.agents import AgentExecutor, create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from dotenv import load_dotenv
import traceback
from typing import Dict, Any

# Load environment variables
load_dotenv()

class QueryAnalyzer:
    def __init__(self):
        self.command_map = {
            "SELECT": "4",  # Query data
            "LIST_TABLES": "5",  # List tables
            "DESCRIBE": "6",  # Describe table
            "CREATE": "2",  # Create table
            "INSERT": "3",  # Insert data
            "UPDATE": "7",  # Update data
            "DELETE": "8",  # Delete data
            "CREATE_INDEX": "9",  # Create index
            "DROP_INDEX": "10",  # Drop index
            "DROP": "11",  # Drop table
        }

    async def analyze_query(self, query_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        command = self.command_map.get(query_type)
        if not command:
            raise ValueError(f"Unsupported query type: {query_type}")
        
        return {
            "command_number": command,
            "params": params
        }

class MCPClient:
    def __init__(self):
        self.process = None
        self.mcp_path = r"C:\Users\Asus\Documents\LN\MCP\postgres-mcp"

    async def execute_command_sequence(self, command_info: Dict[str, Any]) -> str:
        try:
            print("[DEBUG] Starting MCP client process...")
            os.chdir(self.mcp_path)
            
            self.process = subprocess.Popen(
                'cargo run --example mcp_client',
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True
            )

            # Wait for initial output to clear
            print("[DEBUG] Waiting for MCP client to initialize...")
            time.sleep(2)  # Wait for tool schema output

            def read_output():
                output = ""
                while True:
                    line = self.process.stdout.readline()
                    # print(f"[DEBUG PROCESS LINE 1]: {line}")
                    if not line or "Available commands:" in line or "Enter connection string (postgresql://user:pass@host:port/db):" in line:
                        break
                    output += line
                return output.strip()

            def send_command(cmd, description=""):
                print(f"[DEBUG] Sending command: {cmd} ({description})")
                self.process.stdin.write(f"{cmd}\n")
                self.process.stdin.flush()
                time.sleep(1)
                return read_output()

            # Execute commands and collect outputs
            outputs = []
            
            # Connect sequence
            outputs.append(send_command('1', "Connect"))
            db_url = "postgresql://postgres:admin123@localhost:5432/whatsapp-supplier-agent"
            outputs.append(send_command(db_url, "Database URL"))
            
            # Execute main command
            outputs.append(send_command(command_info["command_number"], "Command number"))
            
            # Handle command-specific parameters
            if command_info["command_number"] == "5":  # LIST_TABLES
                if command_info["params"].get("schema"):
                    outputs.append(send_command(command_info["params"]["schema"], "Schema"))
            elif command_info["command_number"] == "4":  # SELECT
                if command_info["params"].get("query"):
                    outputs.append(send_command(command_info["params"]["query"], "Query"))
            elif command_info["command_number"] == "6": #DESCRIBE
                if command_info["params"].get("table_name"):
                    outputs.append(send_command(command_info["params"]["table_name"], "Table_name"))
            # Add more command-specific parameter handling here
            
            # Cleanup sequence
            outputs.append(send_command('12', "Unregister"))
            outputs.append(send_command('13', "Exit"))

            # Get final output
            final_output = self.process.communicate()[0]
            
            # Combine all outputs
            all_output = '\n'.join(outputs + [final_output])
            
            # Filter relevant output
            relevant_lines = [
                line for line in all_output.split('\n')
                if line.strip() and not line.strip().startswith(('Tool {', '}', '[', ']', '2025-'))
            ]

            print(f"[DEBUG] Relevant output: {relevant_lines}")
            
            return '\n'.join(relevant_lines)

        except Exception as e:
            print(f"[ERROR] MCP client error: {str(e)}")
            raise RuntimeError(f"MCP client error: {str(e)}")
        finally:
            if self.process:
                print("[DEBUG] Cleaning up process...")
                self.process.terminate()
                await asyncio.sleep(1)
                self.process.kill()

class DatabaseSession:
    def __init__(self):
        self.analyzer = QueryAnalyzer()
        self.client = MCPClient()

    async def execute_query(self, query_info: str) -> str:
        query_dict = json.loads(query_info)
        command_info = await self.analyzer.analyze_query(
            query_dict["command_type"],
            query_dict["params"]
        )
        return await self.client.execute_command_sequence(command_info)

async def main():
    try:
        print("\n[DEBUG] Initializing language model...")
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=os.getenv("GEMINI_API_KEY"))
        print("[DEBUG] Language model initialized")

        db_session = DatabaseSession()
        tools = [Tool(
            name="analyze_and_execute_query",
            description="""Analyze and execute database commands through MCP client.
            Available commands:
            - SELECT: Query data (requires: query)
            - LIST_TABLES: List all tables (requires: schema)
            - DESCRIBE: Describe table structure (requires: table_name)
            - CREATE: Create new table (requires: create_statement)
            - INSERT: Insert data (requires: insert_statement)
            - UPDATE: Update data (requires: update_statement)
            - DELETE: Delete data (requires: delete_statement)
            Input should be a JSON object with 'command_type' and required parameters.""",
            func=lambda x: asyncio.run(db_session.execute_query(x)),
            coroutine=lambda x: db_session.execute_query(x)
        )]

        print("\n[DEBUG] Creating prompt template...")
        prompt = PromptTemplate.from_template(
            """You are a PostgreSQL database assistant that helps users interact with their database through an MCP client interface.
            
            Available tools: {tool_names}
            
            To accomplish your tasks, you have access to the following tools:
            {tools}
            
            When using the analyze_and_execute_query tool, you must provide:
            1. command_type: The type of operation (SELECT, LIST_TABLES, etc.)
            2. Required parameters for that command type
            
            IMPORTANT: For ANY user query, you MUST follow this EXACT workflow in order:
            
            1. First, list all available tables:
               - Use analyze_and_execute_query with command_type: "LIST_TABLES" and params: {{"schema": "public"}}
            
            2. Then, identify which tables are relevant to the user's query
            
            3. For EACH relevant table, describe its structure:
               - Use analyze_and_execute_query with command_type: "DESCRIBE" and params: {{"table_name": "table_name_here"}}
            
            4. Only after understanding the schema, formulate your SQL query using ONLY columns that actually exist
            
            5. Execute your query and analyze the results
            
            NEVER skip steps 1-3. NEVER assume table structures. NEVER query columns that you haven't verified exist.
            
            Use the following format:
            Question: the input question you must answer
            Thought: I need to follow the workflow to understand the database schema first
            Action: analyze_and_execute_query
            Action Input: {{"command_type": "LIST_TABLES", "params": {{"schema": "public"}}}}
            Observation: [List of tables]
            Thought: Now I need to examine the structure of relevant tables
            Action: analyze_and_execute_query
            Action Input: {{"command_type": "DESCRIBE", "params": {{"table_name": "[relevant_table]"}}}}
            Observation: [Table structure]
            ... (repeat for each relevant table)
            Thought: Now I understand the schema and can formulate a proper SQL query
            Action: analyze_and_execute_query
            Action Input: {{"command_type": "SELECT", "params": {{"query": "SELECT ... FROM ... WHERE ..."}}}}
            Observation: [Query results]
            Thought: I now know the final answer
            Final Answer: [Clear explanation with accurate data]
            
            Begin!
            
            Question: {input}
            Thought:{agent_scratchpad}"""
        )
        print("[DEBUG] Prompt template created")

        print("\n[DEBUG] Creating agent...")
        agent = create_react_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True
        )
        print("[DEBUG] Agent created successfully")

        while True:
            try:
                user_query = input("\nPlease enter your database query in plain English (or 'exit' to quit): ")
                if user_query.lower() == 'exit':
                    break
                    
                print(f"[DEBUG] Received user query: {user_query}")
                print("\n[DEBUG] Executing agent...")
                response = await agent_executor.ainvoke({"input": user_query})
                print("[DEBUG] Agent execution completed")
                
                print("\nFinal Response:")
                print(response)
                
            except Exception as e:
                print(f"\n[ERROR] Query failed: {str(e)}")
                print("Please try another query.")

    except Exception as e:
        print(f"\n[ERROR] An error occurred: {str(e)}")
        print(f"[ERROR] Error type: {type(e)}")
        print(f"[ERROR] Traceback:\n{traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(main())