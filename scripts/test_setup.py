"""Smoke test: verify dependencies, .env loading, and a live Claude Haiku call."""
import os
import requests  # noqa: F401
import pandas  # noqa: F401
import anthropic
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
assert api_key, "ANTHROPIC_API_KEY not found in .env"
print(f"API key loaded (length={len(api_key)})")

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=20,
    messages=[{"role": "user", "content": 'Reply with exactly: hello world'}],
)
print("Claude response:", response.content[0].text)
