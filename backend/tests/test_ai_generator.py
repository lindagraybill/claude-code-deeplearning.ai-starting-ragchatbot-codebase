"""Tests for AIGenerator class.

These tests verify that AIGenerator correctly calls the Anthropic API
and properly handles tool use requests from Claude.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from ai_generator import AIGenerator


class TestAIGeneratorInitialization:
    """Tests for AIGenerator initialization."""

    def test_initialization_sets_model(self):
        """AIGenerator stores the model name."""
        with patch("ai_generator.anthropic.Anthropic"):
            generator = AIGenerator(api_key="test-key", model="test-model")
            assert generator.model == "test-model"

    def test_initialization_creates_client(self):
        """AIGenerator creates an Anthropic client."""
        with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
            generator = AIGenerator(api_key="test-key", model="test-model")
            MockAnthropic.assert_called_once_with(api_key="test-key")

    def test_base_params_set_correctly(self):
        """AIGenerator sets base API parameters."""
        with patch("ai_generator.anthropic.Anthropic"):
            generator = AIGenerator(api_key="test-key", model="claude-test")

            assert generator.base_params["model"] == "claude-test"
            assert generator.base_params["temperature"] == 0
            assert generator.base_params["max_tokens"] == 800


class TestAIGeneratorDirectResponse:
    """Tests for AIGenerator.generate_response() without tool use."""

    def test_direct_response_without_tools(
        self, mock_anthropic_client, mock_anthropic_response
    ):
        """Returns text directly when no tools provided."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response(
            text="Hello! How can I help you?"
        )

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            result = generator.generate_response(query="Hello")

        assert result == "Hello! How can I help you?"
        mock_anthropic_client.messages.create.assert_called_once()

    def test_direct_response_with_tools_not_used(
        self, mock_anthropic_client, mock_anthropic_response
    ):
        """Returns text when tools provided but Claude doesn't use them."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response(
            text="I can answer that directly.", stop_reason="end_turn"
        )

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            tools = [{"name": "search_course_content", "input_schema": {}}]
            result = generator.generate_response(query="What is 2+2?", tools=tools)

        assert result == "I can answer that directly."

    def test_conversation_history_included(
        self, mock_anthropic_client, mock_anthropic_response
    ):
        """Conversation history is appended to system prompt."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response()

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(
                query="Follow up question",
                conversation_history="User: Hi\nAssistant: Hello!",
            )

        call_args = mock_anthropic_client.messages.create.call_args
        system_content = call_args.kwargs.get("system", "")
        assert "Previous conversation:" in system_content
        assert "User: Hi" in system_content


class TestAIGeneratorToolExecution:
    """Tests for AIGenerator handling tool use requests."""

    def test_detects_tool_use_stop_reason(
        self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager
    ):
        """Detects when Claude requests tool use."""
        # First call returns tool use request
        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "tool_123",
                "name": "search_course_content",
                "input": {"query": "machine learning"},
            },
        )

        # Second call returns final response
        final_response = mock_anthropic_response(text="Based on my search...")

        mock_anthropic_client.messages.create.side_effect = [
            tool_response,
            final_response,
        ]

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            tools = [{"name": "search_course_content", "input_schema": {}}]
            result = generator.generate_response(
                query="What is ML?", tools=tools, tool_manager=mock_tool_manager
            )

        # Verify two API calls were made
        assert mock_anthropic_client.messages.create.call_count == 2
        assert result == "Based on my search..."

    def test_executes_tool_via_tool_manager(
        self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager
    ):
        """Executes tool through ToolManager with correct parameters."""
        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "tool_123",
                "name": "search_course_content",
                "input": {"query": "neural networks", "course_name": "AI Course"},
            },
        )
        final_response = mock_anthropic_response(text="Here's what I found...")

        mock_anthropic_client.messages.create.side_effect = [
            tool_response,
            final_response,
        ]

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(
                query="Search for neural networks",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tool_manager,
            )

        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="neural networks", course_name="AI Course"
        )

    def test_tool_result_sent_back_to_api(
        self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager
    ):
        """Tool execution result is sent back to Claude."""
        mock_tool_manager.execute_tool.return_value = (
            "[AI Course - Lesson 1]\nNeural networks content"
        )

        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "tool_123",
                "name": "search_course_content",
                "input": {"query": "test"},
            },
        )
        final_response = mock_anthropic_response(text="Final answer")

        mock_anthropic_client.messages.create.side_effect = [
            tool_response,
            final_response,
        ]

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(
                query="test",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tool_manager,
            )

        # Check second API call includes tool result
        second_call_args = mock_anthropic_client.messages.create.call_args_list[1]
        messages = second_call_args.kwargs["messages"]

        # Find the tool result message
        tool_result_message = next(
            (
                m
                for m in messages
                if m["role"] == "user" and isinstance(m["content"], list)
            ),
            None,
        )
        assert tool_result_message is not None
        assert tool_result_message["content"][0]["type"] == "tool_result"
        assert "[AI Course - Lesson 1]" in tool_result_message["content"][0]["content"]

    def test_handles_empty_tool_results(
        self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager
    ):
        """Handles when tool returns 'No relevant content found' (MAX_RESULTS=0 bug)."""
        # Simulate the bug: tool returns no content
        mock_tool_manager.execute_tool.return_value = "No relevant content found."

        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "tool_123",
                "name": "search_course_content",
                "input": {"query": "test"},
            },
        )
        final_response = mock_anthropic_response(
            text="I couldn't find information about that in the course materials."
        )

        mock_anthropic_client.messages.create.side_effect = [
            tool_response,
            final_response,
        ]

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            result = generator.generate_response(
                query="What is quantum computing?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tool_manager,
            )

        # The tool was called, but returned empty
        mock_tool_manager.execute_tool.assert_called_once()
        # Claude responds based on empty results
        assert "couldn't find" in result.lower() or result is not None


