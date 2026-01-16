# AI Weather Agent - Frontend

Modern web interface for the AI Weather Agent.

## Fájlok

- **index.html** - Fő HTML oldal
- **app.js** - JavaScript logika (API kommunikáció)
- **styles.css** - Stílusok és responsive design

## Használat

### 1. Indítsd el az API szervert

Egy terminálban:

```bash
cd /opt/hw3
source venv/bin/activate
python src/api.py
```

Az API a `http://localhost:5000` címen fog futni.

### 2. Nyisd meg a frontendot

Egy másik terminálban (vagy egyszerűen dupla kattintással):

```bash
# Böngészőben nyisd meg:
cd /opt/hw3/front
python3 -m http.server 8000

# Majd menj a böngészőben:
# http://localhost:8000
```

Vagy egyszerűen nyisd meg az `index.html` fájlt közvetlenül a böngészőben.

## Funkciók

- ✅ Modern, reszponzív design
- ✅ Chat-szerű interfész
- ✅ Valós idejű válaszok
- ✅ Hibakezelés és loading állapotok
- ✅ API health check
- ✅ XSS védelem

## API Végpontok

- **POST /api/ask** - Kérdés küldése
  ```json
  {
    "question": "Milyen az időjárás Budapesten?"
  }
  ```

- **GET /api/health** - API health check

## Technológiák

- Vanilla JavaScript (ES6+)
- CSS3 (CSS Grid, Flexbox, Animations)
- Fetch API
- Responsive Design
