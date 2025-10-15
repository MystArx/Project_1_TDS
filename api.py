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
    # --- START FINAL DEBUG CODE ---
    logging.info("--- INSPECTING RUNTIME ENVIRONMENT ---")
    try:
        # Run 'ls -R' to see all files and folders recursively
        result = subprocess.run("ls -R", shell=True, check=True, capture_output=True, text=True)
        logging.info("--- FILE LISTING START ---")
        logging.info("\n" + result.stdout)
        logging.info("--- FILE LISTING END ---")
    except Exception as e:
        logging.error(f"Failed to list files: {e}")
    # --- END FINAL DEBUG CODE ---

    # The rest of the function continues below
    try:
        round_number = task_data.get("round", 1)
        repo_name = task_data.get("task")
        brief = task_data.get("brief")
        
        if not repo_name or not brief:
            logging.error("Task data is missing 'brief' or 'task' key.")
            return

        deploy_info = None
        if round_number == 1:
            logging.info(f"Handling Round 1: Creating new repo for '{repo_name}'")
            local_repo_path = f"output/{repo_name}"
            # For debugging, we pass the brief directly
            deploy_info = deploy_to_github(local_repo_path, repo_name, brief)
        
        elif round_number == 2:
            logging.info("Round 2 logic not fully implemented in this version.")

        if deploy_info:
            logging.info(f"Deployment successful. Preparing notification.")
            # (Notification logic would go here)
        else:
            logging.error("Deployment failed. No notification sent.")

    except Exception as e:
        logging.error(f"An unexpected error occurred in the background task: {e}", exc_info=True)
            
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
