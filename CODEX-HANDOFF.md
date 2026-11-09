# FamQuest – Übergabe an Codex Cloud

## Als Nächstes

Repository **ManClone/FamQuest**, Branch **codex/finalize-multitenant**. Aktueller Auftrag: den bereits erstellten animierten 3D-Drachen Sternchen in Tims Kinderansicht fertig integrieren und in einer Testumgebung prüfen.

- `6d67ad7` enthält den ursprünglichen Viewer, die zwölf GLB-Modelle und den begonnenen React-Adapter `frontend/src/components/DragonModel.tsx`. Der Adapter ist noch nicht in die Drachenkarte eingebunden und wurde noch nicht im Browser getestet.
- `d0470d4` enthält die Korrekturen für OAuth-Zustimmungsweiterleitungen und MCP-Antwortkompression. Das laufende QNAP-Deployment verwendet für beide Fehler bereits Korrekturen in Gateway und Startkonfiguration.
- `frontend/src/components/DragonCompanion.tsx` ist die aktuelle Karte. `ChildTasksPage.tsx` rendert sie auf „Heute“ und unter „Aufgaben“. Die kompakte Elternansicht nutzt dieselbe Komponente. Bestehende Namensvergabe und den gespeicherten Namen über die Fortschritts-API beibehalten.
- Live wurde Tims Karte „Drachenbegleiter von Tim“ mit dem Namen **Sternchen** beobachtet. Das produktive Image zeigt aktuell ein Drachensymbol. Tims beobachtetes Level war 6. Die Originalschwellen für die zwölf Formen sind 1, 6, 20, 29, 36, 42, 48, 53, 58, 62, 66 und 70. Level 6 soll das Baby nach der Schalenform laden.

## Umsetzung und Abnahme

1. Den 3D-Adapter für die Kinderkarte einbinden und `dragon.model_title`, `dragon.model_loading` und `dragon.model_play` auf Deutsch und Englisch ergänzen. Das Drachensymbol dient als Rückfall bei Lade- oder WebGL-Fehlern. Namensvergabe, XP-Regeln und Datenbankschema beibehalten.
2. Den Adapter gegen den ursprünglichen Viewer unter `frontend/public/dragon3d/` prüfen. Insbesondere Nachrichten beim Start und Wechsel der Wachstumsform, Interaktion, sichtbare Ladefehler, pausierte Animation im Hintergrund und reduzierte Bewegung überprüfen. Der begonnene Adapter implementiert bislang Tippen/Spielen. Automatische Reaktionen etwa auf Lob und Levelaufstieg aus dem Originalpaket sind noch nicht übernommen. Die aktuelle Fortschritts-API liefert nicht alle Ereignisfelder des alten Pakets.
3. Typprüfung, Frontendtests und Produktionsbuild ausführen. Im Browser mit einer Testfamilie auf „Heute“ prüfen, dass bei Level 6 das Baby gerendert wird, der gespeicherte Name erscheint und Interaktion sowie Rückfall funktionieren. Den Viewer auch über den gebauten App-Server prüfen, weil er als gleichursprünglicher iframe mit eigenen JS- und GLB-Dateien geladen wird.
4. Erst nach Abnahme ein neues App-Image für den QNAP vorbereiten. Der alte Installer aus dem ursprünglichen 3D-Paket ist für die frühere Einzel-Familien-Version gebaut. Den produktiven Wechsel führt der Nutzer nach gesonderter Freigabe selbst aus.

## Bestätigter Produktionsstand

- Die neue Mehrfamilien-Architektur läuft auf dem QNAP unter `https://famquest.websiteclone.de/`. Die migrierte Familie hat eine separate Familien-DB und nutzt die zentrale Anmeldung. Die Produktionsmigration wurde mit einer Familie abgenommen. Sertl und Henning sind weiterer Einrichtungsumfang und hier nicht als produktiv abgenommen dokumentiert.
- Die produktive Anwendung heißt `famquest-live` und enthält `live-db`, `live-app`, `live-gateway` und `live-mcp`. Cloudflare routet den Produktionshost einschließlich OAuth und MCP zum Live-Gateway. Den produktiven Connector bei Bedarf mit frischer OAuth-Registrierung verbinden. Der produktive MCP-Lesetest und ein MCP-Schreibtest auf der isolierten Kopie waren erfolgreich.
- Das Produktionsimage ist auf den Digest mit Präfix `d4073b03` fixiert. Eine spätere Aktualisierung muss die zentrale Anmeldung, das Gateway, die MCP-Verbindung und den bestehenden Betrieb berücksichtigen. Keine produktiven Änderungen oder riskanten Migrationen ohne gesonderte Freigabe.
- Die tägliche Sicherung ist auf **03:30 Uhr NAS-Zeit** eingestellt. Ein vorgezogener vollständiger Lauf über den QNAP-Zeitplaner wurde erfolgreich bestätigt, anschließend wurde der Dauerzeitplan wiederhergestellt. Der Job pausiert App und MCP kurz. Die Sicherungen liegen privat unter `/share/Container/famquest-live/backups`.
- Die erste Live-Sicherung wurde isoliert zurückgesichert. Beide Datenbanken und alle zwölf Uploads wurden geprüft. Rollen und Laufzeitkonfiguration wurden per Prüfsumme geprüft. Ein vollständiger App-Start aus dieser Rücksicherung war nicht Teil der Probe. Alte Restore-Container dürfen das produktiv verwendete PostgreSQL-Volume nicht gleichzeitig öffnen.

Die lokalen QNAP-Compose-Dateien und Betriebsartefakte liegen im Desktop-Arbeitsbereich neben dem Repository unter `FamQuest-Dauerbetrieb`. Diese Übergabe enthält keine privaten Konfigurationen, Sicherungen oder Zugangsdaten.
