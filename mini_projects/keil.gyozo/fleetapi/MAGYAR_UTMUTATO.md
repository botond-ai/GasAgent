# Fleet API Client - Magyar Használati Útmutató

## 📋 Tartalom

1. [Gyors kezdés](#gyors-kezdés)
2. [Architektúra](#architektúra)
3. [SOLID elvek](#solid-elvek)
4. [Tesztelés](#tesztelés)
5. [LangGraph integráció](#langgraph-integráció)
6. [Példák](#példák)

## 🚀 Gyors kezdés

### Telepítés

```bash
# Virtuális környezet létrehozása
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Függőségek telepítése
pip install -r requirements.txt

# Környezeti változók beállítása
cp .env.example .env
# Szerkeszd az .env fájlt a Fleet szerver adataiddal
```

### Alkalmazás indítása

```bash
# Fejlesztői mód (automatikus újratöltéssel)
make run

# Vagy közvetlenül:
uvicorn main:app --reload
```

Az API elérhető lesz: `http://localhost:8000`
- Swagger dokumentáció: `http://localhost:8000/docs`
- ReDoc dokumentáció: `http://localhost:8000/redoc`

## 🏗️ Architektúra

### Projekt Struktúra

```
📁 Fleet API Client
├── 📄 main.py                    # FastAPI alkalmazás belépési pont
├── 📄 config.py                  # Konfiguráció kezelés
├── 📄 models.py                  # Pydantic modellek
├── 📄 exceptions.py              # Egyéni kivételek
├── 📄 fleet_client.py            # Fleet API kliens szolgáltatás
├── 📄 langgraph_integration.py   # LangGraph eszközök
├── 📄 conftest.py                # Pytest konfigurációk
├── 📄 test_fleet_client.py       # Unit tesztek
├── 📄 examples.py                # Használati példák
└── 📄 requirements.txt           # Python függőségek
```

### Komponensek

#### 1. **Config (config.py)**
- Pydantic Settings használata
- Környezeti változók kezelése
- Típusbiztos konfiguráció

#### 2. **Models (models.py)**
- Pydantic modellek az API entitásokhoz
- Automatikus validáció
- Típusbiztosság

#### 3. **Fleet Client (fleet_client.py)**
- Üzleti logika
- API kommunikáció
- Dependency Injection

#### 4. **FastAPI App (main.py)**
- REST API végpontok
- Dependency injection
- Hibakezelés

## 🎯 SOLID Elvek

### Single Responsibility Principle (SRP)
**Egyetlen felelősség elve**

Minden osztálynak egyetlen felelőssége van:
- `FleetAPIClient`: Csak Fleet API műveleteket kezel
- `HTTPXClient`: Csak HTTP kommunikációt kezel
- `Settings`: Csak konfigurációt kezel

```python
# ✓ Jó példa - egy felelősség
class FleetAPIClient:
    async def list_hosts(self): ...
    async def get_host(self, host_id): ...

# ✗ Rossz példa - több felelősség
class GodClass:
    def list_hosts(self): ...
    def send_email(self): ...
    def calculate_taxes(self): ...
```

### Open/Closed Principle (OCP)
**Nyitva-zárva elv**

Az osztályok nyitottak a kiterjesztésre, de zártak a módosításra:

```python
# Absztrakt interfész - kiterjeszthető
class HTTPClientInterface(ABC):
    @abstractmethod
    async def get(self, url: str): ...

# Új implementáció - nincs szükség módosításra
class CustomHTTPClient(HTTPClientInterface):
    async def get(self, url: str):
        # Egyéni implementáció
        pass
```

### Liskov Substitution Principle (LSP)
**Liskov helyettesítési elv**

Bármely implementáció helyettesíthető az interfésszel:

```python
# Mindkettő helyettesíthető
def use_client(client: HTTPClientInterface):
    result = await client.get("/api/hosts")

# Működik HTTPXClient-tel
use_client(HTTPXClient())

# Működik MockHTTPClient-tel (teszteléskor)
use_client(MockHTTPClient())
```

### Interface Segregation Principle (ISP)
**Interfész szegregációs elv**

Fókuszált interfészek - csak a szükséges metódusok:

```python
# ✓ Jó - fókuszált interfész
class HTTPClientInterface:
    async def get(self, url: str): ...
    async def post(self, url: str): ...

# ✗ Rossz - túl sok metódus
class MassiveInterface:
    async def get(self): ...
    async def post(self): ...
    async def send_email(self): ...
    async def process_payment(self): ...
```

### Dependency Inversion Principle (DIP)
**Függőség megfordítás elve**

Magasszintű modulok absztrakciókra támaszkodnak:

```python
# ✓ Jó - absztrakcióra támaszkodik
class FleetAPIClient:
    def __init__(self, http_client: HTTPClientInterface):
        self.http_client = http_client

# ✗ Rossz - konkrét implementációra támaszkodik
class FleetAPIClient:
    def __init__(self):
        self.http_client = HTTPXClient()  # Szigorú függőség
```

## 🧪 Tesztelés

### Unit Tesztek Futtatása

```bash
# Minden teszt
make test

# Csak unit tesztek
make test-unit

# Részletes kimenet
pytest -v

# Coverage riporttal
pytest --cov=. --cov-report=html
```

### Teszt Példa

```python
@pytest.mark.asyncio
async def test_list_hosts(fleet_client, mock_http_client, sample_host_data):
    # Arrange - előkészítés
    mock_http_client.get_mock.return_value = {
        "hosts": [sample_host_data]
    }
    
    # Act - végrehajtás
    result = await fleet_client.list_hosts()
    
    # Assert - ellenőrzés
    assert len(result) == 1
    assert result[0].hostname == "test-host"
```

### Mock Használata

```python
# Dependency injection lehetővé teszi a mock-olást
def test_example(fleet_client, mock_http_client):
    # Mock beállítása
    mock_http_client.get_mock.return_value = {"data": "test"}
    
    # Tesztelendő kód
    result = await fleet_client.some_method()
    
    # Ellenőrzések
    assert result is not None
    mock_http_client.get_mock.assert_called_once()
```

## 🤖 LangGraph Integráció

### LangGraph Tool-ok

A Fleet API kliens könnyen használható LangGraph tool node-ként:

```python
from langgraph_integration import list_fleet_hosts, run_fleet_query

# LangGraph eszközként használható
@tool
async def list_fleet_hosts(page: int = 0, per_page: int = 10) -> str:
    """Lista hostokat a Fleet-ből."""
    client = create_fleet_client()
    hosts = await client.list_hosts(page, per_page)
    return str(hosts)
```

### Használat LangGraph-ban

```python
from langgraph_integration import FLEET_TOOLS
from langgraph.prebuilt import ToolNode

# Tool node létrehozása
tool_node = ToolNode(FLEET_TOOLS)

# Használat gráfban
workflow.add_node("fleet_tools", tool_node)
```

### Példa Futtatása

```bash
# LangGraph példa futtatása
make example-langgraph

# Vagy:
python langgraph_integration.py
```

## 📝 Példák

### 1. Bejelentkezés

```python
from fleet_client import create_fleet_client

client = create_fleet_client()

# Bejelentkezés
response = await client.login("user@example.com", "password")
print(f"Token: {response.token}")
```

### 2. Host-ok Listázása

```python
# Host-ok listázása oldaltöréssel
hosts = await client.list_hosts(page=0, per_page=10)

for host in hosts:
    print(f"{host.hostname} - {host.platform} - {host.status}")
```

### 3. Query Futtatása

```python
# Query futtatása specifikus host-okon
result = await client.run_query(
    query="SELECT * FROM processes LIMIT 10",
    host_ids=[1, 2, 3]
)
print(f"Campaign ID: {result.campaign_id}")
```

### 4. Label Létrehozása

```python
from models import LabelCreate

label = LabelCreate(
    name="Ubuntu Szerverek",
    query="SELECT 1 FROM os_version WHERE platform = 'ubuntu'",
    description="Összes Ubuntu szerver"
)

created_label = await client.create_label(label)
print(f"Label ID: {created_label.id}")
```

### 5. Policy Létrehozása

```python
from models import PolicyCreate

policy = PolicyCreate(
    name="Tűzfal Ellenőrzés",
    query="SELECT 1 WHERE EXISTS (SELECT 1 FROM iptables)",
    description="Ellenőrzi hogy a tűzfal be van-e kapcsolva",
    resolution="Kapcsold be a tűzfalat",
    critical=True
)

created_policy = await client.create_policy(policy)
print(f"Policy ID: {created_policy.id}")
```

### 6. Hibakezelés

```python
from exceptions import (
    AuthenticationError,
    ResourceNotFoundError,
    ValidationError
)

try:
    host = await client.get_host(999999)
except ResourceNotFoundError as e:
    print(f"Host nem található: {e.message}")
except AuthenticationError as e:
    print(f"Hitelesítési hiba: {e.message}")
except ValidationError as e:
    print(f"Validációs hiba: {e.message}")
```

## 🔧 Hasznos Parancsok

```bash
# Formázás
make format

# Linter futtatása
make lint

# Docker build
make docker-build

# Docker indítás
make docker-up

# Fejlesztői környezet beállítása
make setup-dev

# Összes ellenőrzés
make check
```

## 📚 További Információk

- **FastAPI dokumentáció**: https://fastapi.tiangolo.com/
- **Pydantic dokumentáció**: https://docs.pydantic.dev/
- **LangGraph dokumentáció**: https://langchain-ai.github.io/langgraph/
- **Fleet API dokumentáció**: https://fleetdm.com/docs/rest-api

## 💡 Tippek

1. **Környezeti változók**: Soha ne commitold a `.env` fájlt valódi hitelesítő adatokkal
2. **Tesztelés**: Írj teszteket minden új funkcióhoz
3. **Type hints**: Használj típus jelöléseket mindenhol
4. **Async/await**: Használd az async függvényeket IO műveletekhez
5. **Dependency Injection**: Injektálj függőségeket a könnyebb tesztelhetőségért

## 🎓 SOLID Elvek Összefoglalva

| Elv | Magyar Név | Rövid Leírás |
|-----|------------|--------------|
| **S**RP | Egyetlen Felelősség | Egy osztály = egy felelősség |
| **O**CP | Nyitva-Zárva | Nyitott kiterjesztésre, zárt módosításra |
| **L**SP | Liskov Helyettesítés | Altípusok helyettesíthetők |
| **I**SP | Interfész Szegregáció | Kis, fókuszált interfészek |
| **D**IP | Függőség Megfordítás | Absztrakciókra támaszkodás |

---

Készült ❤️-tel, FastAPI-val, SOLID elveket követve, AI ágensek integrációjára készen!
