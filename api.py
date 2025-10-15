import os
import logging
import requests
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from dotenv import load_dotenv

# Import all the final functions from your completed agent.py
from agent import (
    generate_code,
    save_and_prepare_repo,
    deploy_to_github,
    handle_revision_and_deploy
)

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)

app = FastAPI()

def run_the_build_process(task_data: dict):
    """
    This is the main background task router.
    It checks the 'round' and calls the appropriate handler function.
    """
    try:
        round_number = task_data.get("round", 1)
        repo_name = task_data.get("task")
        brief = task_data.get("brief")
        
        if not repo_name or not brief:
            logging.error("Task data is missing 'brief' or 'task' key.")
            return

        deploy_info = None
        # --- Main Router Logic ---
        if round_number == 1:
            logging.info(f"Handling Round 1: Creating new repo for '{repo_name}'")
            generated_html = generate_code(brief, task_data.get("attachments"))
            if generated_html:
                local_repo_path = f"output/{repo_name}"
                # <-- UPDATED FUNCTION CALL
                save_and_prepare_repo(local_repo_path, brief, repo_name, generated_html)
                deploy_info = deploy_to_github(local_repo_path, repo_name)
        
        elif round_number == 2:
            logging.info(f"Handling Round 2: Revising repo for '{repo_name}'")
            app_secret = os.getenv("APP_SECRET")
            request_secret = task_data.get("secret")
            if not request_secret or request_secret != app_secret:
                logging.error("Round 2 request missing or has invalid 'secret'. Aborting.")
                return
            logging.info("Secret verified successfully.")
            
            local_repo_path = f"output/{repo_name}"
            deploy_info = handle_revision_and_deploy(local_repo_path, repo_name, brief)

        else:
            logging.error(f"Unknown round number: {round_number}")
            return
            
        # --- Final Notification Logic (runs for both rounds) ---
        if deploy_info:
            logging.info(f"Deployment successful. Preparing notification.")
            evaluation_url = task_data.get("evaluation_url")
            if evaluation_url:
                notification_payload = {
                    "email": task_data.get("email"),
                    "task": task_data.get("task"),
                    "round": task_data.get("round"),
                    "nonce": task_data.get("nonce"),
                    "repo_url": deploy_info.get("repo_url"),
                    "commit_sha": deploy_info.get("commit_sha"), # Now correctly populated
                    "pages_url": deploy_info.get("pages_url"),
                }
                try:
                    logging.info(f"Notifying evaluation server: {notification_payload}")
                    response = requests.post(evaluation_url, json=notification_payload)
                    response.raise_for_status()
                    logging.info("Successfully notified evaluation server.")
                except requests.exceptions.RequestException as e:
                    logging.error(f"Failed to notify evaluation server: {e}")
            else:
                logging.warning("No evaluation_url found. Skipping notification.")
        else:
            logging.error("Deployment failed. No notification sent.")

    except Exception as e:
        logging.error(f"An unexpected error occurred in the background task: {e}", exc_info=True)


@app.post("/api-endpoint")
async def handle_task_request(request: Request, background_tasks: BackgroundTasks):
    """
    This endpoint receives the task, returns an immediate 200 OK,
    and starts the build process in the background.
    """
    try:
        task_data = await request.json()
        logging.info(f"Received request for task: {task_data.get('task')}")
        background_tasks.add_task(run_the_build_process, task_data)
        return {"message": "Task received and is being processed."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

@app.get("/")
def read_root():
    return {"status": "AI App Generator is running."}