import os
from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
try:
    response = client.models.generate_content(
        model="gemini-3.1-flash-image-preview",
        contents="A simple math formula"
    )
    print("Content generation worked.")
except Exception as e:
    print(f"generate_content failed: {e}")

try:
    response = client.models.generate_images(
        model="gemini-3.1-flash-image-preview",
        prompt="A simple math formula",
        config=dict(number_of_images=1)
    )
    print("Image generation worked.")
except Exception as e:
    print(f"generate_images failed: {e}")
