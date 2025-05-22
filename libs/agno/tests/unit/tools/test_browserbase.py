"""Unit tests for BrowserbaseTools class."""

import json
import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from playwright.sync_api import Browser, BrowserContext, Page

from agno.tools.browserbase import BrowserbaseTools

TEST_API_KEY = os.environ.get("BROWSERBASE_API_KEY", "test_api_key")
TEST_PROJECT_ID = os.environ.get("BROWSERBASE_PROJECT_ID", "test_project_id")
TEST_BASE_URL = os.environ.get("BROWSERBASE_BASE_URL")


@patch("agno.tools.browserbase.Browserbase")
@pytest.fixture
def mock_browserbase(mock_browserbase_cls):
    """Create a mock Browserbase client."""
    mock_client = Mock()
    mock_sessions = Mock()
    mock_client.sessions = mock_sessions
    mock_browserbase_cls.return_value = mock_client
    return mock_client


@patch("agno.tools.browserbase.sync_playwright")
@pytest.fixture
def mock_playwright(mock_sync_playwright):
    """Create a mock Playwright instance."""
    # Create a mock playwright instance without using spec
    mock_playwright_instance = Mock()

    # Setup the return value for sync_playwright()
    mock_sync_playwright.return_value = mock_playwright_instance

    # Setup chromium browser
    mock_browser = Mock(spec=Browser)
    mock_playwright_instance.chromium = Mock()
    mock_playwright_instance.chromium.connect_over_cdp = Mock(return_value=mock_browser)

    # Setup browser context
    mock_context = Mock(spec=BrowserContext)
    mock_browser.contexts = [mock_context]

    # Setup page
    mock_page = Mock(spec=Page)
    mock_context.pages = [mock_page]

    return {
        "playwright": mock_playwright_instance,
        "browser": mock_browser,
        "context": mock_context,
        "page": mock_page,
    }


@patch.dict("os.environ", {"BROWSERBASE_API_KEY": TEST_API_KEY, "BROWSERBASE_PROJECT_ID": TEST_PROJECT_ID})
@pytest.fixture
def browserbase_tools(mock_browserbase):
    """Create a BrowserbaseTools instance with mocked dependencies."""
    tools = BrowserbaseTools()
    # Directly set the app to our mock to avoid initialization issues
    tools.app = mock_browserbase
    return tools


@patch("agno.tools.browserbase.Browserbase")
@patch.dict(
    "os.environ", {"BROWSERBASE_API_KEY": TEST_API_KEY, "BROWSERBASE_PROJECT_ID": TEST_PROJECT_ID}, clear=True
)
def test_init_with_env_vars(mock_browserbase, mock_env):
    """Test initialization with environment variables."""
    tools = BrowserbaseTools()
    assert tools.api_key == TEST_API_KEY
    assert tools.project_id == TEST_PROJECT_ID
    assert tools.base_url is None


@patch("agno.tools.browserbase.Browserbase")
@patch.dict("os.environ", {}, clear=True)
def test_init_with_params(mock_browserbase, mock_env):
    """Test initialization with parameters."""
    tools = BrowserbaseTools(api_key="param_api_key", project_id="param_project_id", base_url=TEST_BASE_URL)
    assert tools.api_key == "param_api_key"
    assert tools.project_id == "param_project_id"
    assert tools.base_url == TEST_BASE_URL


