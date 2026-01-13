SUMMARY_PROMPT_HU = """\
Feladatod egy meeting leirat rövid, tényszerű összefoglalása.
Adj vissza egy tömör, 2-4 mondatos összefoglalót, magyarul.
Kerüld a találgatást, csak a leiratból dolgozz.
"""


DECISIONS_PROMPT_HU = """\
Feladatod döntések kinyerése a meeting leiratból.
Adj vissza egy JSON listát (csak listát) a döntések szövegével.
Példa:
[
  "A következő sprint csak hibajavításról szól.",
  "A sprint zárása január 7."
]
"""


ACTION_ITEMS_PROMPT_HU = """\
Feladatod akciópontok kinyerése a meeting leiratból.
Adj vissza egy JSON listát (csak listát) az akciópontokról.
Minden elem struktúrája:
{
  "task": "...",
  "owner": "Név vagy null",
  "due_date": "YYYY-MM-DD vagy null",
  "priority": "low|medium|high"
}
"""
