# FamQuest – sichere Mehrfamilienfähigkeit (Implementierungsplan)

Status: Entwurf; **keine Änderung an der produktiven Datenbank**. Umsetzung in überprüfbaren PRs, erst nach erfolgreichen Isolationstests deployen.

## Ist-Zustand und Risiko

- `Family` in `backend/app/models.py` ist durch `CheckConstraint("singleton")` und einen eindeutigen `singleton`-Wert ausdrücklich auf genau eine Familie begrenzt.
- `auth.get_family(db)` liest ohne Mandantenfilter `select(Family).one_or_none()`.
- `User` und `FamilyMember` besitzen keine `family_id`. Zahlreiche Endpunkte verwenden globalen Datenzugriff.
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
