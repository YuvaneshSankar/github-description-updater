import os
import requests
import subprocess
import base64
import time
from typing import Optional
from dotenv import load_dotenv

# Constants
GITHUB_API_BASE = "https://api.github.com"

# Load environment variables
load_dotenv() # this adds a extra safety before accesing the env

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

if not all([GITHUB_TOKEN, GITHUB_USERNAME]):
    raise Exception("Please set GITHUB_TOKEN and GITHUB_USERNAME environment variables.")

# Headers for GitHub API
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def list_public_repos(username: str):
    """List all public repos for the user."""
    repos = []
    page = 1
    per_page = 50
    while True:
        url = f"{GITHUB_API_BASE}/users/{username}/repos?per_page={per_page}&page={page}&type=public"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos


def get_readme(owner: str, repo: str) -> Optional[str]:
    """Fetch README.md content of a repo, if available."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    content = data.get("content")
    encoding = data.get("encoding")
    if content and encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="ignore")
    return None


def generate_description(repo_name: str, readme_content: Optional[str]) -> str:
    """Generate a concise GitHub repo description using Ollama CLI via subprocess."""
    prompt_intro = f"Task: Generate a GitHub repo description for '{repo_name}'. STRICT RULES: Max 120 characters. Output format: Plain text only - no quotes, no prefixes, no explanations, no markdown. Just the description sentence."
    if readme_content:
        snippet = readme_content[:1500]
        prompt = f"{prompt_intro}\n\nThe README of the project is:\n{snippet}\n\nDescription:"
    else:
        prompt = prompt_intro + "\n\nNo README content is available.\n\nDescription:"

    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120
        )
        if result.returncode != 0:
            print(f"Ollama CLI error for repo {repo_name}: {result.stderr.decode('utf-8')}")
            return ""
        description = result.stdout.decode("utf-8").strip()
        description = description.split("\n")[0]
        if len(description) > 120:
            description = description[:117].rstrip() + "..."
        return description
    except Exception as e:
        print(f"Ollama subprocess error for repo {repo_name}: {e}")
        return ""


def update_repo_description(owner: str, repo: str, description: str):
    """Update the repo description using GitHub API."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    payload = {
        "description": description
    }
    response = requests.patch(url, json=payload, headers=HEADERS)
    if response.status_code == 200:
        print(f"Updated description for '{repo}' successfully.")
    else:
        print(f"Failed to update description for '{repo}': {response.status_code} {response.text}")


def main():
    print(f"Fetching public repos for user: {GITHUB_USERNAME} ...")
    repos = list_public_repos(GITHUB_USERNAME)
    print(f"Found {len(repos)} public repos.")

    for repo in repos:
        repo_name = repo["name"]
        current_description = repo.get("description") or ""
        print(f"\nProcessing repo: {repo_name}")
        print(f"Current description: {current_description}")

        readme = get_readme(GITHUB_USERNAME, repo_name)
        if readme:
            print("README found, generating description...")
        else:
            print("No README found, generating description from repo name only...")

        new_description = generate_description(repo_name, readme)

        if new_description and new_description != current_description:
            print(f"New description: {new_description}")
            update_repo_description(GITHUB_USERNAME, repo_name, new_description)
            # Avoid hitting rate limits, nice thinking, but we need to be careful with the timing
            time.sleep(2)
        else:
            print("Description unchanged or empty; skipping update.")


if __name__ == "__main__":
    main()
