import os
import google.generativeai as genai
from dotenv import load_dotenv
import subprocess
import shutil
import base64
import logging

# --- Configuration ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
GIT_USER_NAME = os.getenv("GIT_USER_NAME")
GIT_USER_EMAIL = os.getenv("GIT_USER_EMAIL")

if not all([GEMINI_API_KEY, GITHUB_USERNAME, GIT_USER_NAME, GIT_USER_EMAIL]):
    # This will log a warning if run locally without a full .env file
    # On Render, it should find all the variables
    print("WARNING: One or more required environment variables may be missing.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

def clean_llm_output(raw_text: str) -> str:
    """Removes markdown formatting from LLM output."""
    if '```' in raw_text:
        # Find the first newline after the opening ``` to skip language specifier
        start_index = raw_text.find('\n', raw_text.find('```')) + 1
        end_index = raw_text.rfind('```')
        if end_index > start_index:
            return raw_text[start_index:end_index].strip()
    return raw_text.strip()

def generate_code(brief: str, attachments: list = None) -> str:
    """Generates HTML code from a brief and attachments."""
    logging.info("🤖 Generating code from brief...")
    attachments_content = ""
    if attachments:
        for attachment in attachments:
            try:
                header, encoded_data = attachment['url'].split(',', 1)
                decoded_content = base64.b64decode(encoded_data).decode('utf-8')
                attachments_content += f"\n\n**Attachment: `{attachment['name']}`**\n```\n{decoded_content}\n```"
            except Exception as e:
                logging.warning(f"Could not decode attachment {attachment['name']}: {e}")
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
        logging.error(f"An error occurred during code generation: {e}")
        return "<html><body>Error generating code. See logs for details.</body></html>"

def generate_readme(brief: str, repo_name: str) -> str:
    """Generates README.md content."""
    logging.info("📄 Generating README.md...")
    prompt = f"""
    You are a technical writer. Create a professional README.md for a project named '{repo_name}'.
    The project brief is: {brief}.
    Include sections for Title, Summary, Usage, and License (MIT).
    Respond with ONLY the raw markdown content.
    """
    try:
        response = model.generate_content(prompt)
        return clean_llm_output(response.text)
    except Exception as e:
        logging.error(f"An error occurred during README generation: {e}")
        return f"# {repo_name}\n\nThis project was generated based on the brief: {brief}"

def deploy_to_github(repo_dir: str, repo_name: str, brief: str, attachments: list = None) -> dict:
    """Orchestrates the entire creation and deployment workflow for Round 1."""
    logging.info(f"🚀 Deploying {repo_name} to GitHub...")
    try:
        # 1. Generate code and files
        generated_html = generate_code(brief, attachments)
        readme_content = generate_readme(brief, repo_name)
        license_content = "MIT License\n\nCopyright (c) 2025 Your Name\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \"Software\"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions..."

        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)
        os.makedirs(repo_dir)
        
        with open(os.path.join(repo_dir, "index.html"), "w") as f: f.write(generated_html)
        with open(os.path.join(repo_dir, "README.md"), "w") as f: f.write(readme_content)
        with open(os.path.join(repo_dir, "LICENSE"), "w") as f: f.write(license_content)
        logging.info("✅ Files created locally.")

        # 2. Run Git commands
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', GIT_USER_NAME], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', GIT_USER_EMAIL], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit via AI agent"], cwd=repo_dir, check=True, capture_output=True)
        
        commit_sha_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True)
        commit_sha = commit_sha_result.stdout.strip()

        # 3. Run GitHub CLI commands
        create_repo_command = f"./bin/gh repo create {repo_name} --public --source=."
        subprocess.run(create_repo_command, shell=True, cwd=repo_dir, check=True, capture_output=True)
        
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo_dir, check=True, capture_output=True)
        
        enable_pages_command = f"./bin/gh api --method POST -H \"Accept: application/vnd.github+json\" /repos/{GITHUB_USERNAME}/{repo_name}/pages -f source[branch]=main -f source[path]=\"/\""
        subprocess.run(enable_pages_command, shell=True, check=True, capture_output=True)
        
        repo_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
        pages_url = f"https://{GITHUB_USERNAME}.github.io/{repo_name}/"
        
        logging.info(f"✅ Deployment successful. Commit SHA: {commit_sha}")
        return {"repo_url": repo_url, "pages_url": pages_url, "commit_sha": commit_sha}

    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode() if e.stderr else "No error output captured."
        logging.error(f"❌ An error occurred during deployment: {error_message}")
        return None

def handle_revision_and_deploy(repo_dir: str, repo_name: str, new_brief: str, attachments: list = None) -> dict:
    """Orchestrates the entire revision workflow for Round 2."""
    logging.info(f"🔄 Starting revision for {repo_name}...")
    try:
        # 1. Clone existing repo
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)
        repo_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}.git"
        subprocess.run(["git", "clone", repo_url, repo_dir], check=True, capture_output=True)
        logging.info("✅ Repo cloned successfully.")

        # 2. Configure Git for the cloned repo
        subprocess.run(['git', 'config', 'user.name', GIT_USER_NAME], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', GIT_USER_EMAIL], cwd=repo_dir, check=True, capture_output=True)
        
        # 3. Read old code, generate new code and files
        with open(os.path.join(repo_dir, "index.html"), "r") as f:
            existing_code = f.read()
        
        revision_prompt = f"You are an expert web developer updating an existing web page.\n\n**Current HTML code:**\n```html\n{existing_code}\n```\n\n**Modify the code for this change request:**\n{new_brief}\n\n**Instructions:**\n- Respond with ONLY the new, complete HTML code."
        updated_code = clean_llm_output(model.generate_content(revision_prompt).text)
        updated_readme = generate_readme(new_brief, repo_name)
        
        with open(os.path.join(repo_dir, "index.html"), "w") as f: f.write(updated_code)
        with open(os.path.join(repo_dir, "README.md"), "w") as f: f.write(updated_readme)
        logging.info("✅ Files updated locally.")
        
        # 4. Commit and push changes
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        status_result = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True)
        if not status_result.stdout:
            logging.info("✅ No changes detected. Code is already up to date.")
        else:
            subprocess.run(["git", "commit", "-m", "Apply Round 2 revisions"], cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(["git", "push"], cwd=repo_dir, check=True, capture_output=True)
            logging.info("✅ Changes pushed to GitHub.")
        
        commit_sha_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True)
        commit_sha = commit_sha_result.stdout.strip()
        
        pages_url = f"https://{GITHUB_USERNAME}.github.io/{repo_name}/"
        logging.info(f"✅ Revision successful. Commit SHA: {commit_sha}")
        return {"repo_url": repo_url, "pages_url": pages_url, "commit_sha": commit_sha}

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        error_message = e.stderr.decode() if hasattr(e, 'stderr') and e.stderr else str(e)
        logging.error(f"❌ An error occurred during revision: {error_message}")
        return None
