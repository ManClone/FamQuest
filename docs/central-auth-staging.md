# Zentrale Anmeldung: isolierter Testdienst

Der separat erzeugbare Dienst in `app.central_auth.create_app` implementiert
die Browser-Anmeldung an der zentralen Auth-Datenbank. Die bestehende Anwendung
in `app.main` bindet ihn bewusst noch nicht ein. Er ist **kein fertiges
Mehrfamilien-Deployment** und wird nicht automatisch auf QNAP gestartet.

## Implementiertes Verhalten

- Anmeldung prüft den zentral gespeicherten Passwort-Hash und genau eine gültige
  Mitgliedschaft in einer aktiven Familie. Die Familie kommt ausschließlich aus
  der Registry. Weder Header noch Login-Body können eine fremde Familie auswählen.
- Die Browser-Sitzung liegt ausschließlich in `famquest_auth`. Gespeichert wird
  nur der Cookie-Hash; das Cookie ist Secure, HttpOnly, SameSite=Lax, hostgebunden
  und für den Root-Pfad gesetzt. Es hat einen eigenen Namen und akzeptiert keine
  vorhandenen Legacy-Sitzungen. Gültigkeitsdauer: maximal ein Jahr, ohne implizite
  Verlängerung.
- Jede Sitzungsprüfung validiert die aktuelle Mitgliedschaft erneut. Gesperrte
  Familien, fehlende/geänderte Zuordnung und Superadmin-Identitäten werden
  abgewiesen. Ein Superadmin hat weiterhin keinen impliziten Familienzugriff.
- Schreibzugriffe erfordern die exakt konfigurierte HTTPS-Origin und den
  sitzungsbezogenen CSRF-Wert. Die Anmeldung selbst erfordert ebenfalls diese
  Origin. Login und Passwortwechsel haben Fehlversuchslimits.
- Passwortwechsel widerruft sämtliche zentralen Browser-Sitzungen, vorhandene
  OAuth-Grants und noch nicht verbrauchte Authorization-Codes des Kontos.
  Ein erneuter Login ist danach erforderlich. Identity-Locks synchronisieren
  konkurrierende Passwortwechsel und den Austausch von Authorization-Codes.
- Antworten werden nicht gecacht. Passwörter, Cookie-Secrets, Datenbanknamen und
  gespeicherte Hashes werden nicht in Sitzungsantworten ausgegeben.

## HTTP-Schnittstellen dieses Testdiensts

| Methode und Pfad | Verhalten |
| --- | --- |
| `POST /api/auth/login` | E-Mail/Passwort prüfen, neue Sitzung setzen |
| `GET /api/auth/me` | E-Mail, aktuelle Rolle, Familienname, CSRF-Wert |
| `POST /api/auth/logout` | Aktuelle Sitzung widerrufen und Cookie entfernen |
| `PUT /api/auth/password` | Passwort ändern; alle bestehenden Sitzungen und Grants widerrufen |
| `GET /api/health` | Erreichbarkeit der zentralen Datenbank prüfen |

Die Antwort ist noch nicht das bestehende Frontend-`MeResponse`-Format: Dafür
muss die serverseitig gewählte Familien-Datenbank geöffnet und das lokale
Familienmitglied sicher zugeordnet werden. Dieser Dienst enthält keine
Fachdaten-Endpunkte, keine Benutzer-Provisionierung und keinen OAuth-Consent-
oder Token-HTTP-Endpunkt. Es existiert keine öffentliche Registrierung.

## Datenbank und Abnahme

Die neue Revision `d20261031_sessions` gehört ausschließlich zur unabhängigen
Auth-Alembic-Historie. Kein `create_all`, keine Provisionierung und keine
Bestandsmigration werden beim Dienststart ausgeführt. Der Dienst verlangt eine
konfigurierte HTTPS-Origin und die bereits vorhandenen separaten Auth-DB-Credentials.

16 HTTP-Tests prüfen getrennte Sertl-/Henning-Anmeldungen, Cookie-Hash und Flags,
Header-Manipulation, Origin/CSRF, Logout, Ablauf, Widerruf bei geänderter
Mitgliedschaft, Passwortwechsel und Fehlversuchslimits. Zusätzlich prüfen die
PostgreSQL-Tests konkurrierende Passwortwechsel. Vor einer produktiven
Zusammenführung folgen Frontend-Anbindung, Tenant-Routing sämtlicher
Fachdaten-Endpunkte, Upload-/Job-Isolation und die Wiederherstellungsprobe.
