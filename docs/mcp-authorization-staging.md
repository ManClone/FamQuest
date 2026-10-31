# Eigene MCP-Autorisierung im Testserver

Die Routen sind nur in `app.multitenant_app.create_app` eingebunden. Die produktive
Anwendung und der vorhandene MCP-Container werden dadurch nicht umgeschaltet.

Der Browserablauf verwendet die zentrale Anmeldung, eine ausdrückliche Zustimmung
von Eltern und die aktuelle Familienzuordnung. Kinder können keine Freigabe
erteilen. CSRF und die konfigurierte Herkunft werden beim Zustimmen geprüft.
Unbekannte Clients und abweichende Weiterleitungsadressen erhalten keine Umleitung.
Nach dem Login wird nur der lokale `/authorize`-Dialog fortgesetzt.

Codes gelten fünf Minuten und können nur einmal mit passendem S256-Verifier und
registrierter Adresse eingelöst werden. Zugangstoken gelten zehn Minuten,
Refresh-Token 30 Tage. Refresh-Rotation, Wiederverwendungserkennung und Widerruf
werden im zentralen Register gespeichert. Ressourcenadresse und Familienzuordnung
sind serverseitig gebunden. Gesperrte Familien verlieren auch bestehende Zugänge.

Discovery nennt `/authorize`, `/token`, `/revoke` und die geschützte Ressource
`PUBLIC_URL/mcp`. Standardmäßig werden nur zuvor registrierte öffentliche Clients
akzeptiert. Die ausdrücklich aktivierte dynamische Registrierung akzeptiert je
Client genau eine HTTPS-Adresse, keine Wildcards, Fragmente oder Zugangsdaten.
Client-Metadaten werden nicht aus dem Netz geladen. Token und Codes werden nicht
im Klartext in der Datenbank gespeichert; Antworten dürfen nicht gecacht werden.

Die HTTP-Tests prüfen den vollständigen Zustimmungs- und Tokenablauf, falsche
Zieladressen, CSRF, Kinderkonten, doppelte Parameter, Körpergrößenlimit,
Code-Wiederverwendung, Refresh-Replay, Widerruf und Familiensperren. Die
Frontendtests prüfen erlaubte und abgelehnte Rücksprungziele.

Der alternative MCP-Einstieg `mcp/central_server.py` prüft jetzt jeden Zugang über
den integrierten Server und reicht dessen individuellen Bearer weiter. Es gibt
keinen Service-Token, keine GitHub-Elternliste und keinen Rückfall auf alte
Sitzungscookies. Der Server prüft Rolle, Familie, lokale Elternzuordnung,
Gültigkeit und Ressourcenadresse. Bei Ausfall wird der Zugang abgewiesen.

`/.well-known/famquest-mcp-tools` liefert nur Werkzeugdefinitionen, keine
Familiendaten. Kontoverwaltung, Banking und Geld bleiben ausgeschlossen.
Alle 76 Werkzeuge lassen sich aus dem tatsächlichen Schema erzeugen.
Die Familiendaten bleiben auch beim Abruf dieser öffentlichen Definitionen geschützt.

Schreibaktionen reservieren ihren Auftragsschlüssel vor der Ausführung dauerhaft
in der jeweiligen Familien-Datenbank. Gleicher Auftrag und gleicher Inhalt liefern
das gespeicherte Ergebnis; anderer Inhalt mit gleichem Schlüssel wird abgewiesen.
Parallele Anfragen führen nur eine Mutation aus. Ein Ausfall nach der fachlichen
Speicherung hinterlässt einen unklaren Ausgang und löst keine automatische
Wiederholung aus. Authentifizierung und nötige Elternbestätigung erfolgen auch vor
der Rückgabe gespeicherter Ergebnisse. Schlüssel dürfen nicht für neue Aufträge
wiederverwendet werden. Es gibt kein automatisches Löschen dieser Nachweise.
Antworten und Nachweise werden nicht in der zentralen Benutzer-Datenbank gespeichert.

Die additive Family-Revision `m20261031mcpactions` muss explizit migriert sein.
Die neue Compose-Datei ist nur eine vorbereitete Alternative; sie wurde nicht
auf dem QNAP gestartet. Der Proxy muss im zentralen Modus ausschließlich `/mcp`
und dessen Unterpfade zum MCP-Container leiten (`CENTRAL_MCP_PATH_PATTERN`).
OAuth, Login, Discovery und die übrigen App-Routen gehören zum integrierten
Webserver. Die öffentliche HTTPS-Adresse muss für den MCP-Container erreichbar
sein; Weiterleitungen werden bei der Tokenprüfung nicht verfolgt.

Noch offen vor produktiver Aktivierung: vollständige CI mit PostgreSQL,
Migrations-/Restore-Probe und Freigabe der konkreten Proxy-/Container-Umstellung.
Der bestehende produktive MCP-Einstieg und QNAP bleiben unverändert.
