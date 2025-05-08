# PostgreSQL Database Assistant with LangChain and Gemini
## Overview
This project implements an intelligent database assistant that allows users to interact with PostgreSQL databases using natural language queries. It leverages the power of Google's Gemini AI model through LangChain to interpret user questions and execute appropriate database operations.

## Features
- Natural language interface for database queries
- Intelligent schema understanding and validation
- Automatic table structure analysis
- State tracking to prevent redundant operations
- Support for multiple database operations:
  - SELECT queries
  - Table listing
  - Schema description
  - Data insertion
  - Table creation and deletion
  - Index management
  - Data updates and deletions
## Prerequisites
- Python 3.8+
- PostgreSQL database
- Rust (for MCP client)
- Google Cloud API key for Gemini AI
## Required Python Packages
```plaintext
langchain
langchain-google-genai
python-dotenv
 ```

## Environment Setup
1. Create a .env file in the project root with:
```plaintext
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql://user:password@host:port/database
 ```
```

2. Install the MCP (Multi-Command PostgreSQL) client:
```bash
git clone https://github.com/your-repo/postgres-mcp.git
cd postgres-mcp
cargo build
 ```
```

## Usage
1. Start the application:
```bash
python src/postgresql_test.py
 ```

2. Enter your database queries in plain English:
```plaintext
Examples:
- "Show me all tables in the database"
- "What are the columns in the customers table?"
- "Find all orders that were delayed"
- "List suppliers who have pending deliveries"
 ```
```

3. Type 'exit' to quit the application
## How It Works
### 1. Query Processing Pipeline
- User inputs natural language query
- Gemini AI interprets the query intent
- System follows a structured workflow:
  1. Lists available tables
  2. Identifies relevant tables
  3. Analyzes table structures
  4. Formulates appropriate SQL query
  5. Executes and returns results
### 2. State Tracking
- Maintains session state to avoid redundant operations
- Caches table listings and structure descriptions
- Tracks executed queries for optimization
### 3. Error Handling
- Comprehensive error catching and reporting
- Invalid query protection
- Database connection management
- Process cleanup for MCP client
## Architecture
### Components
1. ExecutionTracker
   
   - Manages operation state
   - Prevents redundant queries
   - Maintains execution history
2. QueryAnalyzer
   
   - Interprets query types
   - Maps operations to MCP commands
   - Validates query parameters
3. MCPClient
   
   - Handles database communication
   - Manages subprocess execution
   - Formats query results
4. DatabaseSession
   
   - Coordinates component interaction
   - Manages database connections
   - Implements caching logic
## Security Features
- Environment variable based configuration
- Structured query validation
- Process isolation for database operations
- Error handling and logging
## Limitations
- Requires Rust MCP client
- Single database connection per session
- Maximum 10 iterations per query
- Gemini API dependency
## Contributing
Contributions are welcome! Please feel free to submit pull requests or create issues for bugs and feature requests.

## Acknowledgments
- LangChain framework
- Google Gemini AI
- PostgreSQL community
- MCP client contributors
