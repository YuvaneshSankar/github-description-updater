import os
import requests
import base64
import time
from typing import Optional, List, Dict
from dotenv import load_dotenv

GITHUB_API_BASE = "https://api.github.com"
VLLM_API_URL = "http://localhost:8000/v1/chat/completions"

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_ORG_NAME = os.getenv("GITHUB_ORG_NAME")
VLLM_MODEL = os.getenv("VLLM_MODEL", "default")

if not all([GITHUB_TOKEN, GITHUB_ORG_NAME]):
    raise Exception(
        "Please set GITHUB_TOKEN and GITHUB_ORG_NAME environment variables."
    )

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def list_org_repos(org: str) -> List[Dict]:
    repos = []
    page = 1
    per_page = 100

    while True:
        url = f"{GITHUB_API_BASE}/orgs/{org}/repos?per_page={per_page}&page={page}&type=all"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        if not data:
            break

        repos.extend(data)
        page += 1

    return repos


def get_readme(owner: str, repo: str) -> Optional[str]:
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 404:
        return None

    response.raise_for_status()
    data = response.json()
    content = data.get("content") or data.get("reasoning")
    encoding = data.get("encoding")

    if content and encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="ignore")

    return None


def condense_readmes(repos_with_readmes: List[Dict]) -> str:
    condensed = []

    for repo in repos_with_readmes:
        repo_name = repo["name"]
        readme = repo["readme"]
        description = repo.get("description", "No description")

        condensed.append(f"""## Repository: {repo_name}
**Description:** {description}

**README Content:**
{readme}

---
""")

    return "\n".join(condensed)


def generate_org_description(org_name: str, condensed_readmes: str) -> str:
    prompt = f"""Write a single professional one-line description (max 120 characters) for a student GitHub organization called "{org_name}".

This is a student collective focused on research-level experiments in areas like reinforcement learning, CUDA programming, core ML research (optimizers, architectures, training methods), and systems-level ML work.

Context from their repositories:
{condensed_readmes}

Write a clean, professional one-liner. No emojis, no emoticons, no marketing language. Just state what the collective does.

Return only the one-liner, nothing else."""

    payload = {
        "model": VLLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 128,
        "temperature": 0.7,
    }

    try:
        response = requests.post(VLLM_API_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        return (
            data["choices"][0]["message"]["content"]
            or data["choices"][0]["message"]["reasoning"]
            or ""
        )
    except Exception as e:
        print(f"Error calling vLLM API for org description: {e}")
        return ""


def generate_org_readme(org_name: str, condensed_readmes: str) -> str:
    prompt = f"""Create an organization README for "{org_name}", a student collective focused on research-level technical work.

STRICT RULES:
- No emojis or emoticons anywhere. The only exception is the smiley :) — use it at most once if it fits.
- Focus areas must be software/ML research topics only (e.g., reinforcement learning, CUDA kernels, optimizer research, distributed training, model architecture research). Never include mechanical, electrical, hardware manufacturing, or non-software domains.
- Strictly professional and minimal tone. No marketing language, no hype.

Below is the condensed content from all repositories:

{condensed_readmes}

Create a README with ONLY these three sections:

## About
2-3 sentences on what this collective is and what we work on.

## Focus Areas
Bullet list of the actual research/experiment areas derived from the repos. Examples of the right kind of focus areas: reinforcement learning, CUDA programming, optimizer research (e.g., Muon, Adam variants), core ML research, distributed systems, compiler work. Only list areas that are actually present in the repos.

## Top 5 Repositories
List the 5 most significant repositories (by complexity, research value, or engagement) with a one-line description each. Format:
- **repo-name** — one-line description

Keep everything minimal. Short sentences. Valid Markdown only. Return only the README content."""

    payload = {
        "model": VLLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
        "temperature": 0.7,
    }

    try:
        response = requests.post(VLLM_API_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        return (
            data["choices"][0]["message"]["content"]
            or data["choices"][0]["message"]["reasoning"]
            or ""
        )
    except Exception as e:
        print(f"Error calling vLLM API for org readme: {e}")
        return ""


def main():
    print(f"Fetching repositories for organization: {GITHUB_ORG_NAME}...")
    all_repos = list_org_repos(GITHUB_ORG_NAME)
    print(f"Found {len(all_repos)} repositories.")

    repos_with_readme = []

    for repo in all_repos:
        repo_name = repo["name"]
        print(f"\nChecking: {repo_name}")

        readme = get_readme(GITHUB_ORG_NAME, repo_name)
        if readme:
            print(f"  README found")
            repos_with_readme.append(
                {
                    "name": repo_name,
                    "description": repo.get("description", ""),
                    "readme": readme,
                }
            )
        else:
            print(f"  No README - skipping")

        time.sleep(0.5)

    print(f"\nFound {len(repos_with_readme)} repositories with README files.")

    if not repos_with_readme:
        print("No repositories with README files found. Exiting.")
        return

    print("\nCondensing READMEs...")
    condensed_readmes = condense_readmes(repos_with_readme)

    print(f"Generating one-liner description via vLLM ({VLLM_MODEL})...")
    org_description = generate_org_description(GITHUB_ORG_NAME, condensed_readmes)

    if org_description:
        print(f"Description: {org_description}")
    else:
        print("Failed to generate one-liner description.")

    print(f"\nGenerating organization README via vLLM ({VLLM_MODEL})...")
    org_readme = generate_org_readme(GITHUB_ORG_NAME, condensed_readmes)

    if org_readme:
        filename = f"{GITHUB_ORG_NAME}_README.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(org_readme)

        print(f"\nOrganization README generated: {filename}")
        print(f"Total repositories analyzed: {len(repos_with_readme)}")
    else:
        print("\nFailed to generate organization README.")


if __name__ == "__main__":
    main()
