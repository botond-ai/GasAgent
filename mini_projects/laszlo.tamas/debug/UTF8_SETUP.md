# UTF-8 Karakterkódolás Beállítása

## 🎯 Probléma
Magyar és egyéb UTF-8 karakterek (éáőúű, emojik) nem jelennek meg helyesen a Windows PowerShell terminálban.

## ✅ Alkalmazott Megoldások

### 1. PowerShell Szkriptek (✅ Implementálva)

Minden `.ps1` fájl elején:
```powershell
# UTF-8 encoding for console
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
chcp 65001 > $null
```

**Érintett fájlok:**
- `start.ps1`
- `reset.ps1`
- `chunk_document.ps1`

### 2. Python Backend (✅ Implementálva)

`backend/main.py` logging konfigurációja:
```python
import sys

# Force UTF-8 for stdout/stderr (Windows compatibility)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
```

### 3. FastAPI JSON Response (✅ Már volt)

`main.py` használja az `ORJSONResponse`-t, amely automatikusan UTF-8-ban kódol:
```python
app = FastAPI(
    title="AI Chat API",
    default_response_class=ORJSONResponse
)
```

## 🔧 További Lehetőségek (Opcionális)

### Windows Terminal Profil (Tartós megoldás)

`%LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json`:

```json
{
  "profiles": {
    "defaults": {
      "font": {
        "face": "Cascadia Code"
      },
      "commandline": "powershell.exe -NoExit -Command \"[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; chcp 65001 > $null\""
    }
  }
}
```

### VS Code Terminal Settings

`settings.json`:
```json
{
  "terminal.integrated.shellArgs.windows": [
    "-NoExit",
    "-Command",
    "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; chcp 65001 > $null"
  ]
}
```

## 🧪 Tesztelés

```powershell
# UTF-8 teszt
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 > $null

Write-Host "✅ Magyar karakterek: áéíóöőúüű ÁÉÍÓÖŐÚÜŰ" -ForegroundColor Green
Write-Host "🚀 Emoji teszt: ✅ 🔧 📦 🎯" -ForegroundColor Cyan
```

## 📝 Megjegyzések

- **PowerShell ISE**: Nem támogatja a `chcp` parancsot, használj Windows Terminal-t vagy VS Code-ot
- **Git Bash**: Alapból UTF-8, nincs szükség extra konfigurációra
- **Docker logs**: A backend most már UTF-8-ban logolja a magyar karaktereket
- **JSON responses**: Az API válaszok helyesek, csak a PowerShell `Invoke-RestMethod` kimenete lehet problémás

## 🎓 Oktatási Cél

Ez a konfiguráció biztosítja, hogy a diákok Windows rendszeren is helyesen lássák a magyar nyelvű prompt-okat, log üzeneteket és válaszokat.
