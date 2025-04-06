import requests
import json
from dotenv import load_dotenv
from os import getenv

# specifications = """
# You should think step by step in order to fullfill the objective by reasoning in a clear Thought/Action/Observation pattern.
# Before starting the loop, write a clear plan on how to achieve the objective. Then, start the loop:
# - You should first reflect with `Thought: {your_thoughts}` on the current situation.
# During this step, if the objective is achieved, write your final answer/observation in the following format `Final Answer: {your_answer}`.
# - Then, in an Action step, call one or several of the tools at your disposal in the format `Action: {JSON_BLOB}` to achieve the objective.
# - After this you will receive the result of your Action step. You should reflect on this result and update your plan if necessary in the format `Observation: {result}`.
# """

def get_inference(input: str) -> str:
    # Load the API key from the environment variable
    load_dotenv()

    # Make the API request
    response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {getenv('OPENROUTER_DEEPSEEK_V3_0324')}",
    },
    data=json.dumps({
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": [
        {
            "role": "system",
            "content": f"{input} + {specifications}"
        }
        ]
    })
    )

    # Check for errors
    if response.status_code != 200:
        raise Exception(f"Request failed with status code {response.status_code}: {response.text}")
    if "choices" not in response.json() or len(response.json()["choices"]) == 0:
        raise Exception("Invalid response structure: 'choices' not found or empty")
    
    # Extract the content from the response
    return response.json().get("choices")[0].get("message").get("content")

if __name__ == "__main__":
    input = "In three words, what's the meaning of life?"
    result = get_inference(input)
    print(result)