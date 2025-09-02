import pytest
import os
import requests
import subprocess
from unittest.mock import patch, MagicMock

import automate_ollam

@pytest.fixture(autouse=True)
def patch_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "FAKE_GITHUB_TOKEN")
    monkeypatch.setenv("GITHUB_USERNAME", "demo-user")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:latest")

def test_env_loading():
    assert automate_ollam.GITHUB_TOKEN == "FAKE_GITHUB_TOKEN"
    assert automate_ollam.GITHUB_USERNAME == "demo-user"
    assert automate_ollam.OLLAMA_MODEL == "llama3.2:latest"

@patch("requests.get")
def test_list_public_repos_empty(mock_get):
    mock_get.return_value.json.return_value = []
    mock_get.return_value.raise_for_status.return_value = None
    repos = automate_ollam.list_public_repos("demo-user")
    assert repos == []

@patch("requests.get")
def test_list_public_repos_multiple_pages(mock_get):
    calls = []
    def side_effect(url, headers):
        if "page=2" in url:
            resp = MagicMock()
            resp.json.return_value = []
            resp.raise_for_status.return_value = None
            calls.append(2)
            return resp
        else:
            resp = MagicMock()
            resp.json.return_value = [{"name": "repo1"}]
            resp.raise_for_status.return_value = None
            calls.append(1)
            return resp
    mock_get.side_effect = side_effect
    repos = automate_ollam.list_public_repos("demo-user")
    assert repos == [{"name": "repo1"}]
    assert calls == [1, 2]

@patch("requests.get")
def test_get_readme_found(mock_get):
    content = base64.b64encode(b"Hello Repo!").decode()
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"content": content, "encoding": "base64"}
    mock_get.return_value.raise_for_status.return_value = None
    result = automate_ollam.get_readme("owner", "repo")
    assert result == "Hello Repo!"

@patch("requests.get")
def test_get_readme_404(mock_get):
    mock_get.return_value.status_code = 404
    result = automate_ollam.get_readme("owner", "repo")
    assert result is None

def test_generate_description_subprocess_success(monkeypatch):
    class FakeRun:
        returncode = 0
        stdout = b"Repo concise description"
        stderr = b""
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeRun())
    desc = automate_ollam.generate_description("repo", "README content")
    assert desc == "Repo concise description"

def test_generate_description_too_long(monkeypatch):
    long_output = "A" * 200
    class FakeRun:
        returncode = 0
        stdout = long_output.encode()
        stderr = b""
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeRun())
    desc = automate_ollam.generate_description("repo", "README content")
    assert desc.endswith("...") and len(desc) <= 120

def test_generate_description_subprocess_error(monkeypatch, capsys):
    class FakeRun:
        returncode = 1
        stdout = b""
        stderr = b"Error running ollama"
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeRun())
    desc = automate_ollam.generate_description("repo", "README")
    assert desc == ""

def test_update_repo_description_success(monkeypatch):
    called = {}
    class FakeResponse:
        status_code = 200
        def json(self): return {}
    def fake_patch(url, json, headers):
        called["desc"] = json["description"]
        return FakeResponse()
    monkeypatch.setattr(requests, "patch", fake_patch)
    automate_ollam.update_repo_description("owner", "repo", "desc")
    assert called["desc"] == "desc"

def test_update_repo_description_failure(monkeypatch, capsys):
    class FakeResponse:
        status_code = 400
        text = "Bad request"
        def json(self): return {}
    monkeypatch.setattr(requests, "patch", lambda *a, **kw: FakeResponse())
    automate_ollam.update_repo_description("owner", "repo", "desc")
    captured = capsys.readouterr()
    assert "Failed to update description" in captured.out

# Add more exhaustive tests for main loop, time.sleep, description unchanged, error branches, etc.

@pytest.mark.parametrize("current_desc,new_desc", [
    ("old desc", "new desc"),
    ("", "desc"),
    ("same", "same")
])
def test_main_update_check(monkeypatch, current_desc, new_desc):
    monkeypatch.setattr(automate_ollam, "list_public_repos", lambda _: [{"name": "repo", "description": current_desc}])
    monkeypatch.setattr(automate_ollam, "get_readme", lambda *_: "README")
    monkeypatch.setattr(automate_ollam, "generate_description", lambda *a, **kw: new_desc)
    called = {}
    monkeypatch.setattr(automate_ollam, "update_repo_description", lambda o, r, d: called.setdefault("desc", d))
    automate_ollam.main()
    if new_desc and new_desc != current_desc:
        assert called["desc"] == new_desc or called["desc"] == "desc"

# Continue to expand with time.sleep coverage and printing assertions

