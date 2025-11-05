"""Tests for the Jira Search mixin."""

from unittest.mock import ANY, MagicMock

import pytest
import requests

from mcp_atlassian.jira import JiraFetcher
from mcp_atlassian.jira.search import SearchMixin
from mcp_atlassian.models.jira import JiraIssue, JiraSearchResult


class TestSearchMixin:
    """Tests for the SearchMixin class."""

    @pytest.fixture
    def search_mixin(self, jira_fetcher: JiraFetcher) -> SearchMixin:
        """Create a SearchMixin instance with mocked dependencies."""
        mixin = jira_fetcher

        # Mock methods that are typically provided by other mixins
        mixin._clean_text = MagicMock(side_effect=lambda text: text if text else "")

        # Set config with is_cloud=False by default (Server/DC)
        mixin.config = MagicMock()
        mixin.config.is_cloud = False
        mixin.config.projects_filter = None
        mixin.config.url = "https://example.atlassian.net"

        return mixin

    @pytest.fixture
    def mock_issues_response(self) -> dict:
        """Create a mock Jira issues response for testing."""
        return {
            "issues": [
                {
                    "id": "10001",
                    "key": "TEST-123",
                    "fields": {
                        "summary": "Test issue",
                        "issuetype": {"name": "Bug"},
                        "status": {"name": "Open"},
                        "description": "Test description",
                        "created": "2024-01-01T10:00:00.000+0000",
                        "updated": "2024-01-01T11:00:00.000+0000",
                    },
                }
            ],
            "total": 1,
            "startAt": 0,
            "maxResults": 50,
        }

    @pytest.mark.parametrize(
        "is_cloud, expected_method_name",
        [
            (True, "post"),  # Cloud uses new /search/jql endpoint
            (False, "jql"),  # Server/DC uses old jql method
        ],
    )
    def test_search_issues_calls_correct_method(
        self,
        search_mixin: SearchMixin,
        mock_issues_response,
        is_cloud,
        expected_method_name,
    ):
        """Test that the correct Jira API method is called based on Cloud/Server setting."""
        # Setup: Mock config.is_cloud
        search_mixin.config.is_cloud = is_cloud
        search_mixin.config.projects_filter = None  # No filter for this test
        search_mixin.config.url = (
            "https://test.example.com"  # Model creation needs this
        )

        # Setup: Mock response based on is_cloud
        if is_cloud:
            search_mixin.jira.post = MagicMock(return_value=mock_issues_response)
        else:
            search_mixin.jira.jql = MagicMock(return_value=mock_issues_response)

        # Act
        jql_query = "project = TEST"
        result = search_mixin.search_issues(jql_query, limit=10, start=0)

        # Assert: Basic result verification
        assert isinstance(result, JiraSearchResult)
        assert len(result.issues) > 0  # Based on mocked response

        # Assert: Correct method call verification
        if is_cloud:
            search_mixin.jira.post.assert_called_once_with(
                "rest/api/3/search/jql", json=ANY
            )
        else:
            search_mixin.jira.jql.assert_called_once_with(
                jql=jql_query, fields=ANY, start=0, limit=10, expand=None
            )

    def test_search_issues_basic(self, search_mixin: SearchMixin):
        """Test basic search functionality."""
        # Setup mock response
        mock_issues = {
            "issues": [
                {
                    "id": "10001",
                    "key": "TEST-123",
                    "fields": {
                        "summary": "Test issue",
                        "issuetype": {"name": "Bug"},
                        "status": {"name": "Open"},
                        "description": "Issue description",
                        "created": "2024-01-01T10:00:00.000+0000",
                        "updated": "2024-01-01T11:00:00.000+0000",
                        "priority": {"name": "High"},
                    },
                }
            ],
            "total": 1,
            "startAt": 0,
            "maxResults": 50,
            "isLast": True,  # Add for Cloud API compatibility
        }

        # Mock based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post = MagicMock(return_value=mock_issues)
        else:
            search_mixin.jira.jql = MagicMock(return_value=mock_issues)

        # Call the method
        result = search_mixin.search_issues("project = TEST")

        # Verify based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post.assert_called_once_with(
                "rest/api/3/search/jql", json=ANY
            )
        else:
            search_mixin.jira.jql.assert_called_once_with(
                jql="project = TEST",
                fields=ANY,
                start=0,
                limit=50,
                expand=None,
            )

        # Verify results
        assert isinstance(result, JiraSearchResult)
        assert len(result.issues) == 1
        assert all(isinstance(issue, JiraIssue) for issue in result.issues)
        assert result.total == 1
        assert result.start_at == 0
        assert result.max_results == 50

        # Check the first issue
        issue = result.issues[0]
        assert issue.key == "TEST-123"
        assert issue.summary == "Test issue"
        assert issue.description == "Issue description"
        assert issue.status is not None
        assert issue.status.name == "Open"
        assert issue.issue_type is not None
        assert issue.issue_type.name == "Bug"
        assert issue.priority is not None
        assert issue.priority.name == "High"

        # Remove backward compatibility checks
        assert "Issue description" in issue.description
        assert issue.key == "TEST-123"

    def test_search_issues_with_empty_description(self, search_mixin: SearchMixin):
        """Test search with issues that have no description."""
        # Setup mock response
        mock_issues = {
            "issues": [
                {
                    "id": "10001",
                    "key": "TEST-123",
                    "fields": {
                        "summary": "Test issue",
                        "issuetype": {"name": "Bug"},
                        "status": {"name": "Open"},
                        "description": None,
                        "created": "2024-01-01T10:00:00.000+0000",
                        "updated": "2024-01-01T11:00:00.000+0000",
                    },
                }
            ],
            "total": 1,
            "startAt": 0,
            "maxResults": 50,
            "isLast": True,  # Add for Cloud API compatibility
        }

        # Mock based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post = MagicMock(return_value=mock_issues)
        else:
            search_mixin.jira.jql = MagicMock(return_value=mock_issues)

        # Call the method
        result = search_mixin.search_issues("project = TEST")

        # Verify results
        assert len(result.issues) == 1
        assert isinstance(result.issues[0], JiraIssue)
        assert result.issues[0].key == "TEST-123"
        assert result.issues[0].description is None
        assert result.issues[0].summary == "Test issue"

        # Update to use direct properties instead of backward compatibility
        assert "Test issue" in result.issues[0].summary

    def test_search_issues_with_missing_fields(self, search_mixin: SearchMixin):
        """Test search with issues missing some fields."""
        # Setup mock response
        mock_issues = {
            "issues": [
                {
                    "key": "TEST-123",
                    "fields": {
                        "summary": "Test issue",
                        # Missing issuetype, status, etc.
                    },
                }
            ],
            "total": 1,
            "startAt": 0,
            "maxResults": 50,
            "isLast": True,  # Add for Cloud API compatibility
        }

        # Mock based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post = MagicMock(return_value=mock_issues)
        else:
            search_mixin.jira.jql = MagicMock(return_value=mock_issues)

        # Call the method
        result = search_mixin.search_issues("project = TEST")

        # Verify results
        assert len(result.issues) == 1
        assert isinstance(result.issues[0], JiraIssue)
        assert result.issues[0].key == "TEST-123"
        assert result.issues[0].summary == "Test issue"
        assert result.issues[0].status is None
        assert result.issues[0].issue_type is None

    def test_search_issues_with_empty_results(self, search_mixin: SearchMixin):
        """Test search with no results."""
        # Setup mock response for empty results
        empty_response = {
            "issues": [],
            "total": 0,
            "startAt": 0,
            "maxResults": 50,
            "isLast": True,  # Add for Cloud API compatibility
        }

        # Mock based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post = MagicMock(return_value=empty_response)
        else:
            search_mixin.jira.jql = MagicMock(return_value={"issues": []})

        # Call the method
        result = search_mixin.search_issues("project = NONEXISTENT")

        # Verify results
        assert isinstance(result, JiraSearchResult)
        assert len(result.issues) == 0
        # For Cloud, total should be 0; for Server/DC, it defaults to -1 when not provided
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            assert result.total == 0
        else:
            assert result.total == -1

    def test_search_issues_with_error(self, search_mixin: SearchMixin):
        """Test search with API error."""
        # Setup mock to raise exception based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post = MagicMock(side_effect=Exception("API Error"))
        else:
            search_mixin.jira.jql = MagicMock(side_effect=Exception("API Error"))

        # Call the method and verify it raises the expected exception
        with pytest.raises(Exception, match="Error searching issues"):
            search_mixin.search_issues("project = TEST")

    def test_search_issues_with_projects_filter(self, search_mixin: SearchMixin):
        """Test search with projects filter."""
        # Setup mock response
        mock_issues = {
            "issues": [
                {
                    "id": "10001",
                    "key": "TEST-123",
                    "fields": {
                        "summary": "Test issue",
                        "issuetype": {"name": "Bug"},
                        "status": {"name": "Open"},
                    },
                }
            ],
            "total": 1,
            "startAt": 0,
            "maxResults": 50,
            "isLast": True,  # Add for Cloud API compatibility
        }

        # Mock based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post = MagicMock(return_value=mock_issues)
        else:
            search_mixin.jira.jql = MagicMock(return_value=mock_issues)
        search_mixin.config.url = "https://example.atlassian.net"

        # Test with single project filter
        result = search_mixin.search_issues("text ~ 'test'", projects_filter="TEST")

        # Verify based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == "(text ~ 'test') AND project = \"TEST\""
        else:
            search_mixin.jira.jql.assert_called_with(
                jql="(text ~ 'test') AND project = \"TEST\"",
                fields=ANY,
                start=0,
                limit=50,
                expand=None,
            )
        assert len(result.issues) == 1
        assert result.total == 1

        # Reset mock for next call
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post.reset_mock()
        else:
            search_mixin.jira.jql.reset_mock()

        # Test with multiple project filter
        result = search_mixin.search_issues("text ~ 'test'", projects_filter="TEST,DEV")

        # Verify based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == '(text ~ \'test\') AND project IN ("TEST", "DEV")'
        else:
            search_mixin.jira.jql.assert_called_with(
                jql='(text ~ \'test\') AND project IN ("TEST", "DEV")',
                fields=ANY,
                start=0,
                limit=50,
                expand=None,
            )
        assert len(result.issues) == 1
        assert result.total == 1

    def test_search_issues_with_config_projects_filter(self, search_mixin: SearchMixin):
        """Test search with projects filter from config."""
        # Setup mock response
        mock_issues = {
            "issues": [
                {
                    "id": "10001",
                    "key": "TEST-123",
                    "fields": {
                        "summary": "Test issue",
                        "issuetype": {"name": "Bug"},
                        "status": {"name": "Open"},
                    },
                }
            ],
            "total": 1,
            "startAt": 0,
            "maxResults": 50,
            "isLast": True,  # Add for Cloud API compatibility
        }

        # Mock based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post = MagicMock(return_value=mock_issues)
        else:
            search_mixin.jira.jql = MagicMock(return_value=mock_issues)
        search_mixin.config.url = "https://example.atlassian.net"
        search_mixin.config.projects_filter = "TEST,DEV"

        # Test with config filter
        result = search_mixin.search_issues("text ~ 'test'")

        # Verify based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == '(text ~ \'test\') AND project IN ("TEST", "DEV")'
        else:
            search_mixin.jira.jql.assert_called_with(
                jql='(text ~ \'test\') AND project IN ("TEST", "DEV")',
                fields=ANY,
                start=0,
                limit=50,
                expand=None,
            )
        assert len(result.issues) == 1
        assert result.total == 1

        # Reset mock for next call
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post.reset_mock()
        else:
            search_mixin.jira.jql.reset_mock()

        # Test with override
        result = search_mixin.search_issues("text ~ 'test'", projects_filter="OVERRIDE")

        # Verify based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == "(text ~ 'test') AND project = \"OVERRIDE\""
        else:
            search_mixin.jira.jql.assert_called_with(
                jql="(text ~ 'test') AND project = \"OVERRIDE\"",
                fields=ANY,
                start=0,
                limit=50,
                expand=None,
            )
        assert len(result.issues) == 1
        assert result.total == 1

        # Reset mock for next call
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post.reset_mock()
        else:
            search_mixin.jira.jql.reset_mock()

        # Test with override - multiple projects
        result = search_mixin.search_issues(
            "text ~ 'test'", projects_filter="OVER1,OVER2"
        )

        # Verify based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert (
                payload["jql"] == '(text ~ \'test\') AND project IN ("OVER1", "OVER2")'
            )
        else:
            search_mixin.jira.jql.assert_called_with(
                jql='(text ~ \'test\') AND project IN ("OVER1", "OVER2")',
                fields=ANY,
                start=0,
                limit=50,
                expand=None,
            )
        assert len(result.issues) == 1
        assert result.total == 1

    def test_search_issues_with_fields_parameter(self, search_mixin: SearchMixin):
        """Test search with specific fields parameter, including custom fields."""
        # Setup mock response with a custom field
        mock_issues = {
            "issues": [
                {
                    "id": "10001",
                    "key": "TEST-123",
                    "fields": {
                        "summary": "Test issue with custom field",
                        "assignee": {
                            "displayName": "Test User",
                            "emailAddress": "test@example.com",
                            "active": True,
                        },
                        "customfield_10049": "Custom value",
                        "issuetype": {"name": "Bug"},
                        "status": {"name": "Open"},
                        "description": "Issue description",
                        "created": "2024-01-01T10:00:00.000+0000",
                        "updated": "2024-01-01T11:00:00.000+0000",
                        "priority": {"name": "High"},
                    },
                }
            ],
            "total": 1,
            "startAt": 0,
            "maxResults": 50,
            "isLast": True,  # Add for Cloud API compatibility
        }

        # Mock based on is_cloud setting
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post = MagicMock(return_value=mock_issues)
        else:
            search_mixin.jira.jql = MagicMock(return_value=mock_issues)
        search_mixin.config.url = "https://example.atlassian.net"

        # Call the method with specific fields
        result = search_mixin.search_issues(
            "project = TEST", fields="summary,assignee,customfield_10049"
        )

        # Verify the API call includes the fields parameter
        if hasattr(search_mixin.config, "is_cloud") and search_mixin.config.is_cloud:
            search_mixin.jira.post.assert_called_once_with(
                "rest/api/3/search/jql", json=ANY
            )
            # Check the fields in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["fields"] == ["summary", "assignee", "customfield_10049"]
        else:
            search_mixin.jira.jql.assert_called_once_with(
                jql="project = TEST",
                fields="summary,assignee,customfield_10049",
                start=0,
                limit=50,
                expand=None,
            )

        # Verify results
        assert isinstance(result, JiraSearchResult)
        assert len(result.issues) == 1
        issue = result.issues[0]

        # Convert to simplified dict to check field filtering
        simplified = issue.to_simplified_dict()

        # These fields should be included (plus id and key which are always included)
        assert "id" in simplified
        assert "key" in simplified
        assert "summary" in simplified
        assert "assignee" in simplified
        assert "customfield_10049" in simplified

        assert simplified["customfield_10049"] == {"value": "Custom value"}
        assert "assignee" in simplified
        assert simplified["assignee"]["display_name"] == "Test User"

    def test_get_board_issues(self, search_mixin: SearchMixin):
        """Test get_board_issues method."""
        mock_issues = {
            "issues": [
                {
                    "id": "10001",
                    "key": "TEST-123",
                    "fields": {
                        "summary": "Test issue",
                        "issuetype": {"name": "Bug"},
                        "status": {"name": "Open"},
                        "description": "Issue description",
                        "created": "2024-01-01T10:00:00.000+0000",
                        "updated": "2024-01-01T11:00:00.000+0000",
                        "priority": {"name": "High"},
                    },
                }
            ],
            "total": 1,
            "startAt": 0,
            "maxResults": 50,
        }
        search_mixin.jira.get_issues_for_board.return_value = mock_issues

        # Call the method
        result = search_mixin.get_board_issues("1000", jql="", limit=20)

        # Verify results
        assert isinstance(result, JiraSearchResult)
        assert len(result.issues) == 1
        assert all(isinstance(issue, JiraIssue) for issue in result.issues)
        assert result.total == 1
        assert result.start_at == 0
        assert result.max_results == 50

        # Check the first issue
        issue = result.issues[0]
        assert issue.key == "TEST-123"
        assert issue.summary == "Test issue"
        assert issue.description == "Issue description"
        assert issue.status is not None
        assert issue.status.name == "Open"
        assert issue.issue_type is not None
        assert issue.issue_type.name == "Bug"
        assert issue.priority is not None
        assert issue.priority.name == "High"

        # Remove backward compatibility checks
        assert "Issue description" in issue.description
        assert issue.key == "TEST-123"

    def test_get_board_issues_exception(self, search_mixin: SearchMixin):
        search_mixin.jira.get_issues_for_board.side_effect = Exception("API Error")

        with pytest.raises(Exception) as e:
            search_mixin.get_board_issues("1000", jql="", limit=20)
        assert "API Error" in str(e.value)

    def test_get_board_issues_http_error(self, search_mixin: SearchMixin):
        search_mixin.jira.get_issues_for_board.side_effect = requests.HTTPError(
            response=MagicMock(content="API Error content")
        )

        with pytest.raises(Exception) as e:
            search_mixin.get_board_issues("1000", jql="", limit=20)
        assert "API Error content" in str(e.value)

    def test_get_sprint_issues(self, search_mixin: SearchMixin):
        """Test get_sprint_issues method."""
        mock_issues = {
            "issues": [
                {
                    "id": "10001",
                    "key": "TEST-123",
                    "fields": {
                        "summary": "Test issue",
                        "issuetype": {"name": "Bug"},
                        "status": {"name": "Open"},
                        "description": "Issue description",
                        "created": "2024-01-01T10:00:00.000+0000",
                        "updated": "2024-01-01T11:00:00.000+0000",
                        "priority": {"name": "High"},
                    },
                }
            ],
            "total": 1,
            "startAt": 0,
            "maxResults": 50,
        }
        search_mixin.jira.get_sprint_issues.return_value = mock_issues

        # Call the method
        result = search_mixin.get_sprint_issues("10001")

        # Verify results
        assert isinstance(result, JiraSearchResult)
        assert len(result.issues) == 1
        assert all(isinstance(issue, JiraIssue) for issue in result.issues)
        assert result.total == 1
        assert result.start_at == 0
        assert result.max_results == 50

        # Check the first issue
        issue = result.issues[0]
        assert issue.key == "TEST-123"
        assert issue.summary == "Test issue"
        assert issue.description == "Issue description"
        assert issue.status is not None
        assert issue.status.name == "Open"
        assert issue.issue_type is not None
        assert issue.issue_type.name == "Bug"
        assert issue.priority is not None
        assert issue.priority.name == "High"

    def test_get_sprint_issues_exception(self, search_mixin: SearchMixin):
        search_mixin.jira.get_sprint_issues.side_effect = Exception("API Error")

        with pytest.raises(Exception) as e:
            search_mixin.get_sprint_issues("10001")
        assert "API Error" in str(e.value)

    def test_get_sprint_issues_http_error(self, search_mixin: SearchMixin):
        search_mixin.jira.get_sprint_issues.side_effect = requests.HTTPError(
            response=MagicMock(content="API Error content")
        )

        with pytest.raises(Exception) as e:
            search_mixin.get_sprint_issues("10001")
        assert "API Error content" in str(e.value)

    @pytest.mark.parametrize("is_cloud", [True, False])
    def test_search_issues_with_projects_filter_jql_construction(
        self, search_mixin: SearchMixin, mock_issues_response, is_cloud
    ):
        """Test that JQL string is correctly constructed when projects_filter is provided."""
        # Setup
        search_mixin.config.is_cloud = is_cloud
        search_mixin.config.projects_filter = (
            None  # Don't use config filter for this test
        )
        search_mixin.config.url = "https://test.example.com"

        # Add isLast for Cloud API compatibility
        mock_issues_response["isLast"] = True

        # Setup mock response for both API methods
        if is_cloud:
            search_mixin.jira.post = MagicMock(return_value=mock_issues_response)
        else:
            search_mixin.jira.jql = MagicMock(return_value=mock_issues_response)

        # Act: Single project filter
        search_mixin.search_issues("text ~ 'test'", projects_filter="TEST")

        # Assert: JQL verification
        if is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == "(text ~ 'test') AND project = \"TEST\""
        else:
            search_mixin.jira.jql.assert_called_with(
                jql="(text ~ 'test') AND project = \"TEST\"",
                fields=ANY,
                start=ANY,
                limit=ANY,
                expand=ANY,
            )

        # Reset mock for next call
        if is_cloud:
            search_mixin.jira.post.reset_mock()
        else:
            search_mixin.jira.jql.reset_mock()

        # Act: Multiple projects filter
        search_mixin.search_issues("text ~ 'test'", projects_filter="TEST, DEV")

        # Assert: JQL verification
        if is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == '(text ~ \'test\') AND project IN ("TEST", "DEV")'
        else:
            search_mixin.jira.jql.assert_called_with(
                jql='(text ~ \'test\') AND project IN ("TEST", "DEV")',
                fields=ANY,
                start=ANY,
                limit=ANY,
                expand=ANY,
            )

        # Reset mock for next call
        if is_cloud:
            search_mixin.jira.post.reset_mock()
        else:
            search_mixin.jira.jql.reset_mock()

        # Act: Call with both JQL and filter (existing JQL has priority)
        search_mixin.search_issues("project = OTHER", projects_filter="TEST")

        # Assert: JQL verification (existing JQL has priority, so filter is ignored)
        if is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == "project = OTHER"
        else:
            search_mixin.jira.jql.assert_called_with(
                jql="project = OTHER",
                fields=ANY,
                start=ANY,
                limit=ANY,
                expand=ANY,
            )

    @pytest.mark.parametrize("is_cloud", [True, False])
    def test_search_issues_with_config_projects_filter_jql_construction(
        self, search_mixin: SearchMixin, mock_issues_response, is_cloud
    ):
        """Test that JQL string is correctly constructed when config.projects_filter is used."""
        # Setup
        search_mixin.config.is_cloud = is_cloud
        search_mixin.config.projects_filter = "CONF1,CONF2"  # Set config filter
        search_mixin.config.url = "https://test.example.com"

        # Add isLast for Cloud API compatibility
        mock_issues_response["isLast"] = True

        # Setup mock response for both API methods
        if is_cloud:
            search_mixin.jira.post = MagicMock(return_value=mock_issues_response)
        else:
            search_mixin.jira.jql = MagicMock(return_value=mock_issues_response)

        # Act: Use config filter
        search_mixin.search_issues("text ~ 'test'")

        # Assert: JQL verification
        if is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert (
                payload["jql"] == '(text ~ \'test\') AND project IN ("CONF1", "CONF2")'
            )
        else:
            search_mixin.jira.jql.assert_called_with(
                jql='(text ~ \'test\') AND project IN ("CONF1", "CONF2")',
                fields=ANY,
                start=ANY,
                limit=ANY,
                expand=ANY,
            )

        # Reset mock for next call
        if is_cloud:
            search_mixin.jira.post.reset_mock()
        else:
            search_mixin.jira.jql.reset_mock()

        # Act: Override config filter with parameter
        search_mixin.search_issues("text ~ 'test'", projects_filter="OVERRIDE")

        # Assert: JQL verification
        if is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == "(text ~ 'test') AND project = \"OVERRIDE\""
        else:
            search_mixin.jira.jql.assert_called_with(
                jql="(text ~ 'test') AND project = \"OVERRIDE\"",
                fields=ANY,
                start=ANY,
                limit=ANY,
                expand=ANY,
            )

    @pytest.mark.parametrize("is_cloud", [True, False])
    def test_search_issues_with_empty_jql_and_projects_filter(
        self, search_mixin: SearchMixin, mock_issues_response, is_cloud
    ):
        """Test that empty JQL correctly prepends project filter without AND."""
        # Setup
        search_mixin.config.is_cloud = is_cloud
        search_mixin.config.projects_filter = None
        search_mixin.config.url = "https://test.example.com"

        # Add isLast for Cloud API compatibility
        mock_issues_response["isLast"] = True

        # Setup mock response for both API methods
        if is_cloud:
            search_mixin.jira.post = MagicMock(return_value=mock_issues_response)
        else:
            search_mixin.jira.jql = MagicMock(return_value=mock_issues_response)

        # Test 1: Empty string JQL with single project
        search_mixin.search_issues("", projects_filter="PROJ1")

        if is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == 'project = "PROJ1"'
        else:
            search_mixin.jira.jql.assert_called_with(
                jql='project = "PROJ1"',
                fields=ANY,
                start=ANY,
                limit=ANY,
                expand=ANY,
            )

        # Reset mock
        if is_cloud:
            search_mixin.jira.post.reset_mock()
        else:
            search_mixin.jira.jql.reset_mock()

        # Test 2: Empty string JQL with multiple projects
        search_mixin.search_issues("", projects_filter="PROJ1,PROJ2")

        if is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == 'project IN ("PROJ1", "PROJ2")'
        else:
            search_mixin.jira.jql.assert_called_with(
                jql='project IN ("PROJ1", "PROJ2")',
                fields=ANY,
                start=ANY,
                limit=ANY,
                expand=ANY,
            )

        # Reset mock
        if is_cloud:
            search_mixin.jira.post.reset_mock()
        else:
            search_mixin.jira.jql.reset_mock()

        # Test 3: None JQL with projects filter
        result = search_mixin.search_issues(None, projects_filter="PROJ1")

        if is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == 'project = "PROJ1"'
        else:
            search_mixin.jira.jql.assert_called_with(
                jql='project = "PROJ1"',
                fields=ANY,
                start=ANY,
                limit=ANY,
                expand=ANY,
            )
        assert isinstance(result, JiraSearchResult)

    @pytest.mark.parametrize("is_cloud", [True, False])
    def test_search_issues_with_order_by_and_projects_filter(
        self, search_mixin: SearchMixin, mock_issues_response, is_cloud
    ):
        """Test that JQL starting with ORDER BY correctly prepends project filter."""
        # Setup
        search_mixin.config.is_cloud = is_cloud
        search_mixin.config.projects_filter = None
        search_mixin.config.url = "https://test.example.com"

        # Add isLast for Cloud API compatibility
        mock_issues_response["isLast"] = True

        # Setup mock response based on is_cloud
        if is_cloud:
            search_mixin.jira.post = MagicMock(return_value=mock_issues_response)
        else:
            search_mixin.jira.jql = MagicMock(return_value=mock_issues_response)

        # Test 1: ORDER BY with single project
        search_mixin.search_issues("ORDER BY created DESC", projects_filter="PROJ1")

        # Verify the correct API was called
        if is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == 'project = "PROJ1" ORDER BY created DESC'
        else:
            search_mixin.jira.jql.assert_called_with(
                jql='project = "PROJ1" ORDER BY created DESC',
                fields=ANY,
                start=ANY,
                limit=ANY,
                expand=ANY,
            )

        # Reset mock
        if is_cloud:
            search_mixin.jira.post.reset_mock()
        else:
            search_mixin.jira.jql.reset_mock()

        # Test 2: ORDER BY with multiple projects
        search_mixin.search_issues(
            "ORDER BY created DESC", projects_filter="PROJ1,PROJ2"
        )

        if is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert (
                payload["jql"] == 'project IN ("PROJ1", "PROJ2") ORDER BY created DESC'
            )
        else:
            search_mixin.jira.jql.assert_called_with(
                jql='project IN ("PROJ1", "PROJ2") ORDER BY created DESC',
                fields=ANY,
                start=ANY,
                limit=ANY,
                expand=ANY,
            )

        # Reset mock
        if is_cloud:
            search_mixin.jira.post.reset_mock()
        else:
            search_mixin.jira.jql.reset_mock()

        # Test 3: Case insensitive ORDER BY
        search_mixin.search_issues("order by updated ASC", projects_filter="PROJ1")

        if is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == 'project = "PROJ1" order by updated ASC'
        else:
            search_mixin.jira.jql.assert_called_with(
                jql='project = "PROJ1" order by updated ASC',
                fields=ANY,
                start=ANY,
                limit=ANY,
                expand=ANY,
            )

        # Reset mock
        if is_cloud:
            search_mixin.jira.post.reset_mock()
        else:
            search_mixin.jira.jql.reset_mock()

        # Test 4: ORDER BY with extra spaces
        search_mixin.search_issues(
            "  ORDER BY priority DESC  ", projects_filter="PROJ1"
        )

        if is_cloud:
            search_mixin.jira.post.assert_called_with("rest/api/3/search/jql", json=ANY)
            # Check the JQL in the payload
            call_args = search_mixin.jira.post.call_args
            payload = call_args[1]["json"]
            assert payload["jql"] == 'project = "PROJ1"   ORDER BY priority DESC  '
        else:
            search_mixin.jira.jql.assert_called_with(
                jql='project = "PROJ1"   ORDER BY priority DESC  ',
                fields=ANY,
                start=ANY,
                limit=ANY,
                expand=ANY,
            )
