# FamQuest: geprüfter Integrationsstand vom 31.10.2026

## Ergebnis

Der Entwurf ist erheblich weiter als der ursprüngliche Einfamilienstand, aber
noch kein freigegebenes Mehrfamilien-Produktivrelease. Keine Migration, keine
Aktivierung von Sertl/Henning und keine Änderungen am QNAP wurden ausgeführt.
Der historische Healthcheck war erfolgreich; das aktuelle laufende Image,
dessen Digest und die produktive Kalenderkonfiguration sind nicht verifiziert.

## Implementiert

- Zentrale Benutzer-Datenbank mit Browser-Anmeldung, Sitzungen, Passwortwechsel,
  Rollen und familienlokaler Kontozuordnung. Lokale User-Zeilen enthalten keine
  anmeldbaren Passwort-Hashes. Kontoänderungen und Fehler zwischen den beiden
  Datenbank-Commits sind explizit behandelt und reparierbar.
- Integrierter Testserver: Authentifizierte Familie bestimmt die Datenbank aller
  eingebundenen Fachrouten. Getrennte Datenbankrollen und Bildordner; keine
  Auswahl über unzuverlässige Request-Header. Gleichzeitige Familien mit gleichen
  lokalen IDs und Bilddateinamen sind gegeneinander getestet.
- Haushaltsstatistik: Eltern vergleichen geschätzte Minuten, Kinder Erledigungen.
  Neue Erledigungen speichern ihre damalige Zeitvorgabe. Historische Einträge ohne
  Momentaufnahme verwenden die heutige Vorgabe und sind entsprechend bezeichnet.
- OAuth-Discovery, ausdrückliche Elternzustimmung, PKCE, einmalige Codes,
  Zugangstoken, Refresh-Rotation und Widerruf im integrierten Testserver.
  Registrierung ist standardmäßig geschlossen. Der Browser setzt nach Login
  ausschließlich den lokalen Zustimmungsdialog fort.
- Altlasten: private Browser-Caches werden beim Kontowechsel gelöscht, PIN-Reste
  sperren Eltern nicht aus, Demo-Modus wird im integrierten Betrieb abgelehnt.
  Kalenderoperationen verwenden explizite Familienverbindungen und prüfen Sperren.
- Der Einrichtungsweg verwendet dieselbe Namensprüfung wie das Familienrouting:
  Die zentrale Benutzer-Datenbank, leere und überlange Namen werden abgewiesen,
  bevor eine Datenbankverbindung geöffnet wird.

## Nachweise

Der Kontenstand 49df099a27c8f5224f4dcfe5dc5176301c0e9c0a besteht beide vollständigen
GitHub-Workflows: Predeployment 41217993981 und Security 41217993919. Dabei werden
vollständige PostgreSQL-Migrationen, Familienisolation, getrennte Datenbankrollen,
parallele Anmeldungen und konkurrierende Kontoanlage geprüft.

Der zusätzliche OAuth-HTTP-Stand 245167cdff0990318cbf6191a46012495de4fa6e besteht
lokal 39 gemeinsame Anmelde-/Familien-/Fehlercodetests plus den Test gegen eine
widersprüchliche lokale Elternrolle. Alle 322 Frontendtests, Typprüfung und
Produktions-Build sind grün. Die vollständigen GitHub-Läufe 41219154961 und
41219154987 sind beim Erstellen dieses Dokuments noch nicht abgeschlossen.
Die anschließende Absicherung des Einrichtungswegs besteht 39 lokale Tests mit
Familienrouting und integrierten HTTP-Anfragen. Verbindlicher aktueller CI-Status:
https://github.com/ManClone/FamQuest/pull/34/checks

## Verbleibende Release-Arbeit

| Bereich | Noch erforderlich |
| --- | --- |
| MCP | Eigenständigen MCP-Dienst an die individuelle zentrale Tokenprüfung anbinden; Service-Token und globale Elternzuordnung ablösen; doppelte Schreibaktionen verhindern und explizite Elternbestätigungen durchgängig prüfen. MCP-Schreibzugriffe bleiben bis dahin gesperrt. |
| Hintergrundjobs | Automatische Wochenabrechnung und gegebenenfalls Kalenderaktualisierung mit expliziten Familienverbindungen ausführen. Im integrierten Testserver starten noch keine Scheduler. |
| Kalender | Google-Neuanbindung bleibt im Testserver gesperrt. Die produktive Einstellung ist unbekannt; bewusst ausgeschaltete Kalenderfunktionen dürfen nicht ungeprüft aktiviert werden. |
| Bonusregeln | Feste Kritikstufen, geschütztes Grundtaschengeld und Restbonus sowie unveränderliche abgeschlossene Wochen gemäß Issue #25 gegen API und Oberfläche abgleichen und absichern. Bankanbindung bleibt ein gesonderter Machbarkeitstest. |
| Abnahme | Abzeichen/Drache aus Issues #29/#30 gegen die vereinbarten Kriterien abnehmen. |
| Migration/Deployment | Wiederherstellbare Testkopie, vollständige Restore-Probe und Vorher-/Nachher-Abgleich von IDs, Konten, XP, Boni und Uploads; Produktionskonfiguration und Image prüfen; konkrete Umstellung vorlegen und freigeben lassen. |

Der produktive Einstieg app.main:app ist noch unverändert. Der neue Server liegt
separat in app.multitenant_app.create_app. Details stehen in
integrated-family-staging.md, mcp-authorization-staging.md,
legacy-settings-audit.md und household-statistics.md.

Die Freigabe des Nutzers deckt notwendige getestete Änderungen im bestehenden
GitHub-Entwurf und deren Prüfungen ab. Risikoreiche Migrationen und produktive
Änderungen sind separat freizugeben.