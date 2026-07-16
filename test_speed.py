import os, time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.environ.get("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1"),
    api_key=os.environ.get("LLM_API_KEY"),
)

start = time.time()
resp = client.chat.completions.create(
    model=os.environ.get("LLM_MODEL", "meta/llama-3.3-70b-instruct"),
    messages=[{"role": "user", "content": "Say hello in 5 words."}],
    timeout=10,
)
print(f"Took {time.time() - start:.1f}s")
print(resp.choices[0].message.content)