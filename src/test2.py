import asyncio
import os
from langchain_mcp_adapters.tools import load_mcp_tools
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
import traceback

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logging
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Configure server parameters
server_params = StdioServerParameters(
    command="docker",
    args=["run", "--rm", "-i", "mcp/postgres:latest", os.getenv("DATABASE_URL")],
)

async def execute_query(sql_query: str):
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the connection
                await session.initialize()
                logging.info("Database connection initialized")

                # Get MCP tools
                tools = await load_mcp_tools(session)
                mcp_tool = tools[0]  # PostgreSQL tool is the first one
                logging.info("Database tool loaded")

                # Create task group for query execution
                async with asyncio.TaskGroup() as tg:
                    # Format and execute the query
                    formatted_query = {"sql": sql_query}
                    query_task = tg.create_task(mcp_tool.arun(formatted_query))
                    
                    try:
                        result = await query_task
                        logging.info("Query executed successfully")
                        return result
                    except* Exception as e:
                        for exc in e.exceptions:
                            logging.error(f"Detailed error: {exc}")
                            logging.error(f"Error traceback: {traceback.format_exc()}")
                        raise

    except Exception as e:
        logging.error(f"Error during query execution: {str(e)}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise

async def main():
    try:
        while True:
            print("\nEnter your SQL query (or 'exit' to quit):")
            query = input("> ")
            
            if query.lower() == 'exit':
                break

            if not query.strip():
                print("Query cannot be empty")
                continue

            try:
                logging.info(f"Executing query: {query}")
                result = await execute_query(query)
                
                print("\nQuery Result:")
                print(result)
            except Exception as e:
                print(f"\nError executing query: {str(e)}")
                logging.error(f"Query execution failed: {traceback.format_exc()}")
                continue

    except Exception as e:
        logging.error(f"An error occurred in main: {str(e)}")
        logging.error(f"Main error traceback: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting gracefully...")
    except Exception as e:
        logging.critical(f"Critical error: {str(e)}")
        logging.critical(f"Critical error traceback: {traceback.format_exc()}")