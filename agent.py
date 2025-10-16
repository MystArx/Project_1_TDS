import os
import logging
import shutil
import base64
import subprocess
from dotenv import load_dotenv
import google.generativeai as genai
from github import Github
import requests

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
GIT_USER_NAME = os.getenv("GIT_USER_NAME")
GIT_USER_EMAIL = os.getenv("GIT_USER_EMAIL")

# -------------------------
# Logging configuration
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# Configure Google Gemini API
# -------------------------
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# -------------------------
# Helper functions
# -------------------------

def clean_llm_output(raw_text: str) -> str:
    """Removes markdown formatting from LLM output."""
    if '```' in raw_text:
        start_index = raw_text.find('\n', raw_text.find('```')) + 1
        end_index = raw_text.rfind('```')
        if end_index > start_index:
            return raw_text[start_index:end_index].strip()
    return raw_text.strip()

def generate_code(brief: str, attachments: list = None) -> str:
    """Generates HTML code from project brief using Gemini LLM."""
    logger.info("🤖 Generating HTML code from brief...")
    attachments_content = ""

    if attachments:
        for attachment in attachments:
            try:
                header, encoded_data = attachment['url'].split(',', 1)
                binary_data = base64.b64decode(encoded_data)

                # Handle text vs. binary attachments
                filename = attachment.get('name', 'unknown')
                if filename.lower().endswith(('.txt', '.html', '.md', '.json', '.csv')):
                    decoded_content = binary_data.decode('utf-8', errors='ignore')
                else:
                    decoded_content = f"[Binary file: {filename} ({len(binary_data)} bytes)]"

                attachments_content += (
                    f"\n\n**Attachment: `{filename}`**\n```\n{decoded_content}\n```"
                )

            except Exception as e:
                logger.warning(f"Could not process attachment {attachment.get('name', 'unknown')}: {e}")

    # Build the full LLM prompt
    prompt = f"""
You are an expert web developer. Create a single HTML file with inline CSS and JavaScript.
Project Brief: {brief}
{attachments_content}
Instructions: Respond with ONLY the raw HTML code.
"""

    try:
        response = model.generate_content(prompt)
        return clean_llm_output(response.text)
    except Exception as e:
        logger.error(f"Error generating code: {e}")
        return "<html><body>Error generating code. See logs.</body></html>"


def generate_readme(brief: str, repo_name: str) -> str:
    """Generates README.md content."""
    logger.info("📄 Generating README.md...")
    prompt = f"""
You are a technical writer. Create a professional README.md for a project named '{repo_name}'.
The project brief is: {brief}.
Include sections for Title, Summary, Usage, and License (MIT).
Respond with ONLY raw markdown content.
"""
    try:
        response = model.generate_content(prompt)
        return clean_llm_output(response.text)
    except Exception as e:
        logger.error(f"Error generating README: {e}")
        return f"# {repo_name}\n\nThis project was generated based on the brief: {brief}"

