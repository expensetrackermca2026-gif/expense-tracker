import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY')
print(f"Testing with Key: {api_key}")

genai.configure(api_key=api_key)

def test_model(model_name):
    print(f"\n--- Testing Model: {model_name} ---")
    try:
        model = genai.GenerativeModel(model_name)
        with open('test_receipt.jpg', "rb") as f:
            image_data = f.read()
            
        print("Sending request...")
        response = model.generate_content(["Tell me what is this image", {'mime_type': 'image/jpeg', 'data': image_data}])
        print("SUCCESS!")
        print(response.text)
    except Exception as e:
        print(f"FAILED: {e}")

test_model('gemini-flash-latest')
test_model('gemini-2.0-flash')
test_model('gemini-2.5-flash')
