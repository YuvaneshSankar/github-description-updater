import os
import requests
import base64
import time
from typing import Optional

# OpenAI imports
import openai

# Constants
GITHUB_API_BASE = "https://api.github.com"


# Load environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")


if not all([GITHUB_TOKEN, OPENAI_API_KEY, GITHUB_USERNAME]):
    raise Exception("Please set GITHUB_TOKEN, OPENAI_API_KEY, and GITHUB_USERNAME environment variables.")


# Setup OpenAI
openai.api_key = OPENAI_API_KEY


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
    """Generate a concise GitHub repo description using OpenAI."""
    prompt_intro = f"Write a short and clear GitHub repository description (max 120 characters) for a project named '{repo_name}'."
    if readme_content:
        # Limit README length for prompt to avoid token overload
        snippet = readme_content[:1500]  # First 1500 chars of README
        prompt = f"{prompt_intro}\n\nThe README of the project is:\n{snippet}\n\nDescription:"
    else:
        prompt = prompt_intro + "\n\nNo README content is available.\n\nDescription:"

    try:
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            max_tokens=50,
            temperature=0.7,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stop=["\n"],
        )
        description = response.choices[0].text.strip()
        # Ensure description is not too long
        if len(description) > 120:
            description = description[:117].rstrip() + "..."
        return description
    except Exception as e:
        print(f"OpenAI API error for repo {repo_name}: {e}")
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
            # Avoid hitting rate limits
            time.sleep(2)
        else:
            print("Description unchanged or empty; skipping update.")


if __name__ == "__main__":
    main()