class TestAIGeneratorToolCallsForCourseSearch:
    """Tests specifically for CourseSearchTool integration."""

    def test_calls_search_course_content_tool(
        self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager
    ):
        """Verifies search_course_content tool is called for content questions."""
        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "tool_1",
                "name": "search_course_content",
                "input": {"query": "what is machine learning"},
            },
        )
        final_response = mock_anthropic_response(text="ML is...")

        mock_anthropic_client.messages.create.side_effect = [
            tool_response,
            final_response,
        ]

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(
                query="What is machine learning?",
                tools=mock_tool_manager.get_tool_definitions(),
                tool_manager=mock_tool_manager,
            )

        mock_tool_manager.execute_tool.assert_called_once()
        call_args = mock_tool_manager.execute_tool.call_args
        assert call_args[0][0] == "search_course_content"

    def test_tool_not_called_without_tool_manager(
        self, mock_anthropic_client, mock_anthropic_response
    ):
        """When tool_manager is None, tool execution is skipped."""
        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "tool_1",
                "name": "search_course_content",
                "input": {"query": "test"},
            },
        )

        mock_anthropic_client.messages.create.return_value = tool_response

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            # No tool_manager provided
            result = generator.generate_response(
                query="test",
                tools=[{"name": "search_course_content"}],
                tool_manager=None,
            )

        # Should return the tool use block's text representation (or first content block)
        # Since tool_manager is None, _handle_tool_execution is not called
        assert mock_anthropic_client.messages.create.call_count == 1


