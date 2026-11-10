# Zusammenarbeit und dauerhafter Entwicklungsablauf

Diese vom Betreiber festgelegten Regeln gelten für weitere Arbeiten in diesem
Repository. Sie ersetzen überholte Vorschläge aus historischen Übergaben.

- Genau zwei dauerhafte FamQuest-Anwendungen auf dem QNAP: `famquest-live`
  und `famquest-test`. Für normale Entwicklungen keine weiteren Stage-,
  Restore-, Prepare- oder Release-Anwendungen anlegen. Notwendige einmalige
  Wartungscontainer über die vorhandene Anwendung koordinieren und entfernen.
- Neue Entwicklung erfolgt auf `codex/experiments` beziehungsweise einem
  ausdrücklich vereinbarten Entwicklungsbranch. Code im Repository ändern,
  prüfen und über CI in versionierte Docker-Images bauen.
- `famquest-test` bleibt auf einer ausdrücklich ausgewählten unveränderlichen
  Version wie `ghcr.io/manclone/famquest:test-<vollständiger Commit>` gepinnt.
  Ein neuer Branch-Push darf die laufende Testanwendung nicht automatisch ändern.
  Für MCP bei Bedarf dieselbe freigegebene Testrevision auswählen.
- Testupdates hauptsächlich per `docker pull` der ausgewählten Version und
  Aktualisierung der bestehenden Compose-Anwendung. Zugangsdaten, Datenbank,
  Uploads und Konfiguration dauerhaft erhalten; kein wiederholter Neuaufbau
  der Testanwendung oder Neuerzeugen von Zugängen für normale Imageupdates.
- Nach erfolgreicher Testabnahme und Freigabe durch den Betreiber die geprüften
  Änderungen nach `main` übernehmen. Erfolgreiche CI-Prüfung und Veröffentlichung
  des main-Images bestätigen, bevor ein Produktionsupdate vorgeschlagen wird.
- `famquest-live` verwendet `ghcr.io/manclone/famquest:latest`. Dieser Tag ist
  ausschließlich für erfolgreich geprüfte main-Veröffentlichungen vorgesehen.
  Produktivupdates gezielt per Pull und Aktualisierung der bestehenden Anwendung.
  Experimente dürfen den Produktions-Tag nicht überschreiben.
- Der Betreiber führt die produktive Umstellung selbst aus; keine eigenständigen
  QNAP-Produktivänderungen. Schrittweise anleiten, wenn eine Umstellung beauftragt ist.
- Test und Live verwenden getrennte Datenbanken und Uploads. Schemaänderungen
  können zusätzliche ausdrücklich geplante Migrationsschritte erfordern;
  nicht behaupten, dass jeder Versionswechsel ausschließlich per Pull möglich ist.

Details: `docs/famquest-test.md` und `docs/qnap-cleanup.md`.
