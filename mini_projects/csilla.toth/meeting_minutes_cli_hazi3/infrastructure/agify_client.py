import requests

class AgifyClient:
    BASE_URL = "https://api.agify.io"

    def get_age(self, name: str) -> int:
        response = requests.get(self.BASE_URL, params={"name": name}, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get("age") or 0
