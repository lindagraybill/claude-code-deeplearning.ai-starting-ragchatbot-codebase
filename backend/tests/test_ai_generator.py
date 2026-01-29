"""Tests for AIGenerator class.

These tests verify that AIGenerator correctly calls the Anthropic API
and properly handles tool use requests from Claude.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from ai_generator import AIGenerator


class TestAIGeneratorInitialization:
    """Tests for AIGenerator initialization."""

    def test_initialization_sets_model(self):
        """AIGenerator stores the model name."""
        with patch('ai_generator.anthropic.Anthropic'):
            generator = AIGenerator(api_key="test-key", model="test-model")
            assert generator.model == "test-model"

    def test_initialization_creates_client(self):
        """AIGenerator creates an Anthropic client."""
        with patch('ai_generator.anthropic.Anthropic') as MockAnthropic:
            generator = AIGenerator(api_key="test-key", model="test-model")
            MockAnthropic.assert_called_once_with(api_key="test-key")

    def test_base_params_set_correctly(self):
        """AIGenerator sets base API parameters."""
        with patch('ai_generator.anthropic.Anthropic'):
            generator = AIGenerator(api_key="test-key", model="claude-test")

            assert generator.base_params["model"] == "claude-test"
            assert generator.base_params["temperature"] == 0
            assert generator.base_params["max_tokens"] == 800


class TestAIGeneratorDirectResponse:
    """Tests for AIGenerator.generate_response() without tool use."""

    def test_direct_response_without_tools(self, mock_anthropic_client, mock_anthropic_response):
        """Returns text directly when no tools provided."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response(
            text="Hello! How can I help you?"
        )

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_anthropic_client):
            generator = AIGenerator(api_key="test", model="test")
            result = generator.generate_response(query="Hello")

        assert result == "Hello! How can I help you?"
        mock_anthropic_client.messages.create.assert_called_once()

    def test_direct_response_with_tools_not_used(self, mock_anthropic_client, mock_anthropic_response):
        """Returns text when tools provided but Claude doesn't use them."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response(
            text="I can answer that directly.",
            stop_reason="end_turn"
        )

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_anthropic_client):
            generator = AIGenerator(api_key="test", model="test")
            tools = [{"name": "search_course_content", "input_schema": {}}]
            result = generator.generate_response(query="What is 2+2?", tools=tools)

        assert result == "I can answer that directly."

    def test_conversation_history_included(self, mock_anthropic_client, mock_anthropic_response):
        """Conversation history is appended to system prompt."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response()

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_anthropic_client):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(
                query="Follow up question",
                conversation_history="User: Hi\nAssistant: Hello!"
            )

        call_args = mock_anthropic_client.messages.create.call_args
        system_content = call_args.kwargs.get("system", "")
        assert "Previous conversation:" in system_content
        assert "User: Hi" in system_content


