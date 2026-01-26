# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Start the development server:**
```bash
cd backend && uv run uvicorn app:app --reload --port 8000
```

Or use the shell script (Linux/Mac/Git Bash):
```bash
./run.sh
```

**Install dependencies:**
```bash
uv sync
```

**Important:** Always use `uv` to run the server, run Python files, and manage dependencies. Do not use `pip` or `python` directly—use `uv run` instead.

The application runs at http://localhost:8000 with API docs at http://localhost:8000/docs.

## Architecture

This is a RAG (Retrieval-Augmented Generation) chatbot for querying course materials. It uses Claude's tool-calling feature to decide when to search the vector database.

### Query Flow

1. **Frontend** (`frontend/script.js`) sends POST to `/api/query` with query and session_id
2. **FastAPI** (`backend/app.py`) routes to RAGSystem
3. **RAGSystem** (`backend/rag_system.py`) orchestrates the query:
   - Retrieves conversation history from SessionManager
   - Calls AIGenerator with tool definitions
4. **AIGenerator** (`backend/ai_generator.py`) makes Claude API call:
   - If Claude returns `stop_reason: "tool_use"`, executes the search tool and makes a second API call with results
   - Otherwise returns direct response
5. **CourseSearchTool** (`backend/search_tools.py`) queries VectorStore with optional course/lesson filters
6. **VectorStore** (`backend/vector_store.py`) performs semantic search on ChromaDB

### Key Components

| Component | Purpose |
|-----------|---------|
| `RAGSystem` | Main orchestrator - coordinates all components |
| `AIGenerator` | Wraps Anthropic API with tool execution loop |
| `VectorStore` | ChromaDB interface with two collections: `course_catalog` (metadata) and `course_content` (searchable chunks) |
| `DocumentProcessor` | Parses course documents, chunks text with sentence-aware splitting |
| `ToolManager` | Registers tools and executes them by name |
| `SessionManager` | Tracks conversation history per session |

### Document Format

Course documents in `docs/` follow this structure:
```
Course Title: [title]
Course Link: [url]
Course Instructor: [name]

Lesson 0: [title]
Lesson Link: [url]
[content...]

Lesson 1: [title]
...
```

### Configuration

Settings in `backend/config.py`:
- `CHUNK_SIZE`: 800 characters per chunk
- `CHUNK_OVERLAP`: 100 characters overlap between chunks
- `MAX_RESULTS`: 5 search results returned
- `MAX_HISTORY`: 2 conversation exchanges kept
- `EMBEDDING_MODEL`: all-MiniLM-L6-v2
- `ANTHROPIC_MODEL`: claude-sonnet-4-20250514

### Data Models

- `Course`: title, course_link, instructor, lessons[]
- `Lesson`: lesson_number, title, lesson_link
- `CourseChunk`: content, course_title, lesson_number, chunk_index

## Environment

Requires `.env` file with:
```
ANTHROPIC_API_KEY=your-key
```
