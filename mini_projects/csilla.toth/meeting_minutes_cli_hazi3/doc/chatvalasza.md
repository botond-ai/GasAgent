
Rendben — alább kapsz egy teljes, futtatható Python CLI alkalmazást, amely:

SOLID elvek szerint van felépítve

VS Code-barát projektstruktúrát használ

bemeneti szövegből kinyeri a résztvevők neveit

set-ben tárolja őket (nincs duplikáció)

minden névre Agify API-val életkort becsül

az eredményt név → életkor formában kiírja

📁 Projektstruktúra (ajánlott)
meeting_minutes_cli/
│
├── main.py
├── cli/
│   └── app.py
├── domain/
│   └── participant.py
├── services/
│   ├── name_extractor.py
│   └── age_estimator.py
├── infrastructure/
│   └── agify_client.py
└── requirements.txt

🧠 SOLID elvek röviden, hogyan jelennek meg

S – Single Responsibility

NameExtractor → csak nevek kinyerése

AgifyClient → csak HTTP kommunikáció

AgeEstimator → csak becslési logika

O – Open/Closed

Más API könnyen cserélhető

L – Liskov

API kliens interfész szerint használható

I – Interface Segregation

Kicsi, célzott absztrakciók

D – Dependency Inversion

AgeEstimator nem konkrét API-tól függ

+ kódok.
Ezt követően kiegészítés:

Rendben — kibővítjük ugyanezt a projektet úgy, hogy:

✅ a name_extractor.py helyett OpenAI API végezze a névkinyerést

✅ az API-kulcs .env fájlból legyen betöltve

✅ a SOLID elvek megmaradjanak

✅ az alkalmazás továbbra is CLI, VS Code-barát

✅ Agify API változatlanul működjön

Megjegyzés: az OpenAI API használatához kulcs szükséges, ezt te adod meg a .env fájlban.

+ 📁 Frissített projektstruktúra 