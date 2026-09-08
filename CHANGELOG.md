# Changelog

## 0.10.1 – 2026-09-08

- Added manual SteamGridDB cover selection for ambiguous artwork matches.
- Added visible cover queue progress.
- Added pause/resume/cancel controls for cover downloads.
- Fixed forced cover refresh so cached artwork is actually refreshed.
- Existing cover remains intact when refresh fails.
- Old cached cover files are cleaned up only after successful replacement.
- Improved SteamGridDB ambiguous-match logging.
- Separated Cover laden and Cover aktualisieren actions.

## 0.10.0 – 2026-09-08

- Added large responsive game-card library view.
- Increased cover artwork size and improved placeholders.
- Added game-centric sorting, filtering and search.
- Added bulk download for all missing game covers.
- Added cover queue duplicate protection.
- Improved SteamGridDB artwork matching diagnostics.
- Added conservative detection of ambiguous artwork matches.
- Cover rendering now uses only local cached artwork and does not block the UI.

## 0.9.3 – 2026-09-07

- Provider credentials now persist across application updates.
- IGDB Client ID is stored in the OS credential store as well.
- Legacy provider credentials are migrated out of `settings.json`.
- Manual removal of DLC/update parent assignments is now durable.
- Removed content assignments are protected from immediate automatic reassociation.

## 0.9.2 – 2026-09-07

- Bulk-Metadatenabruf wiederholt zuvor fehlgeschlagene Lookups und prüft vorher die IGDB-Konfiguration.
- IGDB-Multiplattformspiele behalten alle unterstützten Plattformen als einen Kandidaten.
- Explizite Plattformauswahl beim manuellen Match und sichere Auflösung unbekannter Plattformen ergänzt.
- Bekannte lokale Plattformen werden vor unbeabsichtigtem Überschreiben geschützt.
- Konservative PC-Erkennung anhand vollständiger Verzeichnissegmente erweitert.
- Manuelle, scanbeständige Plattformkorrektur und verbessertes Feedback für leere Queues ergänzt.

## 0.9.1 – 2026-09-07

- Self-Parents für DLCs, Add-ons und Updates verhindert und bestehende ungültige Beziehungen beim Start repariert.
- Deterministische, reihenfolgeunabhängige Parent-Zuordnung zentral über den `ContentAssociationService`; Titelkandidaten benötigen eine Base-Datei.
- Manuelle Hauptspiel-Zuordnung und Lösen der Zuordnung aus problematischen Cleanup-Ansichten ergänzt.
- Switch Title IDs werden auch als isolierte 16-stellige Hex-Tokens ohne eckige Klammern erkannt.

## 0.9.0 – 2026-09-07

- Additives Schema v6 mit zentralen Content-Typen, technischen IDs, Parent-Relation, Confidence und manuellem Lock.
- Konservative Erkennung für Base Games, Updates, DLC/Add-ons und Demos samt Version und Basistitel.
- Austauschbarer, auf 64 KiB begrenzter Switch-Parser ohne Schlüssel- oder DRM-Funktionen sowie Title-ID-Fallback.
- Plattformbewusste Parent-Zuordnung, sichere Legacy-Konsolidierung und nachgelagerte Content-Analyse-Queue.
- Content-bewusste Dubletten-/Metadata-Logik, neue Cleanup-Kategorien sowie gruppierte Game-Details und Badges.

## 0.8.0 – 2026-09-07

- Dauerhafter Manual-Match-Schutz (`metadata_locked`) und Status `no_match`.
- Separater Cover-Workflow mit gespeichertem SteamGridDB-Match und sicherem Scoring.
- Match-Prüfung, Match-Änderung und freie manuelle Suche im Worker-Thread.
- Secrets im OS Credential Manager einschließlich sicherer Klartextmigration.
- Provider-Factory, vereinheitlichte Health-Ergebnisse und zentrale `incomplete`-Regel.
- Vollständige IGDB-Veröffentlichungsdaten und Schema-v5-Migration.

## 0.7.0 – 2026-09-07

- Austauschbare IGDB-/SteamGridDB-Provider, zentraler HTTP-Client und sichere Laufzeitkonfiguration ohne eingebettete Schlüssel.
- Persistente, sequenzielle Metadata-Queue mit QThread-Integration, manueller Schutzlogik und direktem Refresh über externe IDs.
- Plattformbewusstes Fuzzy-Matching, gespeicherte Kandidaten und konfigurierbare 90/75-Schwellenwerte.
- Atomarer lokaler JPEG/PNG/WebP-Cover-Cache, echte Coveransicht sowie präzisierte Cleanup-Kategorien.
- Additive Schema-v4-Migration und vollständig offline arbeitende Fake-Provider-Tests.

## 0.6.0 – 2026-09-07

- Vollständiger, read-only Cleanup-Drill-down für alle acht Kategorien.
- Zentrale Dublettengruppen mit möglicher, wahrscheinlicher und hashbestätigter Klassifikation; Hashvergleiche berücksichtigen das Verfahren.
- Sicherer Scan-Lebenszyklus für Archive-only-Hinweise und unbekannte Medienkandidaten.
- Zentrale Ausschlussliste für Begleitdateien und expliziter Metadatenstatus.
- Additive Schema-v3-Migration und direkt lauffähige Pytest-Konfiguration.

## 0.5.0 – 2026-09-04

- Sicher protokollierte Scan-Läufe mit Status und fehlertolerantem Missing-Handling.
- Schrittweise, verlustfreie Migration auf Game, MediaFile und Drive.
- Zentrale Plattform- und Formaterkennung sowie verbesserte Titelbereinigung.
- Nicht-invasive Dublettenerkennung und optionaler SHA-256-Worker.
- Bibliotheks-, Cover- und Aufräumen-Bereiche sowie detaillierter Scanfortschritt.
- Batch-Upserts, speicherschonendes Verzeichnis-Scanning und automatisierte Tests.
