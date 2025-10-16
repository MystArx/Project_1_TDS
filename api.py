import os
import logging
import requests
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from dotenv import load_dotenv
from agent import deploy_to_github, handle_revision_and_deploy

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()
ROUND2_SECRET = os.getenv("APP_SECRET")

# -------------------------
# Configure logging
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# Initialize FastAPI app
# -------------------------
app = FastAPI(title="AI App Generator Backend")

# -------------------------
# Background build process
# -------------------------
def run_the_build_process(task_data: dict):
    """
    Handles Round 1 and Round 2 deployments in background.
    """
    logger.info("--- STARTING BUILD PROCESS ---")

    try:
        round_number = task_data.get("round", 1)
        repo_name = task_data.get("task")
        brief = task_data.get("brief")
        attachments = task_data.get("attachments", [])

        if not repo_name or not brief:
            logger.error("Task data is missing 'task' or 'brief'. Skipping deployment.")
            return

        # --- Round 2 secret verification ---
        if round_number == 2:
            provided_secret = task_data.get("secret")
            if ROUND2_SECRET != provided_secret:
                logger.error("❌ Round 2 secret verification failed. Aborting deployment.")
                return

        local_repo_path = f"output/{repo_name}"
        deploy_info = None

        # --- Round 1: Initial deployment ---
        if round_number == 1:
            logger.info(f"Round 1: Creating new repo for '{repo_name}'")
            deploy_info = deploy_to_github(local_repo_path, repo_name, brief, attachments)

        # --- Round 2: Revision deployment ---
        elif round_number == 2:
            logger.info(f"Round 2: Revising repo '{repo_name}'")
            deploy_info = handle_revision_and_deploy(local_repo_path, repo_name, brief, attachments)

        # --- Notify evaluation server ---
        if deploy_info:
            logger.info("✅ Deployment successful. Preparing evaluation notification.")
            evaluation_url = task_data.get("evaluation_url")

            if evaluation_url:
                notification_payload = {
                    "email": task_data.get("email"),
                    "task": repo_name,
                    "round": round_number,
                    "nonce": task_data.get("nonce"),
                    "repo_url": deploy_info.get("repo_url"),
                    "commit_sha": deploy_info.get("commit_sha"),
                    "pages_url": deploy_info.get("pages_url"),
                }
                try:
                    logger.info(f"Sending notification to evaluation server: {notification_payload}")
                    response = requests.post(evaluation_url, json=notification_payload, timeout=30)
                    response.raise_for_status()
                    logger.info("✅ Successfully notified evaluation server.")
                except requests.exceptions.RequestException as e:
                    logger.error(f"Failed to notify evaluation server: {e}")
            else:
                logger.warning("No evaluation_url provided. Skipping notification.")
        else:
            logger.error("Deployment failed. No notification sent.")

    except Exception as e:
        logger.error(f"Unexpected error during build process: {e}", exc_info=True)

# -------------------------
# API Endpoints
# -------------------------
@app.post("/api-endpoint")
async def handle_task_request(request: Request, background_tasks: BackgroundTasks):
    """
    Receives a task request and triggers background deployment.
    """
    try:
        task_data = await request.json()
        logger.info(f"Received task request for: {task_data.get('task')}")
        background_tasks.add_task(run_the_build_process, task_data)
        return {"message": "Task received and is being processed in background."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")


@app.get("/")
def read_root():
    """
    Health check endpoint.
    """
    return {"status": "AI App Generator backend is running."}
