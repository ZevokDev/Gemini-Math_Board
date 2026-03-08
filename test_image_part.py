from google import genai
from google.genai import types

# Just checking types
p = types.Part.from_bytes(data=b"test", mime_type="image/jpeg")
print(p.inline_data.data)