license_content =
'''
MIT License
Copyright (c) 2025
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

def save_and_prepare_repo(repo_dir: str, brief: str, repo_name: str, code: str):
    """Creates local repo files: index.html, README.md, LICENSE."""
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)
    os.makedirs(repo_dir)

    with open(os.path.join(repo_dir, "index.html"), "w") as f:
        f.write(code)
    with open(os.path.join(repo_dir, "README.md"), "w") as f:
        f.write(generate_readme(brief, repo_name))
    with open(os.path.join(repo_dir, "LICENSE"), "w") as f:
        f.write("")
        f.write(license_content)

    logger.info(f"✅ Repository files saved in {repo_dir}")

# -------------------------
# Deployment functions
# -------------------------

def deploy_to_github(repo_dir: str, repo_name: str, brief: str, attachments: list = None) -> dict:
    """Round 1: Create repo, upload files, and enable GitHub Pages (Render-safe)."""
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN not found! Cannot deploy.")
        return None

    try:
        # Generate code
        code = generate_code(brief, attachments)
        readme = generate_readme(brief, repo_name)
        license_text = "MIT License"

        # Create repo via PyGithub
        g = Github(GITHUB_TOKEN)
        user = g.get_user()
        repo = user.create_repo(repo_name, private=False, auto_init=False)
        logger.info(f"✅ GitHub repo created: {repo.full_name}")

        # Upload files using REST API (no git CLI)
        upload_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}

        def upload_file(path, content, message):
            encoded = base64.b64encode(content.encode()).decode()
            data = {"message": message, "content": encoded, "branch": "main"}
            r = requests.put(upload_url + path, headers=headers, json=data)
            r.raise_for_status()
            return r.json()

        logger.info("📤 Uploading files to repo...")
        upload_file("index.html", code, "Add index.html")
        upload_file("README.md", readme, "Add README.md")
        upload_file("LICENSE", license_text, "Add LICENSE")

        # Enable GitHub Pages via REST API
        logger.info("🌐 Enabling GitHub Pages...")
        pages_api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/pages"
        pages_payload = {"source": {"branch": "main", "path": "/"}}
        r = requests.post(pages_api_url, headers=headers, json=pages_payload)
        if r.status_code not in (200, 201, 202):
            logger.warning(f"⚠️ Could not enable GitHub Pages automatically: {r.text}")

        # Get latest commit SHA
        commits_api = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/commits"
        commit_data = requests.get(commits_api, headers=headers).json()
        commit_sha = commit_data[0]["sha"] if isinstance(commit_data, list) and commit_data else "unknown"

        pages_url = f"https://{GITHUB_USERNAME}.github.io/{repo_name}/"
        logger.info(f"✅ Deployment complete. Pages URL: {pages_url}")

        return {"repo_url": repo.html_url, "pages_url": pages_url, "commit_sha": commit_sha}

    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}", exc_info=True)
        return None

def handle_revision_and_deploy(repo_dir: str, repo_name: str, new_brief: str, attachments: list = None) -> dict:
    """Round 2: Update files and redeploy (Render-safe)."""
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN not found! Cannot deploy revision.")
        return None

    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}

        # Fetch old index.html content
        get_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/index.html"
        resp = requests.get(get_url, headers=headers)
        resp.raise_for_status()
        old_data = resp.json()
        old_code = base64.b64decode(old_data["content"]).decode("utf-8")

        # Generate updated code
        attachments_content = ""
        if attachments:
            for attachment in attachments:
                try:
                    header, encoded_data = attachment["url"].split(",", 1)
                    decoded_content = base64.b64decode(encoded_data).decode("utf-8", errors="ignore")
                    attachments_content += f"\n\n**Attachment: `{attachment['name']}`**\n```\n{decoded_content}\n```"
                except Exception as e:
                    logger.warning(f"Could not decode attachment {attachment['name']}: {e}")

        revision_prompt = f"""
You are an expert web developer updating an existing web page.
Current code:
{old_code}
Change request:
{new_brief}
Attachments:
{attachments_content}
Respond with ONLY the new, complete HTML code.
"""
        updated_code = clean_llm_output(model.generate_content(revision_prompt).text)
        new_readme = generate_readme(new_brief, repo_name)

        # Upload new files
        upload_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/"
        def update_file(path, content, sha, message):
            encoded = base64.b64encode(content.encode()).decode()
            data = {"message": message, "content": encoded, "sha": sha, "branch": "main"}
            r = requests.put(upload_url + path, headers=headers, json=data)
            r.raise_for_status()
            return r.json()

        update_file("index.html", updated_code, old_data["sha"], "Apply Round 2 revisions")
        # Update README.md (fetch old SHA)
        readme_resp = requests.get(upload_url + "README.md", headers=headers)
        readme_sha = readme_resp.json()["sha"] if readme_resp.status_code == 200 else None
        update_file("README.md", new_readme, readme_sha, "Update README.md")

        # Get latest commit SHA
        commits_api = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/commits"
        commit_data = requests.get(commits_api, headers=headers).json()
        commit_sha = commit_data[0]["sha"] if isinstance(commit_data, list) and commit_data else "unknown"

        pages_url = f"https://{GITHUB_USERNAME}.github.io/{repo_name}/"
        logger.info(f"✅ Revision deployment complete. Commit SHA: {commit_sha}")
        return {"repo_url": f"https://github.com/{GITHUB_USERNAME}/{repo_name}", "pages_url": pages_url, "commit_sha": commit_sha}

    except Exception as e:
        logger.error(f"❌ Revision deployment failed: {e}", exc_info=True)
        return None

