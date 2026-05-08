import os
import sys
from dotenv import load_dotenv
from app.agent.reasoning import generate_initial_outreach_message, init_openai_client
from app.agent.action import execute_action
from app.memory.db import save_message, get_thread
from app.config_validator import validate_config
import logging
from poll_inbox import poll_inbox

# Configure logging for this script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set to True to bypass the history check for testing
FORCE_OUTREACH = True

if __name__ == "__main__":
    load_dotenv() # Load environment variables

    # Validate configuration before starting outreach
    try:
        validate_config()
    except SystemExit:
        sys.exit(1)

    init_openai_client() # Initialize OpenAI client for reasoning module

    prospect_emails = [
        "vuppuladivya7364@gmail.com",

    ]

    logger.info(f"Initiating outreach to {len(prospect_emails)} prospect(s) (XXYYZZ)...")

    for email in prospect_emails:
        # Check if we have already contacted this prospect to avoid spamming
        thread = get_thread(email, create_if_missing=False)
        if not FORCE_OUTREACH and thread and thread.get("history"):
            logger.info(f"Skipping {email}: Previous conversation history found.")
            continue

        logger.info(f"Chatbot is generating initial outreach for Prospect (XXYYZZ): {email}...")
        # Generate the message and subject using the reasoning module
        outreach_decision = generate_initial_outreach_message()
        outreach_decision["action"] = "INITIAL_OUTREACH" # Explicitly set action for execute_action
        
        # Execute the action (send email and save to DB)
        execute_action(outreach_decision, email)
        logger.info(f"Initial outreach sent to Prospect (XXYYZZ): {email}.")

    logger.info("Outreach initiation complete.")

    logger.info("Transitioning to automatic inbox polling...")
    poll_inbox()
