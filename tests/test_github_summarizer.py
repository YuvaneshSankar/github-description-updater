import pytest
import os
import requests
import subprocess
from unittest.mock import patch, mock_open, MagicMock
import github_summarizer

@pytest.fixture(autouse=True)
def patch_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "FAKE_GITHUB_TOKEN")
    monkeypatch.setenv("GITHUB_USERNAME", "demo-user")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:latest")

@patch("requests.get")
def test_list_public_repos_empty(mock_get):
    mock_get.return_value.json.return_value = []
    mock_get.return_value.raise_for_status.return_value = None
    repos = github_summarizer.list_public_repos("demo-user")
    assert repos == []

@patch("requests.get")
def test_get_readme_base64(mock_get):
    content = base64.b64encode(b"My README!").decode()
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"content": content, "encoding": "base64"}
    mock_get.return_value.raise_for_status.return_value = None
    res = github_summarizer.get_readme("owner", "repo")
    assert res == "My README!"

@patch("requests.get")
def test_get_readme_404(mock_get):
    mock_get.return_value.status_code = 404
    assert github_summarizer.get_readme("owner", "repo") is None

@patch("requests.get")
def test_get_repo_languages_success(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"Python": 1024, "JavaScript": 256}
    res = github_summarizer.get_repo_languages("owner", "repo")
    assert res == {"Python": 1024, "JavaScript": 256}

@patch("requests.get")
def test_get_repo_languages_fail(mock_get):
    mock_get.return_value.status_code = 403
    mock_get.return_value.json.return_value = {}
    res = github_summarizer.get_repo_languages("owner", "repo")
    assert res == {}

def test_generate_project_summary_subprocess_success(monkeypatch):
    class FakeRun:
        returncode = 0
        stdout = b"Project summary text here."
        stderr = b""
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeRun())
    summary = github_summarizer.generate_project_summary("repo", "README", {"Python": 999})
    assert summary == "Project summary text here."

def test_generate_project_summary_subprocess_fail(monkeypatch):
    class FakeRun:
        returncode = 1
        stdout = b""
        stderr = b"Error running ollama"
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeRun())
    summary = github_summarizer.generate_project_summary("repo", "README", {"Python": 999})
    assert "Summary generation failed" in summary

def test_format_repo_stats():
    repo = {"stargazers_count": 10, "forks_count": 2, "open_issues_count": 4}
    s = github_summarizer.format_repo_stats(repo)
    assert "10 stars" in s and "2 forks" in s and "4 open issues" in s

    repo = {}
    s = github_summarizer.format_repo_stats(repo)
    assert "No public engagement yet" in s

def test_generate_markdown_report(monkeypatch):
    projects = [
        {'name': 'Repo1', 'html_url': 'http://', 'created_at': '2024-01-01T12:00:00Z', 
         'updated_at': '2024-09-01T12:00:00Z', 'languages': {"Python": 3, "JavaScript": 2}, "ai_summary": "AI summary", "stargazers_count": 1, "forks_count": 2, "open_issues_count": 3},
        {'name': 'Repo2', 'html_url': 'http://', 'created_at': '2023-01-01T12:00:00Z', 
         'updated_at': '2024-09-02T12:00:00Z', 'languages': {}, "ai_summary": "AI summary", "stargazers_count": 0, "forks_count": 0, "open_issues_count": 0},
    ]
    monkeypatch.setattr(github_summarizer, "GITHUB_USERNAME", "testuser")
    report = github_summarizer.generate_markdown_report(projects)
    assert "#  GitHub Projects Portfolio" in report
    assert "Repo1" in report and "Repo2" in report

@patch("builtins.open", new_callable=mock_open)
def test_main_saves_report(mock_file, monkeypatch):
    monkeypatch.setattr(github_summarizer, "list_public_repos", lambda _: [
        {
            "name": "Repo", "html_url": "url", "languages": {"Python": 1},
            "created_at": "2024-06-01T12:00:00Z", "updated_at": "2024-09-01T12:00:00Z", "stargazers_count": 1,
            "forks_count": 1, "open_issues_count": 0
        }
    ])
    monkeypatch.setattr(github_summarizer, "get_readme", lambda *_: "README")
    monkeypatch.setattr(github_summarizer, "get_repo_languages", lambda *a, **kw: {"Python": 1})
    monkeypatch.setattr(github_summarizer, "generate_project_summary", lambda *a, **kw: "AI summary")
    github_summarizer.main()
    mock_file.assert_called()
    handle = mock_file()
    handle.write.assert_called()

# Add more tests for sorting, quick summary, no README branch, and error handling branches

def test_generate_markdown_edge(monkeypatch):
    projects = []
    monkeypatch.setattr(github_summarizer, "GITHUB_USERNAME", "edgeuser")
    report = github_summarizer.generate_markdown_report(projects)
    assert "**Total Projects with Documentation:** 0" in report

# Continue to expand the suite with documentation, error branches, corrupted inputs, parametric tests, and more.

