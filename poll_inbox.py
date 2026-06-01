import os
import imaplib
import email
import email.utils
import re
import time
import logging
from dotenv import load_dotenv
from app.agent.graph import run_agent_graph # Using the new graph-based controller
from app.memory.db import get_thread
from app.agent.perception import init_openai_client as init_perception
from app.agent.reasoning import init_openai_client as init_reasoning
from app.config_validator import validate_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set to True for testing to respond to any incoming email
BYPASS_OUTREACH_CHECK = False

def _extract_email_body(msg):
    """
    Extracts the plain text body from an email message.
    Prioritizes text/plain over text/html, stripping HTML tags if only HTML is available.
    """
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            # Prioritize text/plain, ignoring attachments
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(errors='replace').strip() # Return immediately if plain text found
                except Exception as e:
                    logger.warning(f"Failed to decode text/plain part: {e}")
            # Fallback to text/html if no plain text found yet, stripping tags
            elif content_type == "text/html" and not body and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        html = payload.decode(errors='replace')
                        body = re.sub('<[^<]+?>', '', html).strip() # Simple regex to strip HTML tags
                except Exception as e:
                    logger.warning(f"Failed to decode text/html part: {e}")
    else: # Not multipart, assume single part
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(errors='replace').strip()
        except Exception as e:
            logger.warning(f"Failed to decode single part email: {e}")
    return body

