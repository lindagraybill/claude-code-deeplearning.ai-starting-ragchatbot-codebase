"""Tests for RAGSystem integration.

These tests verify the full query pipeline through RAGSystem,
including tool registration, AI generation, and source retrieval.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from config import Config
from rag_system import RAGSystem


class TestRAGSystemInitialization:
    """Tests for RAGSystem initialization."""

    def test_initializes_all_components(self):
        """RAGSystem initializes all required components."""
        config = Config()
        config.MAX_RESULTS = 5
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        with patch('rag_system.VectorStore') as MockVectorStore, \
             patch('rag_system.AIGenerator') as MockAIGenerator, \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager'):

            system = RAGSystem(config)

            # Verify components were created
            MockVectorStore.assert_called_once()
            MockAIGenerator.assert_called_once()
            assert system.tool_manager is not None

    def test_registers_search_tools(self):
        """RAGSystem registers CourseSearchTool and CourseOutlineTool."""
        config = Config()
        config.MAX_RESULTS = 5
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator'), \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager'):

            system = RAGSystem(config)

            tool_names = list(system.tool_manager.tools.keys())
            assert "search_course_content" in tool_names
            assert "get_course_outline" in tool_names

    def test_passes_max_results_to_vector_store(self):
        """RAGSystem passes MAX_RESULTS config to VectorStore."""
        config = Config()
        config.MAX_RESULTS = 10
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        with patch('rag_system.VectorStore') as MockVectorStore, \
             patch('rag_system.AIGenerator'), \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager'):

            RAGSystem(config)

            # Verify MAX_RESULTS was passed
            call_args = MockVectorStore.call_args
            assert call_args[0][2] == 10  # Third positional arg is max_results


class TestRAGSystemQueryWithZeroMaxResults:
    """Tests demonstrating the MAX_RESULTS=0 bug."""

    def test_query_with_zero_max_results_creates_broken_system(self):
        """
        When MAX_RESULTS=0, VectorStore is created with max_results=0,
        causing all searches to return empty results.

        This test documents the bug.
        """
        config = Config()
        config.MAX_RESULTS = 0  # THE BUG
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        with patch('rag_system.VectorStore') as MockVectorStore, \
             patch('rag_system.AIGenerator'), \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager'):

            RAGSystem(config)

            # VectorStore created with max_results=0
            call_args = MockVectorStore.call_args
            max_results_passed = call_args[0][2]

            assert max_results_passed == 0, (
                "This test confirms MAX_RESULTS=0 is passed to VectorStore, "
                "which causes all searches to return empty results."
            )


class TestRAGSystemQuery:
    """Tests for RAGSystem.query() method."""

    def test_query_calls_ai_generator_with_tools(self):
        """query() passes tools to AIGenerator."""
        config = Config()
        config.MAX_RESULTS = 5
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator') as MockAIGenerator, \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager') as MockSessionManager:

            mock_generator = MagicMock()
            mock_generator.generate_response.return_value = "Test response"
            MockAIGenerator.return_value = mock_generator

            mock_session = MagicMock()
            mock_session.get_conversation_history.return_value = None
            MockSessionManager.return_value = mock_session

            system = RAGSystem(config)
            response, sources = system.query("What is machine learning?")

            # Verify AIGenerator was called with tools
            call_args = mock_generator.generate_response.call_args
            assert call_args.kwargs.get("tools") is not None
            assert call_args.kwargs.get("tool_manager") is not None

    def test_query_returns_response_and_sources(self):
        """query() returns tuple of (response, sources)."""
        config = Config()
        config.MAX_RESULTS = 5
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator') as MockAIGenerator, \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager') as MockSessionManager:

            mock_generator = MagicMock()
            mock_generator.generate_response.return_value = "Here is your answer"
            MockAIGenerator.return_value = mock_generator

            mock_session = MagicMock()
            mock_session.get_conversation_history.return_value = None
            MockSessionManager.return_value = mock_session

            system = RAGSystem(config)
            # Mock sources from tool manager
            system.tool_manager.get_last_sources = MagicMock(
                return_value=[{"text": "Test Course", "link": "https://example.com"}]
            )

            response, sources = system.query("test query")

            assert response == "Here is your answer"
            assert len(sources) == 1
            assert sources[0]["text"] == "Test Course"

    def test_query_with_session_includes_history(self):
        """query() includes conversation history when session_id provided."""
        config = Config()
        config.MAX_RESULTS = 5
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator') as MockAIGenerator, \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager') as MockSessionManager:

            mock_generator = MagicMock()
            mock_generator.generate_response.return_value = "Follow up answer"
            MockAIGenerator.return_value = mock_generator

            mock_session = MagicMock()
            mock_session.get_conversation_history.return_value = "User: Hi\nAssistant: Hello!"
            MockSessionManager.return_value = mock_session

            system = RAGSystem(config)
            system.query("follow up question", session_id="session-123")

            # Verify history was retrieved
            mock_session.get_conversation_history.assert_called_with("session-123")

            # Verify history was passed to AIGenerator
            call_args = mock_generator.generate_response.call_args
            assert call_args.kwargs.get("conversation_history") is not None

    def test_query_updates_session_history(self):
        """query() adds exchange to session history."""
        config = Config()
        config.MAX_RESULTS = 5
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator') as MockAIGenerator, \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager') as MockSessionManager:

            mock_generator = MagicMock()
            mock_generator.generate_response.return_value = "Answer"
            MockAIGenerator.return_value = mock_generator

            mock_session = MagicMock()
            mock_session.get_conversation_history.return_value = None
            MockSessionManager.return_value = mock_session

            system = RAGSystem(config)
            system.query("My question", session_id="session-456")

            # Verify exchange was added
            mock_session.add_exchange.assert_called_once_with(
                "session-456",
                "My question",
                "Answer"
            )

    def test_query_resets_sources_after_retrieval(self):
        """query() resets tool sources after retrieving them."""
        config = Config()
        config.MAX_RESULTS = 5
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator') as MockAIGenerator, \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager') as MockSessionManager:

            mock_generator = MagicMock()
            mock_generator.generate_response.return_value = "Response"
            MockAIGenerator.return_value = mock_generator

            mock_session = MagicMock()
            mock_session.get_conversation_history.return_value = None
            MockSessionManager.return_value = mock_session

            system = RAGSystem(config)
            system.tool_manager.reset_sources = MagicMock()

            system.query("test")

            # Verify sources were reset
            system.tool_manager.reset_sources.assert_called_once()


class TestRAGSystemQueryFlow:
    """Tests for the complete query flow through RAGSystem."""

    def test_full_query_flow_with_tool_execution(self):
        """
        End-to-end test: query -> tool execution -> response.

        This tests the flow when Claude decides to use a tool.
        """
        config = Config()
        config.MAX_RESULTS = 5
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        with patch('rag_system.VectorStore') as MockVectorStore, \
             patch('rag_system.AIGenerator') as MockAIGenerator, \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager') as MockSessionManager:

            # Setup mock vector store
            mock_store = MagicMock()
            mock_store.max_results = 5
            MockVectorStore.return_value = mock_store

            # Setup mock AI generator that simulates tool use
            mock_generator = MagicMock()
            mock_generator.generate_response.return_value = "Based on the course content..."
            MockAIGenerator.return_value = mock_generator

            # Setup mock session manager
            mock_session = MagicMock()
            mock_session.get_conversation_history.return_value = None
            MockSessionManager.return_value = mock_session

            system = RAGSystem(config)

            # Execute query
            response, sources = system.query("What is machine learning?")

            # Verify the flow
            assert response == "Based on the course content..."
            mock_generator.generate_response.assert_called_once()

    def test_query_prompt_format(self):
        """query() formats the prompt correctly for the AI."""
        config = Config()
        config.MAX_RESULTS = 5
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator') as MockAIGenerator, \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager') as MockSessionManager:

            mock_generator = MagicMock()
            mock_generator.generate_response.return_value = "Response"
            MockAIGenerator.return_value = mock_generator

            mock_session = MagicMock()
            mock_session.get_conversation_history.return_value = None
            MockSessionManager.return_value = mock_session

            system = RAGSystem(config)
            system.query("What is deep learning?")

            # Check the query passed to AI includes instruction
            call_args = mock_generator.generate_response.call_args
            query_sent = call_args.kwargs.get("query", "")
            assert "deep learning" in query_sent
            assert "course materials" in query_sent.lower()


class TestRAGSystemCourseAnalytics:
    """Tests for RAGSystem.get_course_analytics() method."""

    def test_get_course_analytics_returns_stats(self):
        """get_course_analytics() returns course statistics."""
        config = Config()
        config.MAX_RESULTS = 5
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        with patch('rag_system.VectorStore') as MockVectorStore, \
             patch('rag_system.AIGenerator'), \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager'):

            mock_store = MagicMock()
            mock_store.get_course_count.return_value = 4
            mock_store.get_existing_course_titles.return_value = [
                "Course A", "Course B", "Course C", "Course D"
            ]
            MockVectorStore.return_value = mock_store

            system = RAGSystem(config)
            analytics = system.get_course_analytics()

            assert analytics["total_courses"] == 4
            assert len(analytics["course_titles"]) == 4
