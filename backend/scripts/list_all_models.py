import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=api_key)

print("Listing all models and checking for vision support:")
for m in genai.list_models():
    methods = [str(meth) for meth in m.supported_generation_methods]
    if 'generateContent' in methods:
        # Check if it supports vision
        # Some models have 'vision' in name or support multimodal
        print(f"- {m.name} | Methods: {methods}")
