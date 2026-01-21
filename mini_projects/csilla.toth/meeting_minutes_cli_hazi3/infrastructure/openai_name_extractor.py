import os
from typing import Set
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class OpenAINameExtractor:
    """
    OpenAI API-t használ a meeting szövegből
    résztvevők nevének kinyerésére.
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY nincs beállítva a .env fájlban")

        self.client = OpenAI(api_key=api_key)

    def extract(self, text: str) -> Set[str]:
        prompt = f"""
Extract the participants' first names from the meeting notes below.
Return ONLY a comma-separated list of unique names.
No explanations.

Meeting notes:
{text}
"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You extract participant names from meeting notes."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )

        content = response.choices[0].message.content.strip()

        names = {name.strip() for name in content.split(",") if name.strip()}
        return names
