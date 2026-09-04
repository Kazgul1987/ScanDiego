# ScanDiego 0.5.0

ScanDiego ist ein lokaler Game-Collection-Manager für Windows (Python, PySide6 und SQLite). Die Anwendung erkennt externe Datenträger anhand ihrer **Volume Serial Number**, scannt deren Verzeichnisse `Games` und `ROMs` im Hintergrund und bewahrt den ursprünglichen Dateinamen neben einem lesbaren Titel auf.

## Funktionen

- Bestehende Tabellenansicht mit Suche, Laufwerks-/Plattformfilter, Details und CSV-Export.
- Bibliotheks-Tabs für Tabelle und vorbereitete Coveransicht mit Platzhaltern.
- **Aufräumen** zeigt Archive, mögliche/bestätigte Dubletten, fehlende Dateien, unbekannte Plattformen/Formate und Spiele ohne Metadaten. Es werden keine Dateien automatisch gelöscht oder verschoben.
- Abbrechbarer `QThread`-Scan mit aktuellem Ordner, geprüften Dateien, Treffern, Warnungen, Laufzeit und Status.
- Scan-Läufe haben `running`, `completed`, `cancelled`, `failed` oder `completed_with_warnings`. Nur ein vollständig fehlerfreier `completed`-Scan darf ältere Dateien als fehlend markieren. Schon ein nicht lesbarer Unterordner erzeugt Warnstatus und unterdrückt die Missing-Erkennung für das Laufwerk.
- Batch-Upserts (250 Einträge pro Transaktion) und iteratorbasiertes Traversieren großer Ordner.
- Optionale SHA-256-Infrastruktur als Worker-Thread; Hashing erfolgt niemals automatisch. Identische gespeicherte SHA-256-Werte gelten als bestätigte Dublette.

## Plattformen und Formate

Die zentrale Plattformdefinition umfasst PC, PlayStation 1–5, PSP, PS Vita, Xbox/360/One/Series, NES, SNES, Nintendo 64, GameCube, Wii/Wii U, Switch, Game Boy/Color/Advance, DS/3DS, Sega Mega Drive/Genesis, Saturn, Dreamcast und Unknown. Die Erkennung priorisiert Ordner-Aliase (`PS2`, `PlayStation2`, `Super Famicom` usw.) und verwendet danach eindeutige Endungen.

Unterstützt werden `.iso`, `.nsp`, `.xci`, `.bin`, `.cue`, `.img`, `.chd`, `.cso`, `.rvz`, `.wbfs`, `.wia`, `.gcz`, `.nsz`, `.xcz`, `.3ds`, `.cia`, `.gba`, `.gbc`, `.gb`, `.nds`, `.n64`, `.z64`, `.v64`, `.sfc`, `.smc`, `.gen` und `.md`. Archivhinweise erkennen `.rar`, `.zip` und `.7z`.

## Datenbank und Migration

Die portable Datenbank liegt bei einem Quellstart in `data/scandiego.db`, beim gebauten Programm relativ zur EXE. Alte `media_entries` bleiben erhalten und werden beim ersten Start transaktional um additive Spalten ergänzt. Bestehende Zeilen werden in die normalisierten Tabellen `games`, `media_files` und `drives` übernommen; `scan_runs` protokolliert Scanstatus und Statistiken. Die bisherige Tabelle bleibt als kompatible Projektion für UI, Filter und Export bestehen.

## Installation und Start

Voraussetzungen: Windows 10/11 und Python 3.11 oder neuer.

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Testabhängigkeiten und Tests:

```bat
pip install -r requirements-dev.txt
python -m pytest
```

Ein portabler Build wird mit `build.bat` erzeugt. Logs rotieren unter `logs/app.log`; protokolliert werden App-Start, Migrationen, Scans, Lesefehler, Datenbankfehler, Hashing und Dublettenanalyse.

## Metadaten

`games` enthält bereits Felder für Jahr, Publisher, Entwickler, Region, Edition, Cover und `metadata_source`. Externe Provider wie IGDB oder SteamGridDB sind bewusst noch nicht angebunden; die Felder und Coveransicht bilden die Erweiterungsstelle.
