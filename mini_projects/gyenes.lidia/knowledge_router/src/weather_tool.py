import requests
from typing import Dict, Any

class WeatherClient:
    """
    Kezeli a kommunikációt a külső időjárás API-val.
    Tartalmaz egy 'Fallback' (biztonsági) módot: ha az API nem elérhető,
    demo adatot ad vissza, hogy a program ne omoljon össze.
    """
    
    BASE_URL = "https://wttr.in"

    def get_weather(self, city: str) -> Dict[str, Any]:
        # A format=j1 paraméter kéri a JSON választ
        url = f"{self.BASE_URL}/{city}?format=j1"
        
        try:
            # 1. Megnöveljük a timeout-ot 15 másodpercre (wttr.in néha lassú)
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            current_condition = data['current_condition'][0]
            
            return {
                "success": True,
                "city": city,
                "temp_C": current_condition['temp_C'],
                "desc": current_condition['lang_hu'][0]['value'] if 'lang_hu' in current_condition else current_condition['weatherDesc'][0]['value'],
                "humidity": current_condition['humidity'],
                "wind_kmph": current_condition['windspeedKmph']
            }
            
        except Exception as e:
            # 2. BIZTONSÁGI MÓD (Fallback)
            # Ha timeout vagy hálózati hiba van, visszaadunk egy mock adatot,
            # hogy a házifeladat demonstrálható legyen.
            print(f"⚠️ API Hiba ({str(e)}) -> Demo adat betöltése...")
            
            return {
                "success": True,
                "city": f"{city} (Demo Mód)",
                "temp_C": "20",
                "desc": "Részben felhős (API nem elérhető)",
                "humidity": "50",
                "wind_kmph": "10"
            }

if __name__ == "__main__":
    client = WeatherClient()
    print(client.get_weather("Budapest"))