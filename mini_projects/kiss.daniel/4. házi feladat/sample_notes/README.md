# Meeting Notes Test Samples

Ez a könyvtár 3 realisztikus meeting jegyzetet tartalmaz a LangGraph agent teszteléséhez.

## 📁 Sample Files

### 1. `tech_design_meeting.txt` - Tech Design Review
**Jellemzők:**
- ✅ Egyértelmű következő meeting részletek
- ✅ Részletes döntések és action itemek
- ✅ Teljes attendee lista email címekkel
- ✅ Konkrét dátum, idő, helyszín, video link

**Várt eredmény:**
- Confidence: ~100%
- Calendar event: Létrehozható
- Összefoglaló: Database migration decision
- Következő meeting: 2026-01-27 14:00

**Használat:**
```bash
python -m app.main --notes-file sample_notes/tech_design_meeting.txt --dry-run
```

---

### 2. `customer_call.txt` - Customer Call Notes
**Jellemzők:**
- ⚠️ Több lehetséges időpont említve (Option 1, 2, 3)
- ⚠️ "Tentative" meeting időpont
- ✅ Jó business context
- ✅ Részletes action itemek

**Várt eredmény:**
- Confidence: ~85-95%
- Calendar event: Létrehozható a "tentative" időponttal
- Figyelmeztetés: Confirmation szükséges
- Következő meeting: 2026-01-31 14:00 (Option 2)

**Használat:**
```bash
python -m app.main --notes-file sample_notes/customer_call.txt --dry-run
```

---

### 3. `team_retrospective.txt` - Sprint Retrospective
**Jellemzők:**
- ❌ Nincs konkrét következő meeting időpont
- ❌ Csak hozzávetőleges említés ("approximately February 11th")
- ✅ Sok decision és action item
- ✅ Részletes team feedback

**Várt eredmény:**
- Confidence: ~30%
- Calendar event: NEM hozható létre (hiányzó dátum/idő)
- Missing info: Start date and time, End date and time
- Összefoglaló: Retrospective eredmények

**Használat:**
```bash
python -m app.main --notes-file sample_notes/team_retrospective.txt --dry-run
```

---

## 🧪 Integration Tests

Az `tests/test_integration_samples.py` fájl tartalmazza a három jegyzet integrációs tesztjeit:

**Futtassa a teszteket:**
```bash
pytest tests/test_integration_samples.py -v -s
```

**Teszt eredmények:**
- ✅ `test_tech_design_meeting_clear_next_meeting` - 100% confidence
- ✅ `test_customer_call_ambiguous_time` - 95% confidence, warnings
- ✅ `test_retrospective_no_next_meeting` - Incomplete event
- ✅ `test_all_notes_generate_summaries` - Mind a 3 összehasonlítása
- ✅ Edge case tesztek (empty, short, multiple meetings)

---

## 📊 Teszt Eredmények Összefoglalása

| Meeting Type | Confidence | Event Created | Decisions | Actions | Warnings |
|--------------|-----------|---------------|-----------|---------|----------|
| Tech Design | 100% | ✅ Yes | 3 | 5 | None |
| Customer Call | 95% | ✅ Yes | 3 | 5 | Confirmation needed |
| Retrospective | 30% | ❌ No | 4 | 4 | Missing date/time |

---

## 🎯 Testing Scenarios Covered

### Pozitív esetek:
1. ✅ Teljes event információ (dátum, idő, résztvevők, helyszín)
2. ✅ Action itemek owner és deadline mezőkkel
3. ✅ Döntések kinyerése
4. ✅ Rizikók és nyitott kérdések

### Bizonytalan esetek:
1. ⚠️ Több lehetséges időpont (agent választ egyet és flag-eli)
2. ⚠️ "Tentative" vagy "to be confirmed" meeting
3. ⚠️ Timezone konverziók (PST → Budapest)

### Negatív/hiányos esetek:
1. ❌ Nincs konkrét dátum/idő (csak "next month")
2. ❌ Hiányos attendee lista
3. ❌ Túl rövid vagy üres jegyzetek

---

## 🔍 Agent Viselkedés Verifikációja

Az agent helyesen:
- **Összefoglal** mind a 3 meeting típusnál
- **Kinyeri** a döntéseket és action itemeket
- **Felismeri** a következő meeting részleteit
- **Kezeli** a bizonytalan vagy hiányos adatokat
- **Nem hoz létre** calendar eventet ha nem teljes az adat
- **Visszajelzést ad** a hiányzó információkról

---

## 💡 További Tesztelési Ötletek

```bash
# JSON kimenet
python -m app.main --notes-file sample_notes/tech_design_meeting.txt --json --dry-run

# Verbose logging
python -m app.main --notes-file sample_notes/customer_call.txt --dry-run -v

# Különböző timezone
python -m app.main --notes-file sample_notes/tech_design_meeting.txt --timezone "America/New_York" --dry-run
```
