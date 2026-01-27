# SPEC — KnowledgeRouter

## Cél
Belső tudásirányító agent, ami:
- több domain (IT, Legal, HR) tudásbázisából RAG-gal válaszol,
- később workflow akciókat indít (ticket, email draft, file output),
- guardrail-lel és audit loggal.

## Use-case-ek (MVP)
1) IT: VPN / hozzáférés / szoftver gond → policy-alapú válasz + (később) ticket feladás
2) Legal: jogosultság / levelezőlista / compliance → policy-alapú válasz + (később) email draft
3) HR: onboarding/offboarding/szabi → policy-alapú válasz + (később) JSON output + (HF miatt) publikus API check

## NFR
- Docker-first futtatás
- Determinisztikus DEV mód (mock + fix seed)
- Strukturált logging (tool input/output, latency, hibák)
- Teszt: hálózat nélkül (mock)
- Biztonság: később tool whitelist + input validation + outbound allowlist

## Korlátok (Patch #1)
- csak .md/.txt ingest
- nincs routing / orchestration még
