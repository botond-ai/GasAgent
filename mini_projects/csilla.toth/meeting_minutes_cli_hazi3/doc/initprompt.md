készíts példakódot SOLID elvek szerint, python nyelven, VS Code környezetbe egy komplett alkalmazásként. egy meeting-minutes cli alkalmazás a bemeneti szövegből-ból extraktálja a résztvevők nevét, és az Agify API használatával becsülje meg életkorukat. Egy halmazban kerüljenek tárolásra a nevek és korok, ahol a korok kezdeti értéke legyen 0, ne tartalmazzon duplikátumot a névlista, ezért kell a set. Az API-n keresztül minden nevet küldjön el az Agify életkorbecslőnek. A visszakapott becsült kort tárolja le a név mellé. A végén írja ki a részvevők nevét és becsült életkorát.

kiegészítés:
ugyanezt a projetet egészítsd ki openaiapi hívással, az vegye át a name_extractor.py funkcióját, egy .env fileban fogom megadni hozzá az api kulcsomat.
