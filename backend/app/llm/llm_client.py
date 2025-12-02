from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
client = OpenAI()

class RealLLM:
    def __call__(self, prompt: str):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content

llm = RealLLM()
