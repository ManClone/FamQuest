# FamQuest – sichere Mehrfamilienfähigkeit (Implementierungsplan)

Status: Entwurf; **keine Änderung an der produktiven Datenbank**. Umsetzung in überprüfbaren PRs, erst nach erfolgreichen Isolationstests deployen.

## Ist-Zustand und Risiko

- `Family` in `backend/app/models.py` ist durch `CheckConstraint("singleton")` und einen eindeutigen `singleton`-Wert ausdrücklich auf genau eine Familie begrenzt.
- `auth.get_family(db)` liest ohne Mandantenfilter `select(Family).one_or_none()`.
- `User.family_id` wird im Entwurfsbranch additiv eingeführt und für Bestandskonten befüllt; `FamilyMember` und zahlreiche weitere Tabellen besitzen noch keine Mandantenzuordnung. Zahlreiche Endpunkte verwenden weiterhin globalen Datenzugriff.
- `current_session` erlaubt neben Cookie-Sessions auch MCP-Bearer-Anfragen mit `x-famquest-parent-id`. Auch dieser Weg muss mandantengebunden werden.
- Die bereits vorhandenen Grasser-Daten (Mitglieder, XP, Aufgaben, Konten, Transaktionen, Belohnungen, Medien) dürfen weder gelöscht noch unbemerkt umgehängt werden.

**Wichtig:** Den Singleton-Constraint allein zu entfernen ist unsicher. Vor Freischaltung einer zweiten Familie müssen sämtliche Lese- und Schreibpfade tenant-sicher sein.

## Zielmodell

1. Eine gemeinsame PostgreSQL-Instanz, eine App, getrennte Familien als Mandanten.
2. `families.id` bleibt stabil; der bestehende Datensatz ist die Familie Grasser. Migrationen sind additiv, rückwärtskompatibel und idempotent, soweit möglich.
3. Eigene Superadmin-Rolle zur Verwaltung von Familien und Einladungen, **nicht** als normaler Familien-Admin mit Zugriff auf private Familieninhalte.
4. Eltern und Kinder gehören einer Familie an. Keine selbstgewählte `family_id` aus Client-Payload, Header oder Query-Parameter akzeptieren. Mandant kommt ausschließlich aus serverseitig authentifizierter Identität.
5. Datenübergreifende Beziehungen (Mitglieder, Quests, Belohnungen, Freigaben, Zahlungen, Bankkonten, Kalender, Bilder, Konfigurationen) werden auf Familienzugehörigkeit geprüft; auch indirekte IDs.
6. E-Mail-Logins bleiben eindeutig; eine spätere Mehrfachmitgliedschaft erfordert ein explizites Membership-Modell und Familienwechsel mit neuem Berechtigungskontext.

## Phasen und Abnahmekriterien

### PR A – Datenmodell und Bestandsmigration

- Inventar aller Tabellen, Foreign Keys, Indizes, API-Routen und MCP-Aktionen.
- `family_id` bei `users` und mandantenbezogenen Wurzeltabellen ergänzen; bei abhängigen Tabellen entweder `family_id` oder abgesicherte Parent-Beziehung mit eindeutiger Zugehörigkeit.
- Vorhandene Zeilen explizit anhand des bestehenden Familien-Datensatzes zuordnen. Keine neue Default-Familie anlegen, wenn bereits eine existiert.
- Singleton-Einschränkung **erst entfernen, wenn** sämtliche Datenzugriffe mandantenfähig sind.
- Mehrmandantenfähige Unique-Constraints, insbesondere Mitgliederfarben und familieninterne Namen/Schlüssel, prüfen.
- Alembic-Migration auf einer Kopie des realen Backups testen; Revisionskette und `alembic check` prüfen.

### PR B – Authentifizierung und Isolation

