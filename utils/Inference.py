import requests
import json
from dotenv import load_dotenv
from os import getenv
from openai import OpenAI


# def get_inference(input: str) -> str:
#     """
#     Makes an API request to OpenAI's DeepSeek model for inference.

#     Args:
#         input (str): The input string to be sent to the model.

#     Returns:
#         str: The model's response.
#     """
#     # Load the API key from the environment variable
#     load_dotenv()
#     base_url = "https://api.deepseek.com"
#     client = OpenAI(api_key=getenv("DEEPSEEK_KEY"), base_url=base_url)
#     response = client.chat.completions.create(
#         model="deepseek-chat",
#         messages=[
#             {
#                 "role": "system",
#                 "content": f"{input}"
#             }
#         ],
#         )
#     # Check for errors
#     # Extract the content from the response
#     return response.choices[0].message.content
    

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