# FamQuest MCP mit GitHub OAuth

Der Dienst erzeugt Werkzeuge aus dem aktuellen FamQuest-API-Schema. Aufgabenparameter
werden nicht nochmals vereinfacht: Wiederholung, mehrere Tageszeiten, Personen, XP,
Freigabe, optionale und wiederholbare Aufgaben bleiben erhalten. Haushalt, Routinen,
Wochenverteilung, Kalender lesen, Essensplan, Einkauf und Belohnungsverwaltung sind enthalten.
`get_pending_notifications` liest offene Kinderfreigaben, faellige Hausarbeiten und offene
Einmalaufgaben. Es versendet selbst keine Nachrichten und richtet keine Automatisierung ein.

## Identitaet und Grenzen

GitHub OAuth authentifiziert den Benutzer. `FAMQUEST_GITHUB_PARENTS` ordnet unveraenderliche
numerische GitHub-IDs bestehenden FamQuest-**Konto-IDs** zu (keine Familienmitglied-IDs).
Nicht zugeordnete GitHub-Konten erhalten keine Werkzeuge. FamQuest prueft bei jedem Aufruf,
dass das zugeordnete Konto noch existiert und Eltern-/Adminrechte hat. Kein Cookie-Login
und keine Weitergabe des GitHub-Tokens an die FamQuest-API.

Die App braucht `MCP_SERVICE_TOKEN`; der MCP-Dienst denselben Wert als
`FAMQUEST_SERVICE_TOKEN`. Mindestens 32 zufaellige Zeichen, getrennt von allen OAuth-Secrets.
Zugangsdaten, Kontoverwaltung, Bankbuchungen und manuelle Geldbuchungen sind ausgeschlossen.
Sterne-Korrekturen sind fuer Eltern verfuegbar. Kinderfreigaben verlangen eine ausdrueckliche
Elternentscheidung: das Werkzeug verlangt dazu `X-MCP-Parent-Confirmed=true`.
Diese Angabe dokumentiert die Bestaetigung im Werkzeugaufruf; sie ersetzt keine menschliche
Entscheidung. Der Assistent darf sie nie fuer eine automatische Freigabe setzen.

Jede Schreibaktion benoetigt `X-MCP-Request-Key` (UUID). Gleicher Elternteil, Schluessel
und Inhalt liefern das gespeicherte Ergebnis zurueck. Andere Inhalte mit gleichem Schluessel
werden abgewiesen. Nach Verbindungsabbruch oder Absturz wird ein unbekanntes Ergebnis
nicht automatisch erneut geschrieben: zuerst aktuellen FamQuest-Stand pruefen.
SQLite im persistenten Volume speichert Zeitpunkt, Eltern-ID, Pfad, Fingerabdruck und Ergebnis.
Darin koennen Familiendaten stehen; das Volume gehoert in die Datensicherung.

## Einrichtung (noch nicht auf dem NAS aktiviert)

1. `mcp/.env.example` nach `mcp/.env` kopieren und dort die Werte setzen.
2. GitHub OAuth App anlegen. Homepage ist `MCP_PUBLIC_URL`, Callback ist exakt
   `MCP_PUBLIC_URL/auth/callback`. Nur `read:user` wird benoetigt, kein Repositoryzugriff.
3. Eigene GitHub-ID und korrekte FamQuest-Eltern-Konto-ID zuordnen. Client-ID und Secret
   lokal in die MCP-Umgebung eintragen; Secrets nicht in Chat oder Git ablegen.
4. Separate zufaellige Service-/JWT-Schluessel erzeugen. Den Speicher-Schluessel mit
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   erzeugen. JWT- und Speicherschluessel bei Neustarts beibehalten. OAuth-Daten werden
   verschluesselt im persistenten Volume gespeichert.
5. App und MCP in dasselbe interne Docker-Netzwerk aufnehmen. Der separate Compose-Dienst
   kann `app` sonst nicht aufloesen. `FAMQUEST_API_URL` muss auf die aktualisierte App zeigen.
6. Dieselbe oeffentliche Origin kann App und MCP bedienen: `MCP_PUBLIC_URL` ist dann
   beispielsweise `https://famquest.websiteclone.de` (ohne `/mcp`). Der MCP-Endpunkt ist
   `https://famquest.websiteclone.de/mcp`, GitHubs Callback
   `https://famquest.websiteclone.de/auth/callback`.
   Vor der vorhandenen App-Fallbackroute eine Cloudflare-Pfadregel zum Dienst
   `http://famquest-mcp:8000` einfuegen. Die notwendigen Pfade stehen in `routing.py`.
   Die Pfade unveraendert weiterleiten; Discovery, Anmeldung, Consent und Tokenaustausch
   gehoeren zum MCP-Dienst. Alle anderen Pfade bleiben beim bisherigen App-Ziel.
7. `docker compose up -d --build` im MCP-Verzeichnis. In ChatGPT den MCP-Endpunkt
   `https://<App-Hostname>/mcp` mit OAuth verbinden und zuerst `get_connected_parent` pruefen.


Die beiden OAuth-Schluessel und die GitHub-App-Registrierung sind installationsabhaengig.
Ohne sie ist die Implementierung nicht als live angebunden zu betrachten. Ein echter
GitHub-/ChatGPT-Verbindungsdurchlauf bleibt Teil der Inbetriebnahme.

## Tests

`python -m unittest discover -s tests -v` prueft Identitaetszuordnung, Retry-Verhalten,
Schluesselkonflikte und unbekannte Ergebnisse ohne echte GitHub-Zugangsdaten. Backendtests
pruefen Rollen und die erlaubten API-Pfade. Docker baut mit `requirements.lock`.
Alte Quest-Entwurfsdaten bleiben im bisherigen Volume erhalten; sie werden nicht automatisch
als echte Aufgaben veroeffentlicht.
