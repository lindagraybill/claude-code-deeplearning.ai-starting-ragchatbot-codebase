"""Shared fixtures for RAG chatbot tests."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from vector_store import SearchResults
from config import Config


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def mock_config():
    """Create a mock Config object for testing."""
    config = Config()
    config.MAX_RESULTS = 5
    config.CHROMA_PATH = "./test_chroma"
    config.ANTHROPIC_API_KEY = "test-api-key"
    config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.MAX_HISTORY = 2
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    return config


# ============================================================================
# RAG System Fixtures
# ============================================================================

@pytest.fixture
def mock_rag_system(mock_vector_store, mock_tool_manager):
    """Mock RAGSystem for API testing."""
    rag = MagicMock()
    rag.vector_store = mock_vector_store
    rag.tool_manager = mock_tool_manager
    rag.session_manager = MagicMock()
    rag.session_manager.create_session.return_value = "test-session-123"
    rag.query.return_value = (
        "This is a test response about machine learning.",
        [{"text": "Introduction to AI - Lesson 1", "link": "https://example.com/lesson/1"}]
    )
    rag.get_course_analytics.return_value = {
        "total_courses": 3,
        "course_titles": ["Introduction to AI", "Deep Learning", "NLP Fundamentals"]
    }
    return rag


# ============================================================================
# API Testing Fixtures
# ============================================================================

@pytest.fixture
def test_app(mock_rag_system):
    """
    Create a test FastAPI app with mocked RAG system.

    This creates a fresh app without static file mounting to avoid
    filesystem dependencies in tests.
    """
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import List, Optional

    app = FastAPI(title="Test RAG System")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store the mock rag_system on the app for access
    app.state.rag_system = mock_rag_system

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class Source(BaseModel):
        text: str
        link: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Source]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = app.state.rag_system.session_manager.create_session()

            answer, sources = app.state.rag_system.query(request.query, session_id)

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = app.state.rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/")
    async def root():
        return {"status": "ok", "message": "RAG System API"}

    return app


@pytest.fixture
def test_client(test_app):
    """Create a test client for the FastAPI app."""
    from httpx import AsyncClient, ASGITransport
    import asyncio

    async def get_client():
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    return get_client


@pytest.fixture
def mock_search_results():
    """Factory for creating mock SearchResults."""

    def _create(documents=None, metadata=None, distances=None, error=None):
        return SearchResults(
            documents=documents or [],
            metadata=metadata or [],
            distances=distances or [],
            error=error,
        )

    return _create


@pytest.fixture
def sample_search_results():
    """Pre-built SearchResults with sample course content."""
    return SearchResults(
        documents=[
            "Machine learning is a subset of AI that enables systems to learn from data.",
            "Neural networks are computing systems inspired by biological neural networks.",
        ],
        metadata=[
            {"course_title": "Introduction to AI", "lesson_number": 1},
            {"course_title": "Introduction to AI", "lesson_number": 2},
        ],
        distances=[0.15, 0.25],
    )


@pytest.fixture
def empty_search_results():
    """Empty SearchResults (simulates MAX_RESULTS=0 bug)."""
    return SearchResults(documents=[], metadata=[], distances=[])


@pytest.fixture
def mock_vector_store(sample_search_results):
    """Mock VectorStore that returns controlled results."""
    store = MagicMock()
    store.max_results = 5
    store.search.return_value = sample_search_results
    store.get_lesson_link.return_value = "https://example.com/lesson/1"
    store._resolve_course_name.return_value = "Introduction to AI"
    store.get_all_courses_metadata.return_value = [
        {
            "title": "Introduction to AI",
            "course_link": "https://example.com/course",
            "lessons": [
                {"lesson_number": 1, "lesson_title": "Getting Started"},
                {"lesson_number": 2, "lesson_title": "Neural Networks"},
            ],
        }
    ]
    return store


@pytest.fixture
def mock_vector_store_empty(empty_search_results):
    """Mock VectorStore that returns empty results (simulates the bug)."""
    store = MagicMock()
    store.max_results = 0
    store.search.return_value = empty_search_results
    return store


@pytest.fixture
def mock_chroma_collection():
    """Mock ChromaDB collection with controlled query results."""
    collection = MagicMock()

    def mock_query(query_texts, n_results, where=None):
        if n_results == 0:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        return {
            "documents": [["Test content 1", "Test content 2"][:n_results]],
            "metadatas": [
                [
                    {"course_title": "Test Course", "lesson_number": 1},
                    {"course_title": "Test Course", "lesson_number": 2},
                ][:n_results]
            ],
            "distances": [[0.1, 0.2][:n_results]],
        }

    collection.query = MagicMock(side_effect=mock_query)
    collection.get.return_value = {
        "ids": ["Test Course"],
        "metadatas": [{"title": "Test Course", "lessons_json": "[]"}],
    }
    collection.add = MagicMock()
    return collection


@pytest.fixture
def mock_anthropic_response():
    """Factory for creating mock Anthropic API responses."""

    def _create(text="Test response", stop_reason="end_turn", tool_use=None):
        response = MagicMock()
        response.stop_reason = stop_reason

        if tool_use:
            tool_block = MagicMock()
            tool_block.type = "tool_use"
            tool_block.id = tool_use.get("id", "tool_123")
            tool_block.name = tool_use.get("name", "search_course_content")
            tool_block.input = tool_use.get("input", {"query": "test"})
            response.content = [tool_block]
        else:
            text_block = MagicMock()
            text_block.type = "text"
            text_block.text = text
            response.content = [text_block]

        return response

    return _create


@pytest.fixture
def mock_anthropic_client(mock_anthropic_response):
    """Mock Anthropic API client."""
    client = MagicMock()
    client.messages.create.return_value = mock_anthropic_response()
    return client


@pytest.fixture
def mock_tool_manager():
    """Mock ToolManager for testing AIGenerator."""
    manager = MagicMock()
    manager.execute_tool.return_value = "[Test Course - Lesson 1]\nTest content"
    manager.get_last_sources.return_value = [
        {"text": "Test Course - Lesson 1", "link": "https://example.com"}
    ]
    manager.get_tool_definitions.return_value = [
        {
            "name": "search_course_content",
            "description": "Search course materials",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        }
    ]
    return manager


@pytest.fixture(autouse=True)
def mock_sentence_transformer():
    """Prevent actual model loading during tests."""
    with patch(
        "chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction"
    ):
        yield