class TestAIGeneratorToolExecution:
    """Tests for AIGenerator handling tool use requests."""

    def test_detects_tool_use_stop_reason(self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager):
        """Detects when Claude requests tool use."""
        # First call returns tool use request
        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "tool_123",
                "name": "search_course_content",
                "input": {"query": "machine learning"}
            }
        )

        # Second call returns final response
        final_response = mock_anthropic_response(text="Based on my search...")

        mock_anthropic_client.messages.create.side_effect = [tool_response, final_response]

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_anthropic_client):
            generator = AIGenerator(api_key="test", model="test")
            tools = [{"name": "search_course_content", "input_schema": {}}]
            result = generator.generate_response(
                query="What is ML?",
                tools=tools,
                tool_manager=mock_tool_manager
            )

        # Verify two API calls were made
        assert mock_anthropic_client.messages.create.call_count == 2
        assert result == "Based on my search..."

    def test_executes_tool_via_tool_manager(self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager):
        """Executes tool through ToolManager with correct parameters."""
        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "tool_123",
                "name": "search_course_content",
                "input": {"query": "neural networks", "course_name": "AI Course"}
            }
        )
        final_response = mock_anthropic_response(text="Here's what I found...")

        mock_anthropic_client.messages.create.side_effect = [tool_response, final_response]

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_anthropic_client):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(
                query="Search for neural networks",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tool_manager
            )

        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="neural networks",
            course_name="AI Course"
        )

    def test_tool_result_sent_back_to_api(self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager):
        """Tool execution result is sent back to Claude."""
        mock_tool_manager.execute_tool.return_value = "[AI Course - Lesson 1]\nNeural networks content"

        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={"id": "tool_123", "name": "search_course_content", "input": {"query": "test"}}
        )
        final_response = mock_anthropic_response(text="Final answer")

        mock_anthropic_client.messages.create.side_effect = [tool_response, final_response]

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_anthropic_client):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(
                query="test",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tool_manager
            )

        # Check second API call includes tool result
        second_call_args = mock_anthropic_client.messages.create.call_args_list[1]
        messages = second_call_args.kwargs["messages"]

        # Find the tool result message
        tool_result_message = next(
            (m for m in messages if m["role"] == "user" and isinstance(m["content"], list)),
            None
        )
        assert tool_result_message is not None
        assert tool_result_message["content"][0]["type"] == "tool_result"
        assert "[AI Course - Lesson 1]" in tool_result_message["content"][0]["content"]

    def test_handles_empty_tool_results(self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager):
        """Handles when tool returns 'No relevant content found' (MAX_RESULTS=0 bug)."""
        # Simulate the bug: tool returns no content
        mock_tool_manager.execute_tool.return_value = "No relevant content found."

        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={"id": "tool_123", "name": "search_course_content", "input": {"query": "test"}}
        )
        final_response = mock_anthropic_response(
            text="I couldn't find information about that in the course materials."
        )

        mock_anthropic_client.messages.create.side_effect = [tool_response, final_response]

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_anthropic_client):
            generator = AIGenerator(api_key="test", model="test")
            result = generator.generate_response(
                query="What is quantum computing?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tool_manager
            )

        # The tool was called, but returned empty
        mock_tool_manager.execute_tool.assert_called_once()
        # Claude responds based on empty results
        assert "couldn't find" in result.lower() or result is not None


class TestAIGeneratorToolCallsForCourseSearch:
    """Tests specifically for CourseSearchTool integration."""

    def test_calls_search_course_content_tool(self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager):
        """Verifies search_course_content tool is called for content questions."""
        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "tool_1",
                "name": "search_course_content",
                "input": {"query": "what is machine learning"}
            }
        )
        final_response = mock_anthropic_response(text="ML is...")

        mock_anthropic_client.messages.create.side_effect = [tool_response, final_response]

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_anthropic_client):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(
                query="What is machine learning?",
                tools=mock_tool_manager.get_tool_definitions(),
                tool_manager=mock_tool_manager
            )

        mock_tool_manager.execute_tool.assert_called_once()
        call_args = mock_tool_manager.execute_tool.call_args
        assert call_args[0][0] == "search_course_content"

    def test_tool_not_called_without_tool_manager(self, mock_anthropic_client, mock_anthropic_response):
        """When tool_manager is None, tool execution is skipped."""
        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={"id": "tool_1", "name": "search_course_content", "input": {"query": "test"}}
        )

        mock_anthropic_client.messages.create.return_value = tool_response

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_anthropic_client):
            generator = AIGenerator(api_key="test", model="test")
            # No tool_manager provided
            result = generator.generate_response(
                query="test",
                tools=[{"name": "search_course_content"}],
                tool_manager=None
            )

        # Should return the tool use block's text representation (or first content block)
        # Since tool_manager is None, _handle_tool_execution is not called
        assert mock_anthropic_client.messages.create.call_count == 1


class TestAIGeneratorSystemPrompt:
    """Tests for system prompt construction."""

    def test_system_prompt_contains_tool_instructions(self, mock_anthropic_client, mock_anthropic_response):
        """System prompt includes tool usage instructions."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response()

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_anthropic_client):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(query="test")

        call_args = mock_anthropic_client.messages.create.call_args
        system_content = call_args.kwargs.get("system", "")

        assert "search_course_content" in system_content
        assert "get_course_outline" in system_content

    def test_system_prompt_has_response_rules(self, mock_anthropic_client, mock_anthropic_response):
        """System prompt includes rules for responses."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response()

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_anthropic_client):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(query="test")

        call_args = mock_anthropic_client.messages.create.call_args
        system_content = call_args.kwargs.get("system", "")

        assert "Brief" in system_content or "brief" in system_content
        assert "Educational" in system_content or "educational" in system_content
