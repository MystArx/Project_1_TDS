import os
import google.generativeai as genai
from dotenv import load_dotenv
import subprocess
import shutil
import base64

# --- 1. Configuration ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")

if not GEMINI_API_KEY or not GITHUB_USERNAME:
    raise ValueError("Please set GEMINI_API_KEY and GITHUB_USERNAME in your .env file.")

model = genai.GenerativeModel('gemini-2.5-flash')

# --- 2. Helper and Generation Functions ---

def clean_llm_output(raw_text: str) -> str:
    """Removes markdown code block formatting from the LLM's output."""
    if '```' in raw_text:
        start_index = raw_text.find('\n') + 1
        end_index = raw_text.rfind('```')
        if end_index > start_index:
            return raw_text[start_index:end_index].strip()
    return raw_text.strip()

def generate_code(brief: str, attachments: list = None) -> str:
    """Generates HTML code from a brief and attachments."""
    print("🤖 Generating code from brief...")
    attachments_content = ""
    if attachments:
        for attachment in attachments:
            try:
                header, encoded_data = attachment['url'].split(',', 1)
                decoded_content = base64.b64decode(encoded_data).decode('utf-8')
                attachments_content += f"\n\n**Attachment: `{attachment['name']}`**\n```\n{decoded_content}\n```"
            except Exception as e:
                print(f"⚠️ Could not decode attachment {attachment['name']}: {e}")

    prompt = f"""
    You are an expert web developer. Your task is to create a complete, single-page web application in one HTML file.
    All CSS and JavaScript must be inline.

    **Project Brief:**
    {brief}
    {attachments_content} 

    **Instructions:**
    - Use the content from attachments as required by the brief.
    - Respond with ONLY the raw HTML code. Do not include any explanations or markdown.
    """
    try:
        response = model.generate_content(prompt)
        return clean_llm_output(response.text)
    except Exception as e:
        print(f"❌ An error occurred during code generation: {e}")
        return None

# <-- NEW FUNCTION ---
def generate_readme(brief: str, repo_name: str) -> str:
    """Generates README.md content."""
    print("📄 Generating README.md...")
    prompt = f"""
    You are a technical writer. Create a professional README.md file for a web application.

    **Application Name:** `{repo_name}`
    **Brief:** {brief}

    **Instructions:**
    - Create a markdown file with sections: Title, Summary, Usage, and License (MIT).
    - Respond with ONLY the raw markdown content.
    """
    try:
        response = model.generate_content(prompt)
        return clean_llm_output(response.text)
    except Exception:
        return f"# {repo_name}\n\nThis project was generated based on the brief: {brief}"

# --- 3. File and Git Workflow Functions ---

# <-- UPDATED FUNCTION ---
def save_and_prepare_repo(repo_dir: str, brief: str, repo_name: str, code: str):
    """Saves all necessary files to a local directory that will become a Git repo."""
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)
    os.makedirs(repo_dir)
    
    with open(os.path.join(repo_dir, "index.html"), "w") as f:
        f.write(code)
    
    # Generate and save the README.md file
    readme_content = generate_readme(brief, repo_name)
    with open(os.path.join(repo_dir, "README.md"), "w") as f:
        f.write(readme_content)
        
    license_content = "MIT License\n\nCopyright (c) 2025 Your Name\n\nPermission is hereby granted..."
    with open(os.path.join(repo_dir, "LICENSE"), "w") as f:
        f.write(license_content)

    print(f"✅ Code, README, and LICENSE saved in local directory: {repo_dir}")