class TestAIGeneratorSystemPrompt:
    """Tests for system prompt construction."""

    def test_system_prompt_contains_tool_instructions(
        self, mock_anthropic_client, mock_anthropic_response
    ):
        """System prompt includes tool usage instructions."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response()

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(query="test")

        call_args = mock_anthropic_client.messages.create.call_args
        system_content = call_args.kwargs.get("system", "")

        assert "search_course_content" in system_content
        assert "get_course_outline" in system_content

    def test_system_prompt_has_response_rules(
        self, mock_anthropic_client, mock_anthropic_response
    ):
        """System prompt includes rules for responses."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response()

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(query="test")

        call_args = mock_anthropic_client.messages.create.call_args
        system_content = call_args.kwargs.get("system", "")

        assert "Brief" in system_content or "brief" in system_content
        assert "Educational" in system_content or "educational" in system_content

    def test_system_prompt_allows_multi_tool_usage(
        self, mock_anthropic_client, mock_anthropic_response
    ):
        """System prompt includes multi-tool usage guidance."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response()

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(query="test")

        call_args = mock_anthropic_client.messages.create.call_args
        system_content = call_args.kwargs.get("system", "")

        assert "2 tool calls" in system_content
        assert "Multi-Tool Usage" in system_content


class TestSequentialToolExecution:
    """Tests for sequential tool calling (up to 2 rounds)."""

    def test_two_sequential_tool_calls(
        self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager
    ):
        """Supports two rounds of tool calls with 3 API calls total."""
        # Round 1: Claude requests first search
        round1_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "t1",
                "name": "get_course_outline",
                "input": {"course_name": "AI"},
            },
        )
        # Round 2: Claude requests second search after seeing first results
        round2_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "t2",
                "name": "search_course_content",
                "input": {"query": "lesson 2"},
            },
        )
        # Final: Claude provides answer
        final_response = mock_anthropic_response(text="Based on both searches...")

        mock_anthropic_client.messages.create.side_effect = [
            round1_response,
            round2_response,
            final_response,
        ]

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            result = generator.generate_response(
                query="What is in lesson 2 of AI course?",
                tools=[
                    {"name": "search_course_content"},
                    {"name": "get_course_outline"},
                ],
                tool_manager=mock_tool_manager,
            )

        # Verify 3 API calls (initial + 2 tool rounds)
        assert mock_anthropic_client.messages.create.call_count == 3
        # Verify both tools were executed
        assert mock_tool_manager.execute_tool.call_count == 2
        assert result == "Based on both searches..."

    def test_stops_after_max_rounds(
        self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager
    ):
        """Terminates after max rounds even if Claude requests more tools."""
        # Claude keeps requesting tools (would be 3 rounds if allowed)
        tool_response1 = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "t1",
                "name": "search_course_content",
                "input": {"query": "test1"},
            },
        )
        tool_response2 = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "t2",
                "name": "search_course_content",
                "input": {"query": "test2"},
            },
        )
        # Third response - tools not included so Claude must respond with text
        final_response = mock_anthropic_response(text="Final after max rounds")

        mock_anthropic_client.messages.create.side_effect = [
            tool_response1,
            tool_response2,
            final_response,
        ]

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            result = generator.generate_response(
                query="test",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tool_manager,
            )

        # 2 tool executions (max rounds)
        assert mock_tool_manager.execute_tool.call_count == 2
        assert result == "Final after max rounds"

    def test_stops_when_no_tool_use(
        self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager
    ):
        """Stops early when Claude responds without requesting tools."""
        # First call uses tool
        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "t1",
                "name": "search_course_content",
                "input": {"query": "test"},
            },
        )
        # Second call - Claude has enough info, responds directly
        final_response = mock_anthropic_response(
            text="I found the answer.", stop_reason="end_turn"
        )

        mock_anthropic_client.messages.create.side_effect = [
            tool_response,
            final_response,
        ]

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            result = generator.generate_response(
                query="test",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tool_manager,
            )

        # Only 1 tool execution, then Claude stopped
        assert mock_tool_manager.execute_tool.call_count == 1
        assert mock_anthropic_client.messages.create.call_count == 2
        assert result == "I found the answer."

    def test_tools_included_in_second_round(
        self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager
    ):
        """Verifies tools are included in the second API call."""
        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "t1",
                "name": "search_course_content",
                "input": {"query": "test"},
            },
        )
        final_response = mock_anthropic_response(text="Done")

        mock_anthropic_client.messages.create.side_effect = [
            tool_response,
            final_response,
        ]
        tools = [{"name": "search_course_content", "input_schema": {}}]

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(
                query="test", tools=tools, tool_manager=mock_tool_manager
            )

        # Check second call includes tools
        second_call = mock_anthropic_client.messages.create.call_args_list[1]
        assert "tools" in second_call.kwargs
        assert second_call.kwargs["tools"] == tools

    def test_conversation_preserved_between_rounds(
        self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager
    ):
        """Verifies message history accumulates correctly through rounds."""
        mock_tool_manager.execute_tool.side_effect = [
            "[Course A] First search results",
            "[Course B] Second search results",
        ]

        round1 = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "t1",
                "name": "search_course_content",
                "input": {"query": "topic A"},
            },
        )
        round2 = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "t2",
                "name": "search_course_content",
                "input": {"query": "topic B"},
            },
        )
        final = mock_anthropic_response(text="Combined answer")

        mock_anthropic_client.messages.create.side_effect = [round1, round2, final]

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            generator.generate_response(
                query="Compare A and B",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tool_manager,
            )

        # Check third call has accumulated messages
        third_call = mock_anthropic_client.messages.create.call_args_list[2]
        messages = third_call.kwargs["messages"]

        # Should have: user, assistant(tool_use), user(tool_result), assistant(tool_use), user(tool_result)
        assert len(messages) == 5
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"  # tool_result
        assert messages[3]["role"] == "assistant"
        assert messages[4]["role"] == "user"  # tool_result

    def test_tool_execution_error_continues(
        self, mock_anthropic_client, mock_anthropic_response, mock_tool_manager
    ):
        """Handles tool execution failures gracefully and continues."""
        mock_tool_manager.execute_tool.side_effect = Exception(
            "Database connection failed"
        )

        tool_response = mock_anthropic_response(
            stop_reason="tool_use",
            tool_use={
                "id": "t1",
                "name": "search_course_content",
                "input": {"query": "test"},
            },
        )
        final_response = mock_anthropic_response(
            text="I encountered an issue searching the materials."
        )

        mock_anthropic_client.messages.create.side_effect = [
            tool_response,
            final_response,
        ]

        with patch(
            "ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client
        ):
            generator = AIGenerator(api_key="test", model="test")
            result = generator.generate_response(
                query="test",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tool_manager,
            )

        # Check error was passed to Claude in tool_result
        second_call = mock_anthropic_client.messages.create.call_args_list[1]
        tool_result_msg = second_call.kwargs["messages"][-1]
        assert tool_result_msg["role"] == "user"
        assert "Tool execution failed" in tool_result_msg["content"][0]["content"]

        # Should still get a response
        assert result == "I encountered an issue searching the materials."
