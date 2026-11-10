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
- `famquest-test` verwendet `ghcr.io/manclone/famquest:test` und für MCP
  `ghcr.io/manclone/famquest-mcp:test`, jeweils mit `pull_policy: always`.
  Diese Tags zeigen nur auf erfolgreich geprüfte Images aus `codex/experiments`.
  Zusätzlich feste `test-<vollständiger Commit>`-Tags für Zuordnung/Rücksprünge behalten.
- Normale Updates erfolgen durch manuelles „Neu erstellen/Aktualisieren“ der
  bestehenden QNAP-Anwendung; Docker zieht dabei die aktuellen Test-Images.
  Keine Änderung der YAML-Imageversion und kein einzelner Pull-Befehl nötig.
  Ein Branch-Push allein verändert noch keine laufenden Container. Zugangsdaten,
  Datenbank, Uploads und Konfiguration bleiben erhalten.
- Nach erfolgreicher Testabnahme und Freigabe durch den Betreiber die geprüften
  Änderungen nach `main` übernehmen. Erfolgreiche CI-Prüfung und Veröffentlichung
  des main-Images bestätigen, bevor ein Produktionsupdate vorgeschlagen wird.
- `famquest-live` verwendet `ghcr.io/manclone/famquest:latest`. Dieser Tag ist
  ausschließlich für erfolgreich geprüfte main-Veröffentlichungen vorgesehen.
  Auch hier `pull_policy: always` verwenden; der Betreiber löst Updates durch
  „Neu erstellen/Aktualisieren“ der bestehenden Anwendung aus.
  Experimente dürfen den Produktions-Tag nicht überschreiben.
- Der Betreiber führt die produktive Umstellung selbst aus; keine eigenständigen
  QNAP-Produktivänderungen. Schrittweise anleiten, wenn eine Umstellung beauftragt ist.
- Test und Live verwenden getrennte Datenbanken und Uploads. Schemaänderungen
  können zusätzliche ausdrücklich geplante Migrationsschritte erfordern;
  nicht behaupten, dass jeder Versionswechsel ausschließlich per Pull möglich ist.

Details: `docs/famquest-test.md` und `docs/qnap-cleanup.md`.
