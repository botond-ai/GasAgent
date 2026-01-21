import httpx

class OpenAIGateway:
    EMBEDDING_URL = "https://api.openai.com/v1/embeddings"
    COMPLETION_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, completion_model: str, embedding_model: str):
        self.api_key = api_key
        self.completion_model = completion_model
        self.model = embedding_model
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def get_completion_response(self, messages: list[dict[str, str]]) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.COMPLETION_URL,
                headers=self.headers,
                json={
                    "model": self.completion_model,
                    "messages": messages,
                    "temperature": 0.2,
                }
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()

    async def get_completion(self, prompt, context, history):
        messages = [{
            "role": "user",
            "content": "Context is in json format, and it contains 'texts' field with relevant information. It also contains 'sources' with the source of the information. Include that in your answer as citation."
        }, {
            "role": "user",
            "content": f"Context: {context}\n\nQuestion: {prompt}"
        }]

        if history:
            for q, a in history:
                messages.append({
                    "role": "user",
                    "content": q
                })
                messages.append({
                    "role": "assistant",
                    "content": a
                })

        return await self.get_completion_response(messages)

    async def get_embedding(self, text):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.EMBEDDING_URL,
                headers=self.headers,
                json={
                    "input": text,
                    "model": self.model
                }
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]

    async def classify_intent(self, query: str) -> str:
        prompt: str = f"""Classify this query into exactly one domain:
        - hr: vacation, benefits, hiring, payroll
        - it: technical support, software issues, hardware issues, VPN, access
        - finance: invoice, expense, budget, reimbursement
        - legal: compliance, contract, policy, regulation, GDPR
        - marketing: campaign, branding, social media, advertising
        - general: any other query not in the above domains

            Query: {query}

        Return only the domain name as a single word.
        """
        message = [{"role": "user", "content": prompt}]
        result = await self.get_completion_response(message)
        return result.lower()

