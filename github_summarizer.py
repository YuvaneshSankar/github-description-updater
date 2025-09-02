import os
import requests
import subprocess
import base64
import time
from typing import Optional, List, Dict
from dotenv import load_dotenv
from datetime import datetime

GITHUB_API_BASE = "https://api.github.com"

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

if not all([GITHUB_TOKEN, GITHUB_USERNAME]):
    raise Exception("Please set GITHUB_TOKEN and GITHUB_USERNAME environment variables.")

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

def list_public_repos(username: str) -> List[Dict]:
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

def get_repo_languages(owner: str, repo: str) -> Dict[str, int]:
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/languages"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        return response.json()
    
    return {}

def generate_project_summary(repo_name: str, readme_content: str, languages: Dict[str, int]) -> str:
    
    top_languages = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:3]
    lang_info = ", ".join([lang for lang, _ in top_languages]) if top_languages else "Unknown"
    
    prompt = f"""Task: Analyze this GitHub repository and create a comprehensive project summary.

Repository: {repo_name}
Main Technologies: {lang_info}

README Content:
{readme_content[:2000]}

Please provide a detailed summary in the following format:
- Brief project description (1-2 sentences)
- Key features or functionality
- Technologies/frameworks used
- Purpose or use case

Keep the summary informative but concise (max 300 words). Focus on what the project does and its main value proposition."""

    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180
        )
        
        if result.returncode != 0:
            print(f"Ollama CLI error for repo {repo_name}: {result.stderr.decode('utf-8')}")
            return f"Repository: {repo_name}\nTechnologies: {lang_info}\n*Summary generation failed*"
        
        summary = result.stdout.decode("utf-8").strip()
        return summary
        
    except Exception as e:
        print(f"Ollama subprocess error for repo {repo_name}: {e}")
        return f"Repository: {repo_name}\nTechnologies: {lang_info}\n*Summary generation failed*"

def format_repo_stats(repo: Dict) -> str:
    stats = []
    
    if repo.get("stargazers_count", 0) > 0:
        stats.append(f"⭐ {repo['stargazers_count']} stars")
    
    if repo.get("forks_count", 0) > 0:
        stats.append(f"🍴 {repo['forks_count']} forks")
    
    if repo.get("open_issues_count", 0) > 0:
        stats.append(f"📝 {repo['open_issues_count']} open issues")
    
    return " | ".join(stats) if stats else "*No public engagement yet*"

def generate_markdown_report(projects: List[Dict]) -> str:
    
    report = f"""# 🚀 GitHub Projects Portfolio

**Generated on:** {datetime.now().strftime("%B %d, %Y")}  
**Total Projects with Documentation:** {len(projects)}

---

## 📊 Quick Overview

| Metric | Count |
|--------|-------|
| **Total Documented Projects** | {len(projects)} |
| **Total Stars** | {sum(p.get('stargazers_count', 0) for p in projects)} |
| **Total Forks** | {sum(p.get('forks_count', 0) for p in projects)} |

---

## 📁 Project Details

"""
    
    for i, project in enumerate(projects, 1):
        repo_name = project['name']
        repo_url = project['html_url']
        created_date = datetime.strptime(project['created_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%B %Y")
        updated_date = datetime.strptime(project['updated_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y")
        
        languages = project.get('languages', {})
        lang_badges = []
        for lang in list(languages.keys())[:5]:
            lang_badges.append(f"`{lang}`")
        
        lang_section = " ".join(lang_badges) if lang_badges else "`Unknown`"
        
        stats = format_repo_stats(project)
        
        report += f"""### {i}. [{repo_name}]({repo_url})

**Technologies:** {lang_section}  
**Created:** {created_date} | **Last Updated:** {updated_date}  
**Stats:** {stats}

{project.get('ai_summary', '*Summary not available*')}

---

"""
    
    report += f"""
## 🔗 Connect

Visit my GitHub profile: [@{GITHUB_USERNAME}](https://github.com/{GITHUB_USERNAME})

*This report was generated automatically using AI analysis of repository README files.*
"""
    
    return report

def main():
    print(f"Fetching public repos for user: {GITHUB_USERNAME}...")
    all_repos = list_public_repos(GITHUB_USERNAME)
    print(f"Found {len(all_repos)} total public repos.")
    
    repos_with_readme = []
    
    for repo in all_repos:
        repo_name = repo["name"]
        print(f"\nChecking repo: {repo_name}")
        
        readme = get_readme(GITHUB_USERNAME, repo_name)
        if readme:
            print(f"✅ README found for {repo_name}")
            
            languages = get_repo_languages(GITHUB_USERNAME, repo_name)
            repo['languages'] = languages
            
            print("🤖 Generating AI summary...")
            ai_summary = generate_project_summary(repo_name, readme, languages)
            repo['ai_summary'] = ai_summary
            repo['readme_content'] = readme
            
            repos_with_readme.append(repo)
            
            time.sleep(2)
        else:
            print(f"❌ No README found for {repo_name} - skipping")
    
    print(f"\n📝 Found {len(repos_with_readme)} repos with README files.")
    
    if repos_with_readme:
        repos_with_readme.sort(key=lambda x: (x.get('stargazers_count', 0), x['updated_at']), reverse=True)
        
        print("📄 Generating markdown report...")
        markdown_report = generate_markdown_report(repos_with_readme)
        
        filename = f"github_projects_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(markdown_report)
        
        print(f"✅ Report generated successfully: {filename}")
        print(f"📊 Total documented projects: {len(repos_with_readme)}")
        
        print("\n" + "="*60)
        print("QUICK SUMMARY")
        print("="*60)
        for repo in repos_with_readme[:5]:
            print(f"• {repo['name']} ({', '.join(list(repo.get('languages', {}).keys())[:2])})")
        if len(repos_with_readme) > 5:
            print(f"• ... and {len(repos_with_readme) - 5} more projects")
    else:
        print("❌ No repositories with README files found.")

if __name__ == "__main__":
    main()
