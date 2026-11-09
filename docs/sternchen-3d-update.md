# Sternchen: technische Abnahme und vorbereitetes QNAP-Update

Stand: 9. November 2026. Branch `codex/finalize-multitenant`, Basis `82e9b7a`
plus den nachfolgenden Integrationscommit. Der Basis-Commit allein enthält
die fertige Integration noch nicht.

## Ergebnis der technischen Abnahme

- Die große Kinderkarte auf Heute und Aufgaben verwendet den vorhandenen
  gleichursprünglichen iframe-Viewer. Kompakte Elternkarten behalten das Symbol.
- Die zwölf ursprünglichen Levelschwellen bleiben unverändert. Level 1 lädt
  die Schalenform, Level 6 `Baby.glb`. Ein Levelwechsel ersetzt den Viewer sauber.
- Der gespeicherte Name bleibt sichtbar. Namensvergabe und XP-/Lob-Regeln sowie
  Datenbankschemata wurden nicht geändert.
- Laden, Spielen und der sichtbare Rückfall sind auf Deutsch und Englisch vorhanden.
- Manuelles Spielen und Tippen funktionieren. Reduzierte Bewegung zeigt eine
  statische Pose; Hintergrund und nicht sichtbare Karten pausieren die Animation.
- WebGL-Kontextverlust und blockierter GLB-Download entfernen den Viewer und
  zeigen das Drachensymbol mit Erklärung. Aufgaben bleiben nutzbar; erneutes
  Öffnen der Ansicht lädt den Viewer erneut.

Geprüft mit einer isolierten lokalen Testfamilie: Tim, gespeicherter Name
Sternchen, 320 Aufgaben-XP und ein Lob, Level 6. Der automatisierte Browsertest
läuft gegen den gebauten FastAPI-App-Server mit echter PostgreSQL-Datenbank.
Zusätzlich wurde das Runtime-Image als nicht privilegierter Benutzer gestartet:
alle zwölf GLB-Dateien sind lesbar; die englische mobile Kinderansicht zeigt
Baby und gespeicherten Namen auch bei bereits aktivierter reduzierter Bewegung.

Prüfungen:

- 366 Frontendtests in 55 Dateien mit `npx vitest run --maxWorkers=1` bestanden.
  Drei zeitabhängige Fehler im parallelen Lauf bestanden anschließend sowohl
  einzeln als auch im vollständigen Lauf mit einem Worker.
- Typprüfung, Lint und Produktionsbuild bestanden. Vorhandene Lintwarnungen und
  die Warnung zur Bundlegröße bleiben bestehen. Three.js-Fremdcode wird von
  React-Lintregeln ausgenommen; eigener Viewer und React-Code bleiben geprüft.
- Neun Backendtests für Drachenname, Levelregeln und statische Auslieferung bestanden.
- `npm run e2e -- dragon.spec.ts` auf einer frischen isolierten Testdatenbank:
  Wachstum, Spielen/Tippen, reduzierte Bewegung, Hintergrundzustand und beide
  Fehlerpfade bestanden. Andere E2E-Dateien nicht im selben Lauf starten: sie
  benötigen ebenfalls eine eigene frische Datenbank. Chromium/WebGL erforderlich.

Die Cloudprüfung nutzte System-Chromium mit Software-WebGL; die Kamera-/Posendaten
waren endlich und die gerenderte Babyform wurde im Bildschirmfoto geprüft.
Die Produktionsfamilie wurde nicht verwendet. Zentrale Anmeldung, OAuth, Gateway
und MCP wurden durch diese Integration nicht verändert oder neu produktiv abgenommen.
Automatische Reaktionen auf Lob und Levelaufstieg sind weiterhin nicht angebunden.

## Vorbereiteter Kandidat (keine produktive Umstellung)

Lokales Runtime-Image, Architektur amd64:

```
famquest:sternchen-review-20261109
sha256:7f946f7de8623e3e2dd71272928592ccb96ef5f659a4924917a3e3b22362c78a
```

Der Cloud-Build verwendete eine temporäre Dockerfile-Kopie mit BuildKit-Secret
für die öffentliche Proxy-CA bei npm/uv. TLS- und Integritätsprüfung blieben aktiv;
die CA wurde nicht ins Image kopiert. Die funktionalen Schritte entsprechen dem
Repository-Dockerfile mit Target `runtime`. Die zusätzlichen Leserechte für
`/app/static` sind im Repository-Dockerfile enthalten und im Image geprüft.

Das Image wird nur lokal vorbereitet, nicht in eine Registry veröffentlicht.
Das Exportarchiv und seine SHA-256-Prüfsumme liegen außerhalb des Repositories
unter `/workspace/.famquest/famquest-sternchen-review-20261109.tar.gz` und
`/workspace/.famquest/famquest-sternchen-review-20261109.tar.gz.sha256`.
Die Image-ID ist eine lokale Inhalts-ID, kein Registry-Manifest-Digest.

## Übergabe für die spätere Umstellung durch den Betreiber

1. Den Integrationscommit dieses Dokuments prüfen und als Quellstand verwenden.
   Den Kandidaten nicht mit dem ungeänderten Basis-Commit verwechseln.
2. Das aktuelle private Betriebsartefakt von `famquest-live` als Ausgangspunkt
   verwenden. Der historische Einzel-Familien-Installer und die alte
   `docs/qnap-deployment.md` beschreiben nicht den aktuellen Livebetrieb.
3. Vor einer Umstellung die bestehende vollständige Sicherung ausführen und
   den derzeit fixierten Produktionsdigest (Präfix `d4073b03`) sowie die private
   App-/Gateway-/MCP-Konfiguration für den Rückweg sichern.
4. Kandidaten zunächst auf einer isolierten Kopie mit der bestehenden zentralen
   Startkonfiguration prüfen. Den Live-Entrypoint/Startbefehl, dedizierte zentrale
   und Familien-DB-Rollen, Upload-Mounts, Gateway-Vertrauen und OAuth-/MCP-Routen
   erhalten. Das Image hat weiterhin den Legacy-Standardentrypoint; ihn nicht
   versehentlich anstelle des bestehenden zentralen Starts verwenden.
5. Vor dem späteren produktiven Wechsel zentrale Anmeldung, Familienzuordnung,
   API-Health, Sternchen auf Level 6, Spielen, Rückfall und MCP über das Gateway
   prüfen. Diese neue isolierte zentrale Restore-/Betriebsprobe ist hier nicht
   als erledigt behauptet.

Es wurden keine QNAP-Container, produktiven Datenbanken, Connectoren, Zeitpläne
oder Tunnel geändert. Es gibt für diese 3D-Integration keine neue DB-Migration.
Der Betreiber führt den produktiven Wechsel selbst aus.