def test_init_with_missing_api_key():
    """Test initialization with missing API key raises ValueError."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="BROWSERBASE_API_KEY is required"):
            BrowserbaseTools()


@patch("agno.tools.browserbase.Browserbase")
@patch.dict("os.environ", {"BROWSERBASE_API_KEY": TEST_API_KEY}, clear=True)
def test_init_with_missing_project_id(mock_browserbase, mock_env):
    """Test initialization with missing project ID raises ValueError."""
    with pytest.raises(ValueError, match="BROWSERBASE_PROJECT_ID is required"):
        BrowserbaseTools()


def test_ensure_session(browserbase_tools, mock_browserbase):
    """Test _ensure_session method creates a session if none exists."""
    # Setup mock session
    mock_session = Mock()
    mock_session.id = "test_session_id"
    mock_session.connect_url = "ws://test.connect.url"
    mock_browserbase.sessions.create.return_value = mock_session

    # Call the method
    browserbase_tools._ensure_session()

    # Verify results
    assert browserbase_tools._session == mock_session
    assert browserbase_tools._connect_url == "ws://test.connect.url"
    mock_browserbase.sessions.create.assert_called_once_with(project_id=TEST_PROJECT_ID)

    # Reset the mock and call again - should not create a new session
    mock_browserbase.sessions.create.reset_mock()
    browserbase_tools._ensure_session()
    mock_browserbase.sessions.create.assert_not_called()


@patch("agno.tools.browserbase.sync_playwright")
@patch.object(BrowserbaseTools, "_ensure_session")
def test_initialize_browser(browserbase_tools, mock_ensure_session, mock_sync_playwright):
    """Test _initialize_browser method with connect_url."""
    # Set up a mock for the playwright instance
    mock_playwright = Mock()
    mock_browser = Mock()
    mock_context = Mock()
    mock_page = Mock()

    # Set up the mock browser with a list-like contexts attribute
    mock_browser.contexts = MagicMock()
    mock_browser.contexts.__getitem__.return_value = mock_context

    # Set up the mock context with a list-like pages attribute
    mock_context.pages = MagicMock()
    mock_context.pages.__getitem__.return_value = mock_page

    # Set up the chromium connect_over_cdp method
    mock_playwright.chromium = Mock()
    mock_playwright.chromium.connect_over_cdp = Mock(return_value=mock_browser)

    # Set up the sync_playwright().start() chain
    mock_sync_playwright.return_value = Mock()
    mock_sync_playwright.return_value.start.return_value = mock_playwright

    # Call the method with a connect_url
    browserbase_tools._initialize_browser("ws://test.connect.url")

    # Verify the connect_url was set
    assert browserbase_tools._connect_url == "ws://test.connect.url"
    mock_playwright.chromium.connect_over_cdp.assert_called_once_with("ws://test.connect.url")


def test_navigate_to(browserbase_tools, mock_playwright):
    """Test navigate_to method."""
    # Setup mock page
    mock_page = mock_playwright["page"]
    mock_page.title.return_value = "Test Page Title"

    # Set the page on the tools instance to avoid connect_over_cdp
    browserbase_tools._page = mock_page
    browserbase_tools._browser = mock_playwright["browser"]
    browserbase_tools._playwright = mock_playwright["playwright"]

    # Call the method
    result = browserbase_tools.navigate_to("https://example.com")
    result_data = json.loads(result)

    # Verify results
    assert result_data["status"] == "complete"
    assert result_data["title"] == "Test Page Title"
    assert result_data["url"] == "https://example.com"
    mock_page.goto.assert_called_once_with("https://example.com", wait_until="networkidle")


def test_screenshot(browserbase_tools, mock_playwright):
    """Test screenshot method."""
    # Set the page on the tools instance to avoid connect_over_cdp
    browserbase_tools._page = mock_playwright["page"]
    browserbase_tools._browser = mock_playwright["browser"]
    browserbase_tools._playwright = mock_playwright["playwright"]

    # Call the method
    result = browserbase_tools.screenshot("/path/to/screenshot.png", True)
    result_data = json.loads(result)

    # Verify results
    assert result_data["status"] == "success"
    assert result_data["path"] == "/path/to/screenshot.png"
    mock_playwright["page"].screenshot.assert_called_once_with(path="/path/to/screenshot.png", full_page=True)


def test_get_page_content(browserbase_tools, mock_playwright):
    """Test get_page_content method."""
    # Setup mock page
    mock_page = mock_playwright["page"]
    mock_page.content.return_value = "<html><body>Test content</body></html>"

    # Set the page on the tools instance to avoid connect_over_cdp
    browserbase_tools._page = mock_page
    browserbase_tools._browser = mock_playwright["browser"]
    browserbase_tools._playwright = mock_playwright["playwright"]

    # Call the method
    result = browserbase_tools.get_page_content()

    # Verify results
    assert result == "<html><body>Test content</body></html>"
    mock_page.content.assert_called_once()


def test_close_session_with_session_id(browserbase_tools, mock_browserbase):
    """Test close_session method."""
    # Call the method
    result = browserbase_tools.close_session()
    result_data = json.loads(result)

    # Verify results
    assert result_data["status"] == "closed"
    # We no longer expect sessions.delete to be called
    # Instead, verify that cleanup was performed
    assert "Browser resources cleaned up" in result_data["message"]


def test_close_session_without_session_id(browserbase_tools, mock_browserbase):
    """Test close_session method with current session."""
    # Setup mock session
    mock_session = Mock()
    mock_session.id = "current_session_id"
    browserbase_tools._session = mock_session

    # Call the method
    result = browserbase_tools.close_session()
    result_data = json.loads(result)

    # Verify results
    assert result_data["status"] == "closed"
    assert browserbase_tools._session is None


@patch.object(BrowserbaseTools, "_cleanup", side_effect=Exception("Cleanup failed"))
def test_close_session_with_exception(browserbase_tools, mock_browserbase, mock_cleanup):
    """Test close_session method when an exception occurs."""
    # Call the method
    result = browserbase_tools.close_session()
    result_data = json.loads(result)

    # Verify results
    assert result_data["status"] == "warning"
    assert "Cleanup completed with warning" in result_data["message"]
    assert "Cleanup failed" in result_data["message"]
