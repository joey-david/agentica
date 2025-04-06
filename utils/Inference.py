import requests
import json
from dotenv import load_dotenv
from os import getenv

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
                "content": f"{input}"
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
    print(get_inference("What's the meaning of life, in three words?"))