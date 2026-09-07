# ScanDiego 0.9.0

ScanDiego ist ein lokaler Game-Collection-Manager für Windows (Python, PySide6 und SQLite). Die Anwendung erkennt externe Datenträger anhand ihrer **Volume Serial Number**, scannt deren Verzeichnisse `Games` und `ROMs` im Hintergrund und bewahrt den ursprünglichen Dateinamen neben einem lesbaren Titel auf.

## Funktionen

- Bestehende Tabellenansicht mit Suche, Laufwerks-/Plattformfilter, Details und CSV-Export.
- Bibliotheks-Tabs für Tabelle und echte lokal gecachte Cover (mit robustem Platzhalter-Fallback).
- **Aufräumen** zeigt anklickbare Detailansichten für Archive, mögliche, wahrscheinliche und bestätigte Dublettengruppen, fehlende Dateien, unbekannte Plattformen/Formate und Spiele mit relevantem Metadatenfehler. Die Zahlen bezeichnen bei Dubletten Gruppen, nicht einzelne Dateien. Es werden keine Dateien automatisch gelöscht oder verschoben.
- Abbrechbarer `QThread`-Scan mit aktuellem Ordner, geprüften Dateien, Treffern, Warnungen, Laufzeit und Status.
- Scan-Läufe haben `running`, `completed`, `cancelled`, `failed` oder `completed_with_warnings`. Nur ein vollständig fehlerfreier `completed`-Scan darf ältere Dateien als fehlend markieren. Schon ein nicht lesbarer Unterordner erzeugt Warnstatus und unterdrückt die Missing-Erkennung für das Laufwerk.
- Batch-Upserts (250 Einträge pro Transaktion) und iteratorbasiertes Traversieren großer Ordner.
- Optionale SHA-256-Infrastruktur als Worker-Thread; Hashing erfolgt niemals automatisch. Identische gespeicherte SHA-256-Werte gelten als bestätigte Dublette.

## Aufräumanalyse

Die zentrale Dublettenerkennung klassifiziert gleichen normalisierten Titel und gleiche Plattform bei unterschiedlichen Größen als **möglich**, bei gleicher Größe als **wahrscheinlich**. Eine Übereinstimmung wird nur dann **bestätigt**, wenn sowohl Hashwert als auch Hashverfahren identisch sind. Die Detailansicht nummeriert Gruppen und zeigt alle zugehörigen Dateien.

Archive-only-Hinweise und unbekannte Medienkandidaten besitzen einen Scan-Lebenszyklus. Veraltete Ergebnisse werden ausschließlich nach einem vollständig erfolgreichen Scan des Laufwerks deaktiviert; Abbruch, Fehler oder Warnungen bewahren den letzten sicheren Stand. Unbekannte Formate werden nur innerhalb der expliziten Wurzelordner `Games` und `ROMs` erfasst. Unterstützte Spiele- und Archivformate sowie zentrale Begleitdateien (unter anderem Bilder, `.txt`, `.nfo`, `.xml`, Prüfsummen und Dokumentation) sind ausgeschlossen.

Das Aufräumen unterscheidet nun „Metadaten fehlgeschlagen“, „Match prüfen“, „Spiele ohne Cover“ und „Unvollständige Metadaten“. `not_requested` ist weiterhin kein Fehler.

## Plattformen und Formate

Die zentrale Plattformdefinition umfasst PC, PlayStation 1–5, PSP, PS Vita, Xbox/360/One/Series, NES, SNES, Nintendo 64, GameCube, Wii/Wii U, Switch, Game Boy/Color/Advance, DS/3DS, Sega Mega Drive/Genesis, Saturn, Dreamcast und Unknown. Die Erkennung priorisiert Ordner-Aliase (`PS2`, `PlayStation2`, `Super Famicom` usw.) und verwendet danach eindeutige Endungen.

Unterstützt werden `.iso`, `.nsp`, `.xci`, `.bin`, `.cue`, `.img`, `.chd`, `.cso`, `.rvz`, `.wbfs`, `.wia`, `.gcz`, `.nsz`, `.xcz`, `.3ds`, `.cia`, `.gba`, `.gbc`, `.gb`, `.nds`, `.n64`, `.z64`, `.v64`, `.sfc`, `.smc`, `.gen` und `.md`. Archivhinweise erkennen `.rar`, `.zip` und `.7z`.

