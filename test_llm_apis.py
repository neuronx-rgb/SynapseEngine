import os
from dotenv import load_dotenv
from google import genai
from groq import Groq

load_dotenv()

print("=" * 50)
print("TESTING GEMINI")
print("=" * 50)

gemini_key = os.getenv("GEMINI_API_KEY")

if not gemini_key:
    print("❌ GEMINI_API_KEY not found")
else:
    try:
        client = genai.Client(api_key=gemini_key)

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents="Reply with exactly: Gemini connection successful."
        )

        print("✅ Gemini connected")
        print("Response:", response.text)

    except Exception as e:
        print("❌ Gemini failed")
        print("Error:", e)


print("\n" + "=" * 50)
print("TESTING GROQ")
print("=" * 50)

groq_key = os.getenv("GROQ_API_KEY")

if not groq_key:
    print("❌ GROQ_API_KEY not found")
else:
    try:
        client = Groq(api_key=groq_key)

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "user",
                    "content": "Reply with exactly: Groq connection successful."
                }
            ],
            max_tokens=50
        )

        print("✅ Groq connected")
        print("Response:", response.choices[0].message.content)

    except Exception as e:
        print("❌ Groq failed")
        print("Error:", e)


print("\n" + "=" * 50)
print("TEST COMPLETE")
print("=" * 50)