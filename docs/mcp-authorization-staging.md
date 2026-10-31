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

Noch offen: Der eigenständige MCP-Container muss diese Autorisierung tatsächlich
prüfen und den individuellen Bearer-Zugang weiterreichen. Schreibzugriffe bleiben
im integrierten Backend gesperrt, bis der Schutz vor doppelten Aktionen und die
Elternbestätigung vollständig angebunden sind. Dies ist noch kein freigegebener
produktiver Connector und aktiviert keine neue Verbindung auf dem QNAP.