- `CurrentFamily`-Dependency aus validierter Session/Benutzer-Familienzuordnung.
- Alle Routen, Services, Jobs und MCP-Aktionen nach Familie filtern; Schreibzugriffe gegen Cross-Tenant-IDs absichern.
- 403/404 statt Informationen über fremde Datensätze; keine fremden Daten in Fehlertexten oder aggregierten Statistiken.
- Superadmin erhält getrennte Verwaltungsrouten und Berechtigungen. Keine automatische Familienmitgliedschaft.
- Hintergrundjobs (z. B. Routinen) explizit pro Familie ausführen.

### PR C – Administration und Benutzeroberfläche

- Separate Superadmin-Anmeldung, sichere Einrichtung ohne hartcodiertes Passwort, optional MFA.
- Familien anlegen/deaktivieren, Eltern einladen, Einladungen zeitlich begrenzen; Audit-Log.
- Neue Familie Sertl erst nach vollständig grünen Isolationstests anlegen.
- Kinder-/Eltern-Ansichten bleiben innerhalb ihrer eigenen Familie.

### PR D – Rollout

- Vor Deployment frischen PostgreSQL-Dump **und** Uploads sichern.
- Migration zuerst gegen eine Kopie der Bestandsdaten testen; Anzahl/Checksummen relevanter Datensätze vergleichen.
- Isolationstests mit Grasser und Sertl: alle API-Endpunkte, fremde IDs, MCP, Dateizugriffe, Hintergrundjobs.
- Kein `down -v`, keine Datenbank-Neuinitialisierung, kein `alembic stamp` zur Fehlerumgehung.
- QNAP-Deployment erst nach Freigabe; nachher Bestandsdaten (Tim: XP, Aufgaben, Bonus, Konten, Belohnungen) kontrollieren.

## Sofortige Sicherheitsregel

Solange die Mandantenisolierung nicht vollständig implementiert und getestet ist, bleibt die produktive Installation **Single-Family**. Kein zweiter Familien-Datensatz, kein Superadmin in Produktion.

## Beschlossene MCP-Anmeldung (ohne Auth0)

- ChatGPT verwendet **OAuth 2.0 Authorization Code mit PKCE** gegen FamQuest selbst. Der Benutzer meldet sich beim Verknüpfen im FamQuest-Login an; ChatGPT erhält niemals sein Passwort.
- FamQuest betreibt die für den MCP-Client benötigten Discovery-, Authorization- und Token-Endpunkte mit strikter Redirect-URI-Prüfung, Client-Registrierung nach unterstütztem Verfahren, PKCE-S256, State-Prüfung und TLS über den bestehenden Tunnel. Die exakte ChatGPT-Client-Kompatibilität muss vor Implementierung anhand aktueller Vorgaben verifiziert werden.
- Access-Tokens sind kurzlebig, widerrufbar und an Benutzer, Familie, Client und Berechtigungen gebunden; Refresh-Tokens werden rotiert und nur gehasht gespeichert. Token-Audience ist ausschließlich der MCP-Resource-Server.
- MCP-Backend leitet Benutzer und Familie **ausschließlich** aus dem serverseitig geprüften Token ab, niemals aus `X-FamQuest-Parent-ID`, einem Familien-Header oder Tool-Parametern.
- Jeder MCP-Aufruf nutzt dieselben mandantengeprüften Services wie die Web-App. Schreiboperationen mit Elternfreigabe verlangen weiterhin eine explizite Bestätigung.
- Der bisherige globale MCP-Service-Token plus `X-FamQuest-Parent-ID` ist **nur ein Legacy-Übergang** und darf nicht für mehrere Familien freigeschaltet werden. Er muss vor dem Mehrfamilien-Rollout deaktiviert/ersetzt werden.
- Abnahmetests: fremde Familien-IDs und fremde Objekt-IDs, abgelaufene/widerrufene Tokens, falsche Audience, manipulierte Redirect-URIs, fehlende PKCE, Token-Wiederverwendung und Rollentrennung.
