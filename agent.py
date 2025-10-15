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
# These will be set by the environment variables on Render
GIT_USER_NAME = os.getenv("GIT_USER_NAME")
GIT_USER_EMAIL = os.getenv("GIT_USER_EMAIL")

if not all([GEMINI_API_KEY, GITHUB_USERNAME, GIT_USER_NAME, GIT_USER_EMAIL]):
    raise ValueError("One or more required environment variables are missing.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- (generate_code, generate_readme, etc. remain the same) ---
# ... (all your other functions like generate_code, clean_llm_output, etc. go here) ...
def clean_llm_output(raw_text: str) -> str:
    if '```' in raw_text:
        start_index = raw_text.find('\n') + 1
        end_index = raw_text.rfind('```')
        if end_index > start_index:
            return raw_text[start_index:end_index].strip()
    return raw_text.strip()
def generate_code(brief: str, attachments: list = None) -> str:
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
    You are an expert web developer...
    """
    try:
        response = model.generate_content(prompt)
        return clean_llm_output(response.text)
    except Exception as e:
        print(f"❌ An error occurred during code generation: {e}")
        return None
def generate_readme(brief: str, repo_name: str) -> str:
    print("📄 Generating README.md...")
    prompt = f"""
    You are a technical writer...
    """
    try:
        response = model.generate_content(prompt)
        return clean_llm_output(response.text)
    except Exception:
        return f"# {repo_name}\n\nThis project was generated based on the brief: {brief}"
def save_and_prepare_repo(repo_dir: str, brief: str, repo_name: str, code: str):
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)
    os.makedirs(repo_dir)
    with open(os.path.join(repo_dir, "index.html"), "w") as f:
        f.write(code)
    readme_content = generate_readme(brief, repo_name)
    with open(os.path.join(repo_dir, "README.md"), "w") as f:
        f.write(readme_content)
    license_content = "MIT License..."
    with open(os.path.join(repo_dir, "LICENSE"), "w") as f:
        f.write(license_content)
    print(f"✅ Code, README, and LICENSE saved in local directory: {repo_dir}")

# --- UPDATED DEPLOYMENT FUNCTIONS ---

def deploy_to_github(repo_dir: str, repo_name: str) -> dict:
    print(f"🚀 Deploying {repo_name} to GitHub...")
    try:
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True)
        
        # --- THE FIX IS HERE ---
        # Configure Git within the script's runtime environment
        subprocess.run(['git', 'config', 'user.name', GIT_USER_NAME], cwd=repo_dir, check=True)
        subprocess.run(['git', 'config', 'user.email', GIT_USER_EMAIL], cwd=repo_dir, check=True)
        
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit via AI agent"], cwd=repo_dir, check=True)
        
        commit_sha_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True)
        commit_sha = commit_sha_result.stdout.strip()

        create_repo_command = f"gh repo create {repo_name} --public --source=."
        subprocess.run(create_repo_command, shell=True, cwd=repo_dir, check=True)
        
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo_dir, check=True)
        
        enable_pages_command = f"gh api --method POST -H \"Accept: application/vnd.github+json\" /repos/{GITHUB_USERNAME}/{repo_name}/pages -f source[branch]=main -f source[path]=\"/\""
        subprocess.run(enable_pages_command, shell=True, check=True)
        
        repo_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
        pages_url = f"https://{GITHUB_USERNAME}.github.io/{repo_name}/"
        
        return {"repo_url": repo_url, "pages_url": pages_url, "commit_sha": commit_sha}
    except subprocess.CalledProcessError as e:
        print(f"❌ An error occurred during deployment: {e.stderr.decode()}")
        return None

def handle_revision_and_deploy(repo_dir: str, repo_name: str, new_brief: str) -> dict:
    print(f"🔄 Starting revision for {repo_name}...")
    # ... (cloning logic)
    repo_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}.git"
    try:
        subprocess.run(["git", "clone", repo_url, repo_dir], check=True)
    except Exception as e:
        print(f"❌ Failed to clone repo: {e}")
        return None

    # --- THE FIX IS HERE ---
    # Configure Git within the script's runtime environment for the cloned repo
    subprocess.run(['git', 'config', 'user.name', GIT_USER_NAME], cwd=repo_dir, check=True)
    subprocess.run(['git', 'config', 'user.email', GIT_USER_EMAIL], cwd=repo_dir, check=True)

    # ... (rest of the revision and push logic, which also needs the git config)
    # ...
    try:
        # ... your code to read index.html, generate updated code, save it, generate readme ...
        with open(os.path.join(repo_dir, "index.html"), "r") as f:
            existing_code = f.read()
        revision_prompt = f"..."
        updated_code = clean_llm_output(model.generate_content(revision_prompt).text)
        with open(os.path.join(repo_dir, "index.html"), "w") as f:
            f.write(updated_code)
        readme_content = generate_readme(new_brief, repo_name)
        with open(os.path.join(repo_dir, "README.md"), "w") as f:
            f.write(readme_content)
        # ...
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Apply Round 2 revisions"], cwd=repo_dir, check=True)
        subprocess.run(["git", "push"], cwd=repo_dir, check=True)

        commit_sha_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True)
        commit_sha = commit_sha_result.stdout.strip()
        
        pages_url = f"https://{GITHUB_USERNAME}.github.io/{repo_name}/"
        return {"repo_url": repo_url, "pages_url": pages_url, "commit_sha": commit_sha}

    except subprocess.CalledProcessError as e:
        print(f"❌ An error occurred during revision push: {e.stderr.decode()}")
        return None
