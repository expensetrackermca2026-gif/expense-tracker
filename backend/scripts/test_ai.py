import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY')
print(f"Key Found: {api_key[:10]}...")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-flash-latest')

with open('test_receipt.jpg', "rb") as f:
    image_data = f.read()

prompt = """
You are a receipt analysis engine.
Extract structured financial data from this receipt.
Return ONLY valid JSON.

{
  "merchant": "string",
  "total_amount": number,
  "currency": "string",
  "date": "YYYY-MM-DD",
  "category": "Food/Travel/Shopping/Bills/Health/others",
  "confidence_score": number
}
No extra text allowed.
"""

try:
    print("Sending Request...")
    response = model.generate_content([prompt, {'mime_type': 'image/jpeg', 'data': image_data}])
    print("Response Received:")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
