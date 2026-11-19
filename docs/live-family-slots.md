# Einen neuen Familienplatz in Live vorbereiten

Der Betreiber legt Familien unter `/operator` an. Dafür muss eine leere Datenbank
mit einer eigenen eingeschränkten Rolle vorbereitet sein. Der Live-Webprozess
erhält niemals Owner-Zugangsdaten oder Rechte zum Anlegen von Datenbanken.

`app.live_family_slots` ist ein ausdrücklich gestarteter Wartungshelfer. Er prüft
Host `live-db`, Produktionsadresse und den aktuellen Auth-Schemastand. Er verweigert
bereits vorhandene Datenbanken, Rollen, Konfigurationseinträge und Sicherungsdateien.
Nur die neue Datenbank wird auf den Schema-Stand des verwendeten App-Images migriert
und anschließend auf leere Fachdatentabellen geprüft. Bestehende Datenbanken werden
nicht migriert. Vor der Änderung wird `runtime.before-<Datenbankname>.json` exklusiv
und privat gespeichert. Die neue `runtime.json` wird atomar ersetzt, mit dem
bisherigen Eigentümer und Modus 0600. Bestehende Einstellungen und Kennwörter bleiben
erhalten. Bei Teilfehlern bleiben Artefakte zur manuellen Prüfung liegen; niemals
blind erneut ausführen oder Datenbanken/Rollen/Konfigurationskopien löschen.

## Ablauf auf dem NAS

1. Koordiniertes Live-Backup erfolgreich ausführen. Noch keine Familie anlegen.
2. Den Backupbefehl in der kanonischen `/share/Container/famquest-live/compose.yml`
   mit `scripts/prepare-live-backup.py` und
   `scripts/qnap-live-multitenant-backup.sh` aktualisieren. Der Patcher ändert nur
   `services.backup.command`, sichert das Original privat und behält andere Services
   und deren Imageversionen bei. Mit `docker compose config --quiet` validieren und
   den vorhandenen Scheduler mit `--run` erfolgreich prüfen. Nicht die vollständige
   Repository-Vorlage über die angepasste NAS-Konfiguration kopieren.
3. Während der Platzvorbereitung denselben Lock wie der tägliche Backupjob halten:
   `/share/homes/clone88/.famquest-live-auto-backup-lock`. Einen bestehenden Lock
   nicht löschen. Dadurch können Backup und Konfigurationsänderung nicht überlappen.
4. Einen kurzlebigen Wartungscontainer mit genau der Image-ID des laufenden Live-App-
   Containers starten. Netzwerk `famquest-live_data`, UID 0, schreibgeschütztes
   Container-Dateisystem und `/tmp` als tmpfs. Das vorhandene externe Volume
   `famquest-live-config-v1` unter `/live-config` schreibbar einbinden. Nur diesem
   Container die Owner-Variablen mit
   `--env-file /share/Container/famquest-central-stage/postgres.env` mitgeben.
   Der neue, geprüfte Helfer kann beim unveränderten bestehenden App-Image als
   schreibgeschützte Datei nach `/app/app/live_family_slots.py` eingebunden werden.
   Beispiel-Einstieg: `python -m app.live_family_slots --database famquest_sertl_runtime`.
   Keine zusätzliche Container-Station-Anwendung und kein Pull nötig.
5. Nur nach erfolgreichem Helferlauf `live-app` neu starten, seine Health-Prüfung
   abwarten und MCP neu starten. Den Lock wieder freigeben. Bei Fehlern stoppen und
   den tatsächlichen Zustand prüfen; keine automatische Rücksetzung oder Löschung.
6. Unter `/operator` aktualisieren: ein freier Platz sollte sichtbar sein.
   Familienname, Elternname und Elternadresse eintragen und ein eigenes Anfangspasswort
   direkt in der Oberfläche setzen. Keine Zugangsdaten in Shellargumenten speichern.
7. Nach erfolgreicher Anlage erneut koordiniert sichern. Elternlogin und Trennung
   von der bisherigen Familie prüfen. Die Anlage allein ist kein Isolationstest.

## Mehrmandanten-Backup

Der neue Backupbefehl erfasst alle Nicht-Template-Datenbanken des Live-PostgreSQL-
Clusters. `DATABASES` enthält deren Namen, `databases/<Name>.dump` die geprüften Dumps.
Die bisherigen Dateien `auth.dump` und `family.dump` bleiben als Kopien der zentralen
Benutzer-DB und Grasser-DB für bestehende Restore-Anweisungen erhalten. Globale Rollen,
gemeinsame Uploads und private Laufzeitkonfiguration werden ebenfalls gesichert.
Alle Dateien einschließlich neuer Datenbank-Dumps stehen in `SHA256SUMS`.
`BACKUP-COMPLETE` entsteht erst nach erfolgreicher Prüfung aller Dateien.
Eine erfolgreiche Sicherung bestätigt keine produktive Wiederherstellung.

Die Erweiterung der Backup-YAML gehört auch in eine spätere Übernahme der
Container-Station-Konfiguration, damit eine veraltete Vorlage den Backupbefehl
nicht wieder auf eine einzige Familie zurücksetzt.
