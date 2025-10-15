import os
import logging
import requests
import subprocess
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from dotenv import load_dotenv
from agent import deploy_to_github, handle_revision_and_deploy

load_dotenv()
logging.basicConfig(level=logging.INFO)
app = FastAPI()

def run_the_build_process(task_data: dict):
    # --- START FINAL DEBUG CODE ---
    logging.info("--- INSPECTING RUNTIME ENVIRONMENT ---")
    try:
        result = subprocess.run("ls -R", shell=True, check=True, capture_output=True, text=True)
        logging.info("--- FILE LISTING START ---")
        logging.info("\n" + result.stdout)
        logging.info("--- FILE LISTING END ---")
    except Exception as e:
        logging.error(f"Failed to list files: {e}")
    # --- END FINAL DEBUG CODE ---

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
            deploy_info = deploy_to_github(local_repo_path, repo_name, brief, task_data.get("attachments"))
        
        elif round_number == 2:
            logging.info("Round 2 logic needs to be fully implemented.")
            # Example call for when you implement it
            # local_repo_path = f"output/{repo_name}"
            # deploy_info = handle_revision_and_deploy(local_repo_path, repo_name, brief, task_data.get("attachments"))

        if deploy_info:
            logging.info(f"Deployment successful. Preparing notification.")
            # (Your notification logic would go here)
        else:
            logging.error("Deployment failed. No notification sent.")

    except Exception as e:
        logging.error(f"An unexpected error occurred in the main task process: {e}", exc_info=True)

@app.post("/api-endpoint")
async def handle_task_request(request: Request, background_tasks: BackgroundTasks):
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