## Datenbank und Migration

Die portable Datenbank liegt bei einem Quellstart in `data/scandiego.db`, beim gebauten Programm relativ zur EXE. Alte `media_entries` bleiben erhalten und werden beim ersten Start transaktional um additive Spalten ergänzt. Bestehende Zeilen werden in die normalisierten Tabellen `games`, `media_files` und `drives` übernommen; `scan_runs` protokolliert Scanstatus und Statistiken. Schema 6 ergänzt `MediaFile` verlustfrei um Content-Typ, Titel, Version, technische IDs, Parent, Region, Erkennungsaudit und manuellen Lock. Bestehende Dateien starten sicher als `unknown`. Die bisherige Tabelle bleibt als kompatible Projektion für UI, Filter und Export bestehen.

## Content-Modell (0.9)

Ein `Game` kann beliebig viele Hauptspiel-Dateien, Updates und DLCs/Add-ons besitzen. Die zentralen
Typen sind `base_game`, `update`, `dlc`, `addon`, `demo` und `unknown`; die Dateinamenerkennung
behandelt DLC als Oberbegriff, während `addon` für künftige Parser und manuelle Zuordnungen erhalten
bleibt. Explizite, wortbegrenzte Marker erkennen Updates, Versionen, DLC-/Expansion-Pakete und Demos.
Eine getrennte Basistitel-Logik entfernt nur erkannte Content-Suffixe und verändert weder Dateien noch
die allgemeine Titel-Normalisierung. Titel und Plattform müssen eindeutig übereinstimmen; eine exakte
technische Base-ID hat Vorrang. Unsichere oder elternlose Funde bleiben unzugeordnet und erscheinen im
Aufräumen. Manuelle Zuordnungen werden dauerhaft gesperrt.

Der austauschbare Switch-Parser unterstützt `.nsp`, `.xci`, `.nsz` und `.xcz`, liest höchstens 64 KiB
und verarbeitet ausschließlich offen vorliegende Metadaten. Zusätzlich werden eindeutige 16-stellige
Title IDs in Dateinamen verwendet. Die zentral getestete Beziehung wertet Offset `000` als Base,
`800` als Update und den folgenden `0x1000`-Block mit nicht-null Content-Index als DLC. Normale verschlüsselte NCA-Metadaten
werden **nicht** entschlüsselt: es gibt keine eingebetteten Keys, Key-Downloads, Key-Erzeugung oder
DRM-Umgehung. ScanDiego konfiguriert derzeit bewusst auch kein Keyfile; ohne Keys funktionieren
Dateinamen-Fallback, Zuordnung, Bibliothek, Queues und Cleanup vollständig. Ein nicht lesbarer
Container erzeugt nur eine Warnung und stoppt weder Scan noch Analyse.