# <-- UPDATED FUNCTION ---
def deploy_to_github(repo_dir: str, repo_name: str) -> dict:
    """Initializes a git repo, creates a public GitHub repo, and pushes the code."""
    # --- START DEBUG CODE ---
    print("--- PYTHON SCRIPT: DEBUGGING GIT CONFIG ---")
    subprocess.run("git config --list --show-origin", shell=True, cwd=repo_dir)
    print("--- PYTHON SCRIPT: END DEBUGGING ---")
    # --- END DEBUG CODE ---
    print(f"🚀 Deploying {repo_name} to GitHub...")
    try:
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit via AI agent"], cwd=repo_dir, check=True, capture_output=True)
        
        # Capture the commit SHA
        commit_sha_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True)
        commit_sha = commit_sha_result.stdout.strip()

        create_repo_command = f"gh repo create {repo_name} --public --source=."
        subprocess.run(create_repo_command, shell=True, cwd=repo_dir, check=True, capture_output=True)
        
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo_dir, check=True, capture_output=True)

        print("🌍 Enabling GitHub Pages...")
        enable_pages_command = f"gh api --method POST -H \"Accept: application/vnd.github+json\" /repos/{GITHUB_USERNAME}/{repo_name}/pages -f source[branch]=main -f source[path]=\"/\""
        subprocess.run(enable_pages_command, shell=True, check=True, capture_output=True)
        
        repo_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
        pages_url = f"https://{GITHUB_USERNAME}.github.io/{repo_name}/"
        
        print(f"✅ Deployment successful. Commit SHA: {commit_sha}")
        # Return the commit_sha in the result
        return {"repo_url": repo_url, "pages_url": pages_url, "commit_sha": commit_sha}

    except subprocess.CalledProcessError as e:
        print(f"❌ An error occurred during deployment: {e.stderr.decode()}")
        return None

# <-- UPDATED FUNCTION ---
def handle_revision_and_deploy(repo_dir: str, repo_name: str, new_brief: str) -> dict:
    """Clones an existing repo, updates it, and pushes the changes."""
    print(f"🔄 Starting revision for {repo_name}...")
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)
    
    repo_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}.git"
    try:
        subprocess.run(["git", "clone", repo_url, repo_dir], check=True, capture_output=True)
        print("✅ Repo cloned successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to clone repo {repo_url}: {e.stderr.decode()}")
        return None

    try:
        with open(os.path.join(repo_dir, "index.html"), "r") as f:
            existing_code = f.read()
    except FileNotFoundError:
        print("❌ Could not find index.html.")
        return None

    revision_prompt = f"You are an expert web developer updating an existing web page.\n\n**Current HTML code:**\n```html\n{existing_code}\n```\n\n**Modify the code for this change request:**\n{new_brief}\n\n**Instructions:**\n- Respond with ONLY the new, complete HTML code."
    updated_code = clean_llm_output(model.generate_content(revision_prompt).text)
    
    if not updated_code:
        print("❌ AI failed to generate revised code.")
        return None
        
    with open(os.path.join(repo_dir, "index.html"), "w") as f:
        f.write(updated_code)
        
    # Generate and save the updated README.md
    readme_content = generate_readme(new_brief, repo_name)
    with open(os.path.join(repo_dir, "README.md"), "w") as f:
        f.write(readme_content)
    
    try:
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        status_result = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True)
        if not status_result.stdout:
            print("✅ No changes detected. Code is already up to date.")
        else:
            subprocess.run(["git", "commit", "-m", "Apply Round 2 revisions"], cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(["git", "push"], cwd=repo_dir, check=True, capture_output=True)
            print("✅ Changes pushed to GitHub.")

        # Capture the new commit SHA after pushing
        commit_sha_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True)
        commit_sha = commit_sha_result.stdout.strip()
        
        pages_url = f"https://{GITHUB_USERNAME}.github.io/{repo_name}/"
        print(f"✅ Revision successful. Commit SHA: {commit_sha}")
        # Return the new commit_sha in the result
        return {"repo_url": repo_url, "pages_url": pages_url, "commit_sha": commit_sha}

    except subprocess.CalledProcessError as e:
        print(f"❌ An error occurred during git push: {e.stderr.decode()}")
        return None
