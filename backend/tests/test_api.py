"""Tests for FastAPI endpoints.

These tests verify the API layer handles requests/responses correctly,
using a test app that defines endpoints inline to avoid static file issues.
"""
import pytest
from httpx import AsyncClient, ASGITransport


class TestQueryEndpoint:
    """Tests for POST /api/query endpoint."""

    @pytest.mark.asyncio
    async def test_query_returns_successful_response(self, test_app, mock_rag_system):
        """Query endpoint returns answer and sources."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query",
                json={"query": "What is machine learning?"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["answer"] == "This is a test response about machine learning."

    @pytest.mark.asyncio
    async def test_query_creates_session_when_not_provided(self, test_app, mock_rag_system):
        """Query endpoint creates a new session if none provided."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query",
                json={"query": "Test query"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        mock_rag_system.session_manager.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_uses_provided_session_id(self, test_app, mock_rag_system):
        """Query endpoint uses the provided session_id."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query",
                json={"query": "Follow up question", "session_id": "existing-session"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "existing-session"
        mock_rag_system.query.assert_called_with("Follow up question", "existing-session")

    @pytest.mark.asyncio
    async def test_query_returns_sources_with_links(self, test_app):
        """Query endpoint includes source links in response."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query",
                json={"query": "What is deep learning?"}
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "Introduction to AI - Lesson 1"
        assert data["sources"][0]["link"] == "https://example.com/lesson/1"

    @pytest.mark.asyncio
    async def test_query_handles_empty_query(self, test_app):
        """Query endpoint handles empty query gracefully."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query",
                json={"query": ""}
            )

        # Empty query should still be processed (business logic decides response)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_query_returns_500_on_rag_system_error(self, test_app, mock_rag_system):
        """Query endpoint returns 500 when RAG system raises exception."""
        mock_rag_system.query.side_effect = Exception("Internal error")

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query",
                json={"query": "What causes an error?"}
            )

        assert response.status_code == 500
        assert "Internal error" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_query_validates_request_body(self, test_app):
        """Query endpoint validates request body schema."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing required 'query' field
            response = await client.post(
                "/api/query",
                json={}
            )

        assert response.status_code == 422  # Validation error


class TestCoursesEndpoint:
    """Tests for GET /api/courses endpoint."""

    @pytest.mark.asyncio
    async def test_courses_returns_stats(self, test_app):
        """Courses endpoint returns course statistics."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 3
        assert len(data["course_titles"]) == 3
        assert "Introduction to AI" in data["course_titles"]

    @pytest.mark.asyncio
    async def test_courses_returns_all_course_titles(self, test_app):
        """Courses endpoint returns all course titles."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/courses")

        data = response.json()
        expected_titles = ["Introduction to AI", "Deep Learning", "NLP Fundamentals"]
        assert data["course_titles"] == expected_titles

    @pytest.mark.asyncio
    async def test_courses_returns_500_on_error(self, test_app, mock_rag_system):
        """Courses endpoint returns 500 when analytics fails."""
        mock_rag_system.get_course_analytics.side_effect = Exception("Database error")

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/courses")

        assert response.status_code == 500
        assert "Database error" in response.json()["detail"]


class TestRootEndpoint:
    """Tests for GET / endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_ok_status(self, test_app):
        """Root endpoint returns OK status."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestCORSHeaders:
    """Tests for CORS middleware configuration."""

    @pytest.mark.asyncio
    async def test_cors_allows_all_origins(self, test_app):
        """CORS middleware allows requests from any origin."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.options(
                "/api/query",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST"
                }
            )

        # OPTIONS request should succeed
        assert response.status_code == 200


class TestRequestValidation:
    """Tests for request validation and error handling."""

    @pytest.mark.asyncio
    async def test_invalid_json_returns_422(self, test_app):
        """Invalid JSON body returns 422 error."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query",
                content="not valid json",
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_wrong_content_type_returns_422(self, test_app):
        """Wrong content type returns 422 error."""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query",
                content="query=test",
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

        assert response.status_code == 422
