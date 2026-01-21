3.házi külső api hívás

Távlati cél:
A kiválasztott megvalósítandó projektem a meeting-asszisztens.
Jelen házival egy külső API hívást kell prezentálnom, jelen kód erre a részre szorítkozik.
A kiválasztott api egy ingyenes "okos" api, ami adott string bemenetre egy életkort tippel.

A kód elkészítéséhez használt kezdeti prompt az initprompt.md file-ban található.
Használat: 
1) A terminalban a meeting_minuts_cli_hazi3-ban elhelyezett main.py program futtatásával indítható.
cd mini_projects\csilla.toth\meeting_minutes_cli_hazi3
python main.py
(ha első futtatás, telepíti a szükséges csomagokat, venv-et készít.)
2) írjunk be egy szöveget, melynek a végén az enter, ctrl+D ill Ctrl+Z segítségével zárjuk azt.
A program halmazba gyűjti az egyedi "neveket", az életkort 0-ra inicializálja, majd az api hívás segítségével egyeként a nevekhez kort rendel.
3) Az elemek kiírásra kerülnek 
 a program nem vár végtelen ciklusban.
