# Zentralen Testbetrieb vorbereiten

Die alternative Compose-Datei `docker-compose.central.yml` startet ausschließlich
die integrierte Anwendung an einem getrennten lokalen Port. Sie erstellt keine
Datenbanken und führt keine Migrationen aus. Nicht mit produktiven Verbindungen
oder Upload-Verzeichnissen starten, solange Migration und Restore nicht geprüft
und die konkrete Umstellung freigegeben sind.

Das Image muss aus dem geprüften Commit gebaut und unveränderlich referenziert
werden. `FAMQUEST_CENTRAL_IMAGE` benennt dieses lokal vorhandene Image;
`FAMQUEST_CENTRAL_UPLOADS` ein isoliertes, wiederhergestelltes Testverzeichnis.
Die separate, nicht eingecheckte `.env.central` enthält die HTTPS-Testadresse und
dedizierte zentrale bzw. familienlokale DB-Zugänge. Es gibt keinen Rückfall auf
den bisherigen allgemeinen DB-Benutzer. Ein Reverse-Proxy muss Host und HTTPS
korrekt weitergeben; nur den tatsächlichen Proxy als vertrauenswürdig konfigurieren.

Vor dem Start läuft `python -m app.deployment_check`. Diese Prüfung liest nur:

- Zentrale und aktive Familien müssen exakt den aktuellen unabhängigen
  Migrationsständen entsprechen.
- Mindestens eine aktive Familie und pro Familie ein zugeordnetes Elternkonto.
- Alle zentralen Konten müssen eine eindeutige, passende lokale Rolle besitzen.
- Lokale User-Zeilen dürfen keine alten Login-Hashes enthalten. Die Prüfung
  löscht solche Werte nicht automatisch; deren Entfernung ist ein gesonderter,
  zu prüfender Schritt nach gesicherter Übernahme in die zentrale Benutzer-DB.

Fehlende oder veraltete Schemata werden weder erstellt noch repariert.
Die normale Einfamilien-Startdatei bleibt unverändert auswählbar.

## Hintergrundjobs

`CENTRAL_BACKGROUND_JOBS=true` aktiviert ausdrücklich die familiengebundene
Prüfung der bereits konfigurierten Wochen-Taschengeldbuchungen. Es werden keine
Beträge erfunden, keine alten Wochen nachgebucht und keine Überweisungen ausgeführt.
Vorhandene Wochenschlüssel und Sperren verhindern doppelte Buchungen.

Kalenderzugriffe bleiben standardmäßig aus. Sie benötigen zusätzlich
`CENTRAL_CALENDAR_JOBS=true` und ein positives `CALENDAR_SYNC_MINUTES`.
Bei gesperrten oder zwischenzeitlich anders zugeordneten Familien wird kein Job
gestartet. Eine fehlerhafte Familie blockiert die anderen nicht. Beim Herunterfahren
wird eine bereits laufende Prüfung abgeschlossen, bevor Verbindungen geschlossen
werden. Die bisherige produktive Kalenderkonfiguration wurde nicht verändert.

Die Migrations-/Restore-Probe, der Datenvergleich und die Bonusregel-Abnahme
bleiben vor dem produktiven Einsatz erforderlich. Diese Dateien sind eine
Vorbereitung und kein Nachweis einer bereits erfolgten QNAP-Umstellung.
