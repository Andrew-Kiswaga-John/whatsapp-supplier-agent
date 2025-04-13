import asyncio
import os
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import AgentExecutor, create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain.tools import Tool
from dotenv import load_dotenv
import traceback
import json
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

# Load environment variables
load_dotenv()

class DatabaseConnection:
    def __init__(self):
        self.client = None
        self.session = None
        self._lock = asyncio.Lock()
        self.server_params = StdioServerParameters(
            command="docker",
            args=["run", "--rm", "-i", "mcp/postgres:latest", os.getenv("DATABASE_URL")],
        )

    async def connect(self):
        async with self._lock:
            if not self.session:
                self.client = stdio_client(self.server_params)
                read, write = await self.client.__aenter__()
                self.session = ClientSession(read, write)
                await self.session.__aenter__()
                await self.session.initialize()
        return self.session

    async def disconnect(self):
        async with self._lock:
            if self.session:
                await self.session.__aexit__(None, None, None)
                self.session = None
            if self.client:
                await self.client.__aexit__(None, None, None)
                self.client = None

class DatabaseTool:
    def __init__(self, connection: DatabaseConnection, mcp_tool: Any):
        self.connection = connection
        self.mcp_tool = mcp_tool
        self.schema_cache = None

    async def get_schema(self) -> Dict[str, Any]:
        if not self.schema_cache:
            try:
                await self.connection.connect()
                schema_query = {"sql": "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public'"}
                self.schema_cache = await self.mcp_tool.arun(schema_query)
            except Exception as e:
                print(f"[WARNING] Failed to fetch schema: {str(e)}")
                self.schema_cache = {}
        return self.schema_cache

    async def execute_query(self, query_input: Dict[str, Any]) -> Dict[str, Any]:
        try:
            await self.connection.connect()
            
            if isinstance(query_input, str):
                query_input = json.loads(query_input)
            
            if not isinstance(query_input, dict):
                raise ValueError("Query input must be a dictionary or valid JSON string")
            
            sql_query = query_input.get('query')
            if not sql_query:
                raise ValueError("Query input must contain a 'query' key")

            formatted_query = {"sql": sql_query}
            
            result = await self.mcp_tool.arun(formatted_query)
            return result

        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format in query input")
        except Exception as e:
            print(f"[DEBUG] Query execution error details: {str(e)}")
            raise RuntimeError(f"Query execution failed: {str(e)}")

class DatabaseSession:
    def __init__(self):
        self.connection = DatabaseConnection()
        self.db_tool = None
        self.tools = None

    async def __aenter__(self):
        try:
            session = await self.connection.connect()
            
            mcp_tools = await load_mcp_tools(session)
            print(f"[DEBUG] Loaded raw MCP tools: {[tool.name for tool in mcp_tools]}")
            
            self.db_tool = DatabaseTool(self.connection, mcp_tools[0])
            await self.db_tool.get_schema()
            
            self.tools = [Tool(
                name="query",
                description="""Execute a SQL query on the PostgreSQL database. 
                The query must be read-only (SELECT statements only).
                Input should be a JSON object with a 'query' key containing the SQL query string.""",
                func=self.db_tool.execute_query,
                coroutine=self.db_tool.execute_query
            )]
            
            return self.tools
            
        except Exception as e:
            print(f"[ERROR] Failed to setup database session: {str(e)}")
            await self.connection.disconnect()
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.connection.disconnect()

async def main():
    try:
        print("\n[DEBUG] Initializing language model...")
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=os.getenv("GEMINI_API_KEY"))
        print("[DEBUG] Language model initialized")

        db_session = DatabaseSession()
        async with db_session as tools:
            print("\n[DEBUG] Creating prompt template...")
            prompt = PromptTemplate.from_template(
                """You are a PostgreSQL database assistant that helps users interact with their database.
                
                To accomplish your tasks, you have access to the following tools:
                {tools}
                
                Use the following format:
                Question: the input question you must answer
                Thought: you should always think about what to do
                Action: the action to take, should be one of [{tool_names}]
                Action Input: the input must be a JSON object containing the SQL query
                Observation: the result of the action
                ... (this Thought/Action/Action Input/Observation can repeat N times)
                Thought: I now know the final answer
                Final Answer: provide a clear explanation of what was done and the results
                
                Remember: 
                - Always format Action Input as a JSON object with the 'query' key containing the SQL query string
                - Only use READ-ONLY queries (SELECT statements)
                - Explain the results in a user-friendly manner
                - Handle errors gracefully and suggest fixes
                
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
                max_iterations=3,
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