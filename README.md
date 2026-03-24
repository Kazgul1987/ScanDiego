# ScanDiego

ScanDiego ist ein portables Windows-Desktop-Tool (PySide6 + SQLite), das externe Laufwerke auf Spiele-Images und ROMs scannt:

- **`<Laufwerk>\Games`** → Kategorie `game`
- **`<Laufwerk>\ROMs`** → Kategorie `rom`

Die Zuordnung erfolgt nicht nur per Laufwerksbuchstabe, sondern zusätzlich über die **Volume Serial Number** (Drive-ID).

## Features (MVP)

- Erkennung externer Laufwerke (Laufwerksbuchstabe, Label, Dateisystem, Volume Serial)
- Rekursiver Scan in `Games` und `ROMs`
- Erkennung von Dateitypen: `.iso`, `.nsp`, `.xci`, `.bin`, `.cue`, `.img`
- Optionaler Modus: Meldet Ordner mit `.rar`/`.zip`, wenn **keine** ROM/Image-Datei (`.iso`, `.nsp`, `.xci`, `.bin`, `.cue`, `.img`) im selben Ordner liegt
- Ausgabe im Archiv-Modus erfolgt auf **Ordnerebene** (keine Einzelauflistung von `.rar`/`.zip`)
- UI bleibt responsiv durch Worker in eigenem `QThread`
- Scan abbrechbar
- SQLite-Datenbank lokal (`data/scandiego.db`)
- Upsert statt Duplikaten (`UNIQUE(drive_id, full_path)`)
- `last_seen_date`-Aktualisierung + Markierung fehlender Dateien (`is_missing`)
- Suche, Festplattenfilter, Detailansicht
- Kontextmenü/Komfort: Ordner öffnen, Pfad kopieren
- CSV-Export
- Logging in `logs/app.log`

---

## Projektstruktur

```text
ScanDiego/
├─ main.py
├─ build.bat
├─ requirements.txt
├─ README.md
└─ app/
   ├─ ui/
   │  └─ main_window.py
   ├─ services/
   │  ├─ drive_service.py
   │  └─ scanner_worker.py
   ├─ database/
   │  └─ db_manager.py
   ├─ models/
   │  ├─ drive.py
   │  └─ game_entry.py
   └─ utils/
      ├─ paths.py
      ├─ logging_setup.py
      ├─ formatting.py
      └─ date_utils.py
```

---

## Entwickler-Start

### 1) Voraussetzungen

- Windows 10/11
- Python 3.11+ (empfohlen)

### 2) Virtuelle Umgebung + Start

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## Portable Build (ohne Installer)

### Schnell über `build.bat`

```bat
build.bat
```

Ergebnis:

- Portabler Ordner in `dist\ScanDiego\`
- Start via `ScanDiego.exe`
- DB/Logs werden relativ zur EXE im Ordner `data/` und `logs/` geführt

### Manuell mit PyInstaller

```bat
pyinstaller --noconfirm --clean --windowed --name ScanDiego --add-data "data;data" --add-data "logs;logs" main.py
```

---

## Architektur (kurz)

- **UI-Schicht (`app/ui`)**
  - Fensteraufbau, Interaktionen, Tabellen, Filter, Export
- **Service-Schicht (`app/services`)**
  - Laufwerkserkennung (Windows API)
  - Scanlogik mit Rekursion und Abbruchsteuerung
- **Datenbank-Schicht (`app/database`)**
  - Schema, Upsert, Filterabfragen, Missing-Markierung
- **Modelle (`app/models`)**
  - Typisierte Datencontainer
- **Utils (`app/utils`)**
  - Pfade, Logging, Datum/Zeit, Titel-/Größenformatierung

Die UI bleibt stabil, weil der eigentliche Dateiscan in einem Worker-Thread läuft.

---

## Wichtige pragmatische Entscheidungen

1. **Externe Laufwerke**: Für MVP werden alle `DRIVE_FIXED` und `DRIVE_REMOVABLE` Laufwerke außer Systemlaufwerk als „extern relevant“ behandelt.
2. **Drive-Zuordnung**: Primär über `volume_serial` (Drive-ID), zusätzlich Anzeige von Laufwerksbuchstabe und Label.
3. **Scan-Root**: Es werden nur `Games` und `ROMs` gescannt (wie gefordert), nicht das gesamte Laufwerk.
4. **Titelermittlung**: Standardmäßig Dateiname ohne Endung, `_` → Leerzeichen, doppelte Leerzeichen reduziert.
5. **Fehlende Dateien**: Nach Scan eines Laufwerks werden ältere Einträge desselben `drive_id` als `is_missing=1` markiert.

---

## Hinweise

- Beim Trennen eines Laufwerks während des Scans werden Lesefehler geloggt; die Anwendung bleibt lauffähig.
- Für sehr große Datenträger kann ein erster Vollscan dauern; Fortschritt wird in der Statusleiste aktualisiert.
- Erweiterungen (z. B. Hashing, zusätzliche Dateiendungen, bessere Tag-Bereinigung) sind vorbereitet.
