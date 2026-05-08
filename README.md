# Email AI Agent ("Alex")

An autonomous AI-powered recruitment assistant designed to manage candidate outreach, negotiate rates within budget constraints, and schedule interviews via email.

## 🚀 Overview

This agent utilizes a **Perception → Reasoning → Action** architecture to handle unstructured email communication. It mimics a human recruiter named "Alex" who is persistent, professional, and goal-oriented.

### Key Features
- **Autonomous Intent Analysis**: Uses LLMs to categorize candidate responses (Interest, Negotiation, Reschedule, etc.).
- **Safe Negotiation**: Hard-coded budget validation prevents the agent from exceeding financial ceilings.
- **Smart Scheduling**: Integration with a calendar service to propose and book available time slots.
- **Persistent Memory**: SQLAlchemy-backed SQLite database tracks conversation history and funnel status.
- **Robust Communication**: Gmail integration with exponential backoff retry logic and threading support.

## 🏗️ Architecture

The agent logic is split into three distinct phases:
1.  **Perception (`perception.py`)**: Transforms raw email text into structured intent data.
2.  **Reasoning (`reasoning.py`)**: Evaluates the intent against business rules (Budget, Gig description) to decide the next step.
3.  **Action (`action.py`)**: Executes the decision—sending emails, booking slots, or updating the database.

## 🛠️ Setup

### Prerequisites
- Python 3.8+
- OpenAI API Key
- Gmail Account with App Password (for IMAP/SMTP)

### Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install openai sqlalchemy python-dotenv
   ```
3. Create a `.env` file in the root directory:
   ```env
   OPENAI_API_KEY=your_key_here
   EMAIL_HOST=imap.gmail.com
   EMAIL_PORT=587
   EMAIL_USERNAME=your_email@gmail.com
   EMAIL_PASSWORD=your_app_password
   SENDER_EMAIL=your_email@gmail.com
   COMPANY_NAME="Your Company"
   GIG_DESCRIPTION="Software Engineer Role"
   BUDGET_CEILING=100
   CURRENCY=USD
   ```

## 📋 Usage

### 1. Initial Outreach
To start the recruitment funnel by sending the first batch of emails:
```bash
python outreach.py
```

### 2. Inbox Polling
To monitor for replies and process them autonomously:
```bash
python poll_inbox.py
```

### 3. Monitoring Data
To see a summary of all candidate threads and their current status:
```bash
python view_db.py
```

### 4. Testing
Run a local simulation of a candidate reply without sending real emails:
```bash
python run_demo.py
```

## 📁 Project Structure

- `app/agent/`: Core logic (Perception, Reasoning, Action, Graph flow).
- `app/memory/`: Database models and persistence logic.
- `app/prompts/`: System instructions and templates for the AI.
- `app/services/`: External integrations (Email, Calendar).
- `app/config.py`: Configuration management.
- `email_agent.db`: Local SQLite database (generated on first run).

## 🛡️ Safety & Guardrails
- **Repetition Shield**: Prevents the agent from sending identical messages in loops.
- **Budget Gatekeeper**: The Action layer overrides AI decisions if they violate the `BUDGET_CEILING`.
- **Security Allowlist**: Currently restricted to specific test recipients in `email_service.py` to prevent accidental spam.

---
*Developed as a high-performance recruitment automation tool.*
