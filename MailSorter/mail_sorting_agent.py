import sys
import os
from dotenv import load_dotenv
from utils.Agent import ToolCallingAgent
login()

def prompt(emailsToSort: int) -> str:
    f"""
    You are an expert assistant specialized in classification.
    Your task is to retrieve and classify the {emailsToSort} most recent emails into existing folders using the tools are your disposal.
    """

if __name__ == "__main__":
    load_dotenv(
        dotenv_path="../.env"
    )
    
    # initiate the agent and grant it its tools
    agent = ToolCallingAgent(
        tools=[

        ],
        model=HfApiModel(
            token=os.getenv("HF_API_KEY"),
            model_id=
        )
    )
    
    # get the number of emails to sort
    if len(sys.argv) < 2:
        emailsToSort = 50
    else:
        emailsToSort = sys.argv[1]
    
    result = agent.run(prompt(emailsToSort))
    print(result)