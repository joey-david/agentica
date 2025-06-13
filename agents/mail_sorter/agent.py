from core.agent import ToolCallingAgent
from core.utils.config import load_agent_config
from agents.mail_sorter.tools import (
    login,
    getUnclassifiedEmails,
    getUnreadUnclassifiedEmails,
    getEmailFullBody,
    getExistingLabels,
    createLabels,
    deleteLabels,
    sortEmails
)

config = load_agent_config(agent_name="mail_sorter")
NAME = config["name"]
DESCRIPTION = config["description"]
PERSISTENT_PROMPT = config.get("persistent prompt") or ""
MAX_STEPS = config.get("max steps", 20)

print(NAME)
print(DESCRIPTION)
user_prompt = input("Prompt: ")
Agent = ToolCallingAgent(
    tools=[login, getUnclassifiedEmails, getUnreadUnclassifiedEmails, getEmailFullBody, getExistingLabels, createLabels, deleteLabels, sortEmails],
    persistent_prompt=PERSISTENT_PROMPT,
    user_prompt=user_prompt,
    max_steps=MAX_STEPS
)

def main():
    results = Agent.run()
    print(results)

if __name__ == "__main__":
    main()