# Integrierter Familien-Testserver

`app.multitenant_app.create_app` verbindet den zentralen Login mit den bestehenden
Fachdaten-Routern. Der produktive Einstieg `app.main:app` bleibt unverändert.
Es gibt keinen automatischen Migrationslauf, keine automatische Familienaktivierung
und keinen Zugriff auf produktive Testdaten beim Import.

## Neue Sicherheitsgrenze

Die zentral verifizierte Sitzung liefert Familie und Rolle sowie einen expliziten,
familienlokalen User-Verweis. Dieser wird vor jedem Fachdatenzugriff validiert.
Die lokale Rolle muss zur zentralen Rolle passen. Die API behält lokale Audit-IDs,
verwendet aber niemals einen lokalen Passwort-Hash zur Anmeldung. Browser-Sitzungen
liegen zentral; vorhandene Legacy-Sitzungen und globale MCP-Parent-Header sind
keine Anmeldung für den integrierten Server.

Alle eingebundenen Fachrouten verwenden die überschreibbare gemeinsame DB-
Abhängigkeit. Dadurch erhalten Aufgaben, Routinen, Haushalt, Belohnungen, Punkte,
Freigaben, Profil, Wetter, Mahlzeiten, Einkauf und Kalender jeweils eine Session
zur richtigen Familien-Datenbank. Uploads verwenden getrennte Familienordner.

Die Login-/Me-Antwort entspricht jetzt dem Format der vorhandenen Oberfläche.
Private Browser-Caches werden bei einem Kontowechsel geleert. Die unabhängige
Auth-Revision `e20261031_actors` ergänzt die explizite lokale Actor-Zuordnung;
Bestandszuordnungen werden nicht geraten oder ungeprüft aktiviert.

## Prüfungen und Grenzen

Lokale HTTP-Tests verwenden getrennte Auth-/Sertl-/Henning-Datenbanken und prüfen
gleichzeitige Anmeldungen, Lesen, Schreiben, manipulierte Header, CSRF, gleiche
Bilddateinamen, Sperrung, fehlende Zuordnung, PIN-Reste, zentrale Passwortänderung
und gebundene MCP-Lesezugriffe. Ein separater PostgreSQL-Test provisioniert drei
temporäre Datenbanken mit eigenen Rollen, migriert vollständige Schemas und prüft
Fachdatenzugriffe sowie die verweigerte Verbindung von Family-A-Rollen auf Family B.
Dieser PostgreSQL-Test benötigt noch den CI-Lauf des neuen Commits.

Der aktuelle Stand ist ein überprüfbarer Integrationszwischenstand, **kein
Mehrfamilien-Produktivrelease**. Account-/Mitgliedsbearbeitung, Google-Neuanbindung
und MCP-Schreibzugriffe sind absichtlich gesperrt. Automatische Scheduler werden
noch nicht gestartet. Die verbleibenden Implementierungen und der Restore-/Cutover-
Probelauf sind vor einem Deployment abzuschließen. Siehe `legacy-settings-audit.md`.