Die Cover-Bibliothek bleibt auf Game-Ebene und zeigt kleine Update-/DLC-Zähler. Details gruppieren
Hauptspiele, Updates, DLC/Add-ons und sonstigen Content. Die Metadaten-Queue ignoriert reine,
zugeordnete Zusatz-Game-Datensätze. Alte eindeutige DLC-/Update-Games werden nur dann entfernt, wenn
ihre Datei sicher umgehängt wurde, der Datensatz leer und ungelockt ist und keine relevanten
Metadaten/Cover trägt. Cleanup ist stets read-only und ergänzt elternlose DLCs/Updates, unbekannte
Typen, mehrere Base-Dateien, unsichere Zuordnungen und manuelle Prüfung.

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
pytest -q
python -m pytest -q
```

Ein portabler Build wird mit `build.bat` erzeugt. Logs rotieren unter `logs/app.log`; protokolliert werden App-Start, Migrationen, Scans, Lesefehler, Datenbankfehler, Hashing und Dublettenanalyse.

## Metadaten und Cover

Die austauschbare Provider-Schicht nutzt zunächst **IGDB** für Spieldaten und **SteamGridDB** für vertikale Cover. IGDB benötigt eine Twitch/IGDB Client-ID und ein Client-Secret, SteamGridDB einen API-Key. Diese können unter **Metadaten & Cover** oder bevorzugt über `SCANDIEGO_IGDB_CLIENT_ID`, `SCANDIEGO_IGDB_CLIENT_SECRET` und `SCANDIEGO_STEAMGRIDDB_API_KEY` gesetzt werden. Die lokale `data/settings.json` und der Cover-Ordner sind von Git ausgeschlossen; Passwortfelder sind maskiert. Secrets werden nie protokolliert.

Nach einem Scan kann die automatische, strikt nachgelagerte Metadaten-Queue gestartet werden. Sie läuft sequenziell in einem eigenen `QThread`, ist abbrechbar/pausierbar, setzt persistente Zustände (`not_requested`, `queued`, `searching`, `matched`, `ambiguous`, `incomplete`, `failed`, `manual`) und nimmt nach einem Neustart unterbrochene Arbeit wieder auf. Ein Fehler stoppt andere Spiele nicht. Bereits verknüpfte Provider-IDs werden direkt abgerufen; manuelle Matches werden von normalen Läufen geschützt.

Der Matcher normalisiert Unicode und Interpunktion. Der Titel trägt 75 Punkte, ein exakter Plattformtreffer 25 Punkte; ein bekannter Plattformkonflikt deckelt das Ergebnis auf 55. Das Veröffentlichungsjahr kann bis zu 5 Zusatzpunkte liefern. Ab 90 wird automatisch übernommen, 75–89 bzw. nahe konkurrierende Treffer werden als `ambiguous` zur Prüfung gespeichert, darunter gilt die Suche als fehlgeschlagen. Schwellenwerte sind in den Einstellungen konfigurierbar. Über das Kontextmenü lässt sich suchen, aktualisieren oder zurücksetzen; gespeicherte Kandidaten bilden die Grundlage für die manuelle Prüfung.

Cover werden validiert (JPEG, PNG oder WebP), zunächst temporär geschrieben und atomar unter `data/covers/<provider>_<external-id>_<game-id>.<ext>` ersetzt. Vorhandene Dateien werden nicht erneut geladen. Coverfehler verändern einen erfolgreichen Metadatenmatch nicht. Ohne Netzwerk oder Credentials bleiben Scan, Cleanup, Tabelle, bestehende Cover und die gesamte lokale Bibliothek verfügbar; lediglich Queue-Einträge erhalten einen verständlichen Fehlerstatus. HTTP-Anfragen haben Timeouts, begrenzte Retries und Frequenz, beachten `Retry-After` bei 429 und erzeugen keine parallele Anfrageflut.

## Sichere Matches und Provider (0.8)

Manuell bestätigte Matches erhalten einen dauerhaften `metadata_locked`-Schutz. Automatische
Läufe überspringen sie; ein ausdrückliches Aktualisieren verwendet die bereits bekannte externe
ID und führt keinen Fuzzy-Rematch aus. **Match prüfen** und **Match ändern** zeigen gespeicherte
Kandidaten und erlauben eine nicht blockierende Suche mit eigenem Suchtext. „Kein passender
Treffer“ setzt `no_match`, sodass automatische Läufe die Entscheidung respektieren.

Cover laufen in einer separaten Cover-Queue. SteamGridDB-Treffer werden bewertet, unsichere
Treffer nicht übernommen und die bestätigte Artwork-ID für spätere Aktualisierungen gespeichert.
Cover gehören nicht zur Metadaten-Vollständigkeit: `incomplete` bedeutet, dass trotz Match weniger
als drei der Angaben Titel, Veröffentlichungsdatum/-jahr, Publisher und Developer vorhanden sind.

IGDB-Secret und SteamGridDB-Key werden über `keyring` im Credential Manager gespeichert;
Umgebungsvariablen haben Vorrang. Alte Klartextwerte werden nur nach erfolgreicher Übernahme
entfernt. Ohne verfügbares Keyring-Backend bleibt die App offline nutzbar und speichert kein Secret
im Klartext. Die Provider-Auswahl im Einstellungsdialog wird von den Workern über eine Factory
verwendet. Metadata- und Cover-Queues sind getrennt sichtbar und können durch ihre Worker
abgebrochen werden; MetadataQueueService unterstützt außerdem Pause und Fortsetzen.

### Datenschutz

Bei einer Suche werden ausschließlich normalisierter **Spieltitel** und **Plattform** benötigt. Lokale Pfade, Dateinamen, Laufwerksbuchstaben, Volume-Seriennummern und andere Bibliotheksdaten werden nicht an Provider übertragen.
