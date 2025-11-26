from openai import OpenAI

client = OpenAI(api_key="")

class RealLLM:
    def __call__(self, prompt: str):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content

llm = RealLLM()
