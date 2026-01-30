import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """You are an AI assistant specialized in course materials and educational content.

Available Tools:
1. **search_course_content** - Search lesson content for specific topics or concepts
2. **get_course_outline** - Get course structure with title, link, and all lesson titles

Tool Selection:
- Use **get_course_outline** for: "What lessons are in [course]?", "Show me the outline of [course]", "What topics does [course] cover?", course structure questions
- Use **search_course_content** for: Questions about specific concepts, "How does [course] explain [topic]?", detailed content questions
- Use **no tool** for: General knowledge questions, greetings

Multi-Tool Usage:
- You may use up to **2 tool calls** per query when needed
- Use a second tool call when first search is insufficient or comparing multiple topics
- Example: First get_course_outline to find lesson, then search_course_content for details

Rules:
- If no results found, you may try a different search query or state clearly that no content matches
- **No meta-commentary**: Provide direct answers only, don't mention search results

Responses must be:
1. **Brief and focused**
2. **Educational**
3. **Clear**
4. **Example-supported** when helpful
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude
        response = self.client.messages.create(**api_params)
        
        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)
        
        # Return direct response
        return response.content[0].text
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle iterative tool execution with up to MAX_ROUNDS rounds.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters including tools
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution loop completes
        """
        MAX_ROUNDS = 2
        round_count = 0
        current_response = initial_response
        messages = base_params["messages"].copy()

        while round_count < MAX_ROUNDS:
            # Extract tool_use blocks from response
            tool_use_blocks = [
                block for block in current_response.content
                if block.type == "tool_use"
            ]

            if not tool_use_blocks:
                break

            round_count += 1

            # Add assistant message with full content (may include text + tool_use)
            messages.append({"role": "assistant", "content": current_response.content})

            # Execute all tools and collect results
            tool_results = []
            for block in tool_use_blocks:
                try:
                    result = tool_manager.execute_tool(block.name, **block.input)
                except Exception as e:
                    result = f"Tool execution failed: {str(e)}"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })

            # Add tool results as user message
            messages.append({"role": "user", "content": tool_results})

            # Prepare next API call
            next_params = {
                **self.base_params,
                "messages": messages,
                "system": base_params["system"]
            }

            # Include tools if we haven't hit the limit
            if round_count < MAX_ROUNDS and "tools" in base_params:
                next_params["tools"] = base_params["tools"]
                next_params["tool_choice"] = {"type": "auto"}

            # Make API call
            current_response = self.client.messages.create(**next_params)

            # If Claude stopped for reasons other than tool_use, we're done
            if current_response.stop_reason != "tool_use":
                break

        return self._extract_text_response(current_response)

    def _extract_text_response(self, response) -> str:
        """Extract text content from response, handling mixed content blocks."""
        for block in response.content:
            if hasattr(block, 'text'):
                return block.text
        return "Unable to generate a response."