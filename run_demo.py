from app.agent.graph import run_agent_graph # Using the new graph-based controller
import json
from dotenv import load_dotenv
from app.agent.perception import init_openai_client as init_perception
from app.agent.reasoning import init_openai_client as init_reasoning
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    load_dotenv() # Load environment variables for the demo script
    init_perception()
    init_reasoning()

    # Simulate an incoming email from a candidate
    test_email = {
        "thread_id": "divyavuppula7364@gmail.com",
        "content": "Hi, I am interested in the opportunity. Can you share more details?"
    }

    print(f"--- Simulating Automatic Reply from {test_email['thread_id']} ---\n{test_email['content']}\n")
    
    response = run_agent_graph(test_email)
    
    print(f"\n--- Graph Decision ---\n{json.dumps(response, indent=2)}")