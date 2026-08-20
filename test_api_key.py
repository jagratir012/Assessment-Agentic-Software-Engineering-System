"""Quick test to verify Anthropic API key works."""

import sys
sys.path.insert(0, r"C:\temp\apkg")

import anthropic

# Paste your key here directly
API_KEY = "sk-ant-######################################################################################"

# Try multiple model names to find which one works
models_to_try = [
    "claude-sonnet-4-20250514",
    "claude-sonnet-4-6",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-opus-4-20250514",
    "claude-haiku-4-20250514",
]

client = anthropic.Anthropic(api_key=API_KEY)

print(f"Testing API key: {API_KEY[:15]}...{API_KEY[-5:]}")
print(f"Key length: {len(API_KEY)} chars")
print("-" * 50)

for model in models_to_try:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "say ok"}],
        )
        print(f"✓ SUCCESS: {model} -> {response.content[0].text}")
        break
    except anthropic.NotFoundError as e:
        print(f"✗ 404: {model}")
    except anthropic.AuthenticationError as e:
        print(f"✗ AUTH ERROR: {model} -> {e}")
        break
    except Exception as e:
        print(f"✗ ERROR: {model} -> {type(e).__name__}: {e}")