def poll_inbox():
    """
    Continuously monitors Gmail inbox for unread emails.
    Processes replies from prospects and triggers agent response.
    """
    load_dotenv()
    
    # Validate config before starting
    try:
        validate_config()
    except SystemExit as e:
        logger.error("Configuration validation failed. Exiting.")
        return
    
    init_perception()
    init_reasoning()
    
    # Gmail IMAP settings
    mail_host = os.getenv("EMAIL_HOST", "imap.gmail.com")
    mail_user = os.getenv("EMAIL_USERNAME")
    mail_pass = os.getenv("EMAIL_PASSWORD")
    poll_interval = int(os.getenv("POLL_INTERVAL", 30))

    if not all([mail_user, mail_pass]):
        logger.error("Email credentials (EMAIL_USERNAME/EMAIL_PASSWORD) missing in .env")
        return

    mail = None
    connection_retries = 0
    max_retries = 3
    
    # Batch processing settings to avoid rate limits
    BATCH_LIMIT = 3 

    try:
        while True:
            try:
                # Ensure connected
                if mail is None:
                    logger.info(f"Connecting to {mail_host}...")
                    mail = imaplib.IMAP4_SSL(mail_host, timeout=30)
                    mail.login(mail_user, mail_pass)
                    logger.info(f"✓ Chatbot Online: {mail_user}. Monitoring inbox...")
                    connection_retries = 0
                
                # Heartbeat to show the script is active
                logger.info("Polling inbox for new unread messages...")

                # Select inbox and search for unread emails
                mail.select("INBOX")
                status, messages = mail.search(None, 'UNSEEN')
                
                if status != "OK":
                    logger.warning(f"Search failed: {status}")
                    time.sleep(poll_interval)
                    continue
                
                msg_ids = messages[0].split()
                if not msg_ids:
                    # No new emails
                    time.sleep(poll_interval)
                    continue
                
                # Limit checking to the 3 most recent unread messages
                msg_ids = msg_ids[-3:]
                logger.info(f"Checking {len(msg_ids)} most recent unread email(s)")
                
                processed_count = 0
                # Process newest to oldest
                for num in reversed(msg_ids):
                    if processed_count >= BATCH_LIMIT:
                        logger.info(f"Reached batch limit of {BATCH_LIMIT}. Pausing until next poll.")
                        break
                        
                    try:
                        res, msg_data = mail.fetch(num, "(RFC822)")
                        if res != "OK":
                            logger.warning(f"Failed to fetch message {num}")
                            continue
                        
                        for response_part in msg_data:
                            if not isinstance(response_part, tuple):
                                continue
                            
                            try:
                                msg = email.message_from_bytes(response_part[1])
                            except Exception as e:
                                logger.error(f"Failed to parse email: {e}")
                                continue
                            
                            # Extract sender
                            sender = msg.get("From")
                            if not sender:
                                logger.warning("Email has no From header, skipping")
                                continue
                            
                            try:
                                parsed_addr = email.utils.parseaddr(sender)[1]
                            except Exception as e:
                                logger.error(f"Failed to parse sender address: {e}")
                                continue
                            
                            if not parsed_addr:
                                logger.warning(f"Could not parse sender address from: {sender}")
                                continue
                            
                            from_email = parsed_addr.lower().strip()
                            subject = msg.get("Subject", "(no subject)")

                            # STRICT ALLOWLIST CHECK
                            if from_email != "XXXXXX@gmail.com":
                                logger.info(f"  └─ [SECURITY] Skipping {from_email}: Agent is restricted to XXXXX@gmail.com")
                                continue
                            
                            # Check for Auto-Submitted header (standard for bots/alerts)
                            auto_submitted = msg.get("Auto-Submitted", "").lower()

                            logger.info(f"Checking email from: {from_email}")

                            # Expanded list of automated/newsletter senders
                            ignored_patterns = [
                                "no-reply", "noreply", "newsletter", "notifications", "student@mailers",
                                "coursera", "databricks", "mailer-daemon", "googlemail", "instahyre",
                                "wellfound", "meta.com", "docusign", "amazon", "aws", "github",
                                "postmaster", "bounce", "alert", "support", "info@"
                            ]
                            if any(pattern in from_email for pattern in ignored_patterns) or auto_submitted:
                                logger.info(f"  └─ Ignoring automated or service sender: {from_email}")
                                # Optional: Mark as read so we don't check it again
                                mail.store(num, '+FLAGS', '\\Seen')
                                continue
                            
                            # Extract email body using helper function
                            body = _extract_email_body(msg)
                            
                            # Only process replies from prospects we have already contacted
                            thread = get_thread(from_email, create_if_missing=False)
                            
                            # STRICT CHECK: Only process if the thread exists AND the agent (Alex) 
                            # initiated the conversation via outreach.py.
                            has_outreach = thread and any(m.get("sender") == "agent" for m in thread.get("history", []))
                            
                            if not BYPASS_OUTREACH_CHECK and not has_outreach:
                                logger.info(f"  └─ Skipping {from_email}: No existing outreach history found in DB.")
                                continue
                            
                            # Safety: Truncate body to avoid token limits
                            safe_body = body[:3000] if body else ""

                            if not safe_body:
                                logger.warning(f"Email body is empty from {from_email}, skipping")
                                continue
                            
                            logger.info(f"Processing reply from {from_email} - Subject: {subject}")
                            
                            processed_count += 1
                            
                            # Pass to agent controller
                            try:
                                payload = {
                                    "thread_id": from_email, 
                                    "content": safe_body,
                                    "subject": subject,
                                    "message_id": msg.get("Message-ID")
                                }
                                run_agent_graph(payload)
                                # Small sleep to help avoid 429 Too Many Requests
                                time.sleep(2)
                            except Exception as e:
                                if "Rate limit reached" in str(e) or "429" in str(e):
                                    logger.error(f"🛑 OpenAI Rate Limit Reached. Error: {e}")
                                    time.sleep(60) # Wait a minute before trying next email
                                    continue
                                logger.error(f"Agent failed to process email from {from_email}: {e}")
                                # Don't mark as read - let user know something went wrong
                                continue
                            
                            # Mark as read after successful processing
                            try:
                                mail.store(num, '+FLAGS', '\\Seen')
                            except Exception as e:
                                logger.warning(f"Failed to mark email {num} as read: {e}")
                    
                    except Exception as e:
                        logger.error(f"Error processing email {num}: {e}", exc_info=True)
                        continue
                
                # Wait before next poll
                time.sleep(poll_interval)

            except imaplib.IMAP4.abort:
                logger.warning("IMAP connection lost (abort), reconnecting...")
                mail = None
                connection_retries += 1
                if connection_retries >= max_retries:
                    logger.error(f"Failed to reconnect after {max_retries} attempts, exiting")
                    break
                time.sleep(5)
            
            except (imaplib.IMAP4.error, OSError) as e:
                logger.warning(f"IMAP connection error: {e}, reconnecting...")
                mail = None
                connection_retries += 1
                if connection_retries >= max_retries:
                    logger.error(f"Failed to reconnect after {max_retries} attempts, exiting")
                    break
                time.sleep(5)

    except KeyboardInterrupt:
        logger.info("Poll loop interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error in polling loop: {e}", exc_info=True)
    finally:
        if mail:
            try:
                mail.logout()
                logger.info("Logged out of mail server")
            except Exception as e:
                logger.warning(f"Error during logout: {e}")

if __name__ == "__main__":
    poll_inbox()
