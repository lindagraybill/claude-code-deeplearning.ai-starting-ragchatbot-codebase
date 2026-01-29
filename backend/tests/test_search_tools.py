"""Tests for CourseSearchTool and ToolManager.

These tests verify the execute method of CourseSearchTool and the
ToolManager's ability to register and execute tools.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from vector_store import SearchResults


class TestCourseSearchToolExecute:
    """Tests for CourseSearchTool.execute() method."""

    def test_execute_returns_formatted_content(self, mock_vector_store, sample_search_results):
        """execute() should return formatted content with course/lesson headers."""
        mock_vector_store.search.return_value = sample_search_results

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="What is machine learning?")

        # Verify VectorStore.search was called correctly
        mock_vector_store.search.assert_called_once_with(
            query="What is machine learning?",
            course_name=None,
            lesson_number=None
        )

        # Verify result contains expected content
        assert "Introduction to AI" in result
        assert "Lesson 1" in result
        assert "machine learning" in result.lower()

    def test_execute_returns_no_content_when_empty(self, mock_vector_store_empty):
        """execute() returns 'No relevant content found' when VectorStore returns empty."""
        tool = CourseSearchTool(mock_vector_store_empty)
        result = tool.execute(query="What is quantum computing?")

        assert "No relevant content found" in result

    def test_execute_with_course_filter(self, mock_vector_store, sample_search_results):
        """execute() passes course_name filter to VectorStore."""
        mock_vector_store.search.return_value = sample_search_results

        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="neural networks", course_name="AI Course")

        mock_vector_store.search.assert_called_once_with(
            query="neural networks",
            course_name="AI Course",
            lesson_number=None
        )

    def test_execute_with_lesson_filter(self, mock_vector_store, sample_search_results):
        """execute() passes lesson_number filter to VectorStore."""
        mock_vector_store.search.return_value = sample_search_results

        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="introduction", lesson_number=1)

        mock_vector_store.search.assert_called_once_with(
            query="introduction",
            course_name=None,
            lesson_number=1
        )

    def test_execute_with_both_filters(self, mock_vector_store, sample_search_results):
        """execute() passes both course_name and lesson_number filters."""
        mock_vector_store.search.return_value = sample_search_results

        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="deep learning", course_name="ML Course", lesson_number=3)

        mock_vector_store.search.assert_called_once_with(
            query="deep learning",
            course_name="ML Course",
            lesson_number=3
        )

    def test_execute_handles_error_from_vector_store(self, mock_vector_store):
        """execute() returns error message when VectorStore returns error."""
        error_results = SearchResults(
            documents=[],
            metadata=[],
            distances=[],
            error="No course found matching 'NonExistent'"
        )
        mock_vector_store.search.return_value = error_results

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="test", course_name="NonExistent")

        assert "No course found matching" in result

    def test_execute_tracks_sources(self, mock_vector_store, sample_search_results):
        """execute() populates last_sources for UI display."""
        mock_vector_store.search.return_value = sample_search_results

        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="test")

        # Verify sources were tracked
        assert len(tool.last_sources) == 2
        assert tool.last_sources[0]["text"] == "Introduction to AI - Lesson 1"

    def test_execute_with_empty_results_includes_filter_info(self, mock_vector_store_empty):
        """When empty with filters, message includes filter context."""
        tool = CourseSearchTool(mock_vector_store_empty)
        result = tool.execute(query="test", course_name="ML Course", lesson_number=5)

        assert "No relevant content found" in result
        assert "ML Course" in result
        assert "lesson 5" in result


class TestCourseSearchToolDefinition:
    """Tests for CourseSearchTool.get_tool_definition()."""

    def test_tool_definition_structure(self, mock_vector_store):
        """Tool definition has required Anthropic format."""
        tool = CourseSearchTool(mock_vector_store)
        definition = tool.get_tool_definition()

        assert definition["name"] == "search_course_content"
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["input_schema"]["type"] == "object"

    def test_tool_definition_has_query_parameter(self, mock_vector_store):
        """Tool definition includes query as required parameter."""
        tool = CourseSearchTool(mock_vector_store)
        definition = tool.get_tool_definition()

        properties = definition["input_schema"]["properties"]
        assert "query" in properties
        assert "query" in definition["input_schema"]["required"]

    def test_tool_definition_has_optional_filters(self, mock_vector_store):
        """Tool definition includes optional course_name and lesson_number."""
        tool = CourseSearchTool(mock_vector_store)
        definition = tool.get_tool_definition()

        properties = definition["input_schema"]["properties"]
        assert "course_name" in properties
        assert "lesson_number" in properties

        # These should NOT be required
        required = definition["input_schema"]["required"]
        assert "course_name" not in required
        assert "lesson_number" not in required


class TestCourseOutlineToolExecute:
    """Tests for CourseOutlineTool.execute() method."""

    def test_execute_returns_course_outline(self, mock_vector_store):
        """execute() returns formatted course outline."""
        tool = CourseOutlineTool(mock_vector_store)
        result = tool.execute(course_name="Introduction to AI")

        assert "Course:" in result
        assert "Introduction to AI" in result
        assert "Lessons:" in result

    def test_execute_returns_error_for_unknown_course(self, mock_vector_store):
        """execute() returns error when course not found."""
        mock_vector_store._resolve_course_name.return_value = None

        tool = CourseOutlineTool(mock_vector_store)
        result = tool.execute(course_name="NonExistent Course")

        assert "No course found matching" in result


class TestToolManager:
    """Tests for ToolManager class."""

    def test_register_tool(self, mock_vector_store):
        """ToolManager can register a tool."""
        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)

        manager.register_tool(search_tool)

        assert "search_course_content" in manager.tools

    def test_register_multiple_tools(self, mock_vector_store):
        """ToolManager can register multiple tools."""
        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        outline_tool = CourseOutlineTool(mock_vector_store)

        manager.register_tool(search_tool)
        manager.register_tool(outline_tool)

        assert len(manager.tools) == 2
        assert "search_course_content" in manager.tools
        assert "get_course_outline" in manager.tools

    def test_get_tool_definitions(self, mock_vector_store):
        """ToolManager returns all tool definitions for Anthropic API."""
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_vector_store))
        manager.register_tool(CourseOutlineTool(mock_vector_store))

        definitions = manager.get_tool_definitions()

        assert len(definitions) == 2
        names = [d["name"] for d in definitions]
        assert "search_course_content" in names
        assert "get_course_outline" in names

    def test_execute_tool_by_name(self, mock_vector_store, sample_search_results):
        """ToolManager executes tool by name with parameters."""
        mock_vector_store.search.return_value = sample_search_results

        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_vector_store))

        result = manager.execute_tool("search_course_content", query="machine learning")

        assert "machine learning" in result.lower() or "Introduction to AI" in result

    def test_execute_unknown_tool(self):
        """ToolManager returns error for unknown tool name."""
        manager = ToolManager()

        result = manager.execute_tool("nonexistent_tool", query="test")

        assert "not found" in result.lower()

    def test_get_last_sources(self, mock_vector_store, sample_search_results):
        """ToolManager retrieves sources from last tool execution."""
        mock_vector_store.search.return_value = sample_search_results

        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(search_tool)

        manager.execute_tool("search_course_content", query="test")
        sources = manager.get_last_sources()

        assert len(sources) == 2

    def test_reset_sources(self, mock_vector_store, sample_search_results):
        """ToolManager can reset sources from all tools."""
        mock_vector_store.search.return_value = sample_search_results

        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(search_tool)

        manager.execute_tool("search_course_content", query="test")
        assert len(manager.get_last_sources()) > 0

        manager.reset_sources()
        assert manager.get_last_sources() == []


class TestToolManagerWithEmptyResults:
    """Tests for ToolManager behavior when search returns empty (MAX_RESULTS=0 bug)."""

    def test_execute_search_with_empty_vector_store(self, mock_vector_store_empty):
        """
        When VectorStore returns empty (MAX_RESULTS=0), tool returns 'No relevant content'.

        This test documents the bug behavior - searches always return empty.
        """
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_vector_store_empty))

        result = manager.execute_tool("search_course_content", query="What is machine learning?")

        # This is what happens with MAX_RESULTS=0
        assert "No relevant content found" in result

    def test_sources_empty_when_no_results(self, mock_vector_store_empty):
        """Sources list is empty when search returns no results."""
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_vector_store_empty))

        manager.execute_tool("search_course_content", query="test")
        sources = manager.get_last_sources()

        assert sources == []
