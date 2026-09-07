# Changelog

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
