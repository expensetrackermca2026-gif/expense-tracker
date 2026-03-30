import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GOOGLE_API_KEY')
print(f"API Key: {api_key[:10]}...")

genai.configure(api_key=api_key)

try:
    model = genai.GenerativeModel(
        model_name='gemini-flash-latest',
        system_instruction="You are a helpful assistant."
    )
    chat = model.start_chat(history=[])
    response = chat.send_message("hi")
    print(f"Response: {response.text}")
except Exception as e:
    import traceback
    traceback.print_exc()
