# Prüfung von Alt-Einstellungen und Kompatibilität

Geprüft am 31.10.2026 anhand des aktuellen Codes. Produktive QNAP-Konfiguration
und dortige Geheimnisse wurden hierfür nicht gelesen oder verändert. Insbesondere
ist der tatsächliche Status der Kalendersynchronisierung auf dem NAS nicht verifiziert.

## Behobene oder abgesicherte Übergänge

- **Globale Datenbank:** Der integrierte Testserver überschreibt die gemeinsame
  FastAPI-DB-Abhängigkeit. Vor jedem Fachdatenzugriff wird die zentrale Anmeldung
  geprüft und eine separate Family-Session geöffnet. Fehlende lokale Actor-Zuordnung
  wird abgelehnt; eine Familien-ID oder Parent-ID im Header bestimmt keine Verbindung.
- **Globale Kalenderverbindung:** Vorhandene manuelle und nachgelagerte Sync-Aufrufe
  verwenden im Mehrfamilienbetrieb die explizite Family-Engine und eine passende
  Session-Factory. Vor Ausführung wird der Familienstatus erneut geprüft. Der
  integrierte Testserver startet weiterhin keine automatischen Kalender- oder Geldjobs.
- **PIN-Reste:** Alte Datenbankfelder bleiben kompatibel erhalten. Elternzugriff
  richtet sich nach dem zentralen Konto und der Rolle, nicht nach der alten
  PIN-Entsperrung. Ein Integrationstest prüft ausdrücklich ein altes aktives PIN-Flag.
- **Demo-Modus:** Der integrierte Testserver verweigert die Kombination mit Demo-Modus,
  statt Schreibzugriffe still durch alte Demo-Schutzregeln blockieren zu lassen.
- **Setup:** Im integrierten Betrieb meldet der Setup-Status eine fertig eingerichtete
  Installation. Der öffentliche Legacy-Setup-Endpunkt und Demo-Login sind nicht
  eingebunden. Eine zweite Familie entsteht nicht durch den alten Setup-Assistenten.
- **Alte MCP-Zugänge:** Legacy-Service-Token und frei gesetzte Parent-ID authentifizieren
  den neuen Testserver nicht. Lesezugriffe verwenden zentrale, familiengebundene
  Tokens. MCP-Schreiben ist bis zum integrierten Deduplication-Gateway gesperrt.
- **Bilder:** Avatare, Gerichtebilder und Fotos verwenden requestbezogene
  Familienverzeichnisse. API-Antworten werden nicht zwischen Anmeldungen gecacht.
  Ein Test verwendet absichtlich denselben Avatar-Dateinamen in zwei Familien.
- **Browser-Caches:** Erfolgreicher Login, Setup/Demo-Login und Logout verwerfen
  vorherige private Query-Daten. Alte Lob-/Abzugs-Animationsmarker werden entfernt,
  damit identische lokale Kinder-IDs einer anderen Familie keine neuen Ereignisse
  unterdrücken. Anzeigegröße, Sprache und Bilderrahmen-Geräteeinstellungen bleiben erhalten.
- **Passwortformular:** Nach erfolgreichem Passwortwechsel prüft die Oberfläche die
  Anmeldung erneut. Der zentrale Passwortwechsel widerruft die Sitzung; das alte
  lokale Passwort-Handling wird im integrierten Server nicht eingebunden.
- **Übernommene IDs:** Die Kopierhilfe erhält die lokale User-Zuordnung und richtet
  PostgreSQL-Sequenzen nach explizit kopierten IDs aus. Neue Konten kollidieren
  dadurch nicht mit kopierten IDs. Diese Hilfe ist weiterhin nur für geprüfte
  Restore-Testkopien vorgesehen, nicht für einen automatischen Produktivlauf.
- **Reservierte Datenbanken:** Der Family-Router lehnt insbesondere `famquest_auth`,
  leere oder überlange technische Namen ab. Auth-Daten können nicht versehentlich
  als Familien-Datenbank ausgewählt werden.

## Bewusst erhaltene Kompatibilität

Die aktuelle Hauptnavigation enthält weiterhin die vereinbarten Alltags- und
Verwaltungsbereiche. Frühere Kalender-, Essensplan- und Einkaufsseiten werden
auf die Startseite umgeleitet. Fotos sind kein primärer Verwaltungstab; ein
bestehender direkter Foto-/Bilderrahmenzugang und vorhandene Bilddaten bleiben
erhalten. Ein gespeicherter Bilderrahmen-Timeout ist weiterhin eine lokale,
optionale Geräteeinstellung und wurde nicht ungefragt gelöscht.

Ohne Google-Zugangsdaten gibt es keinen Google-Abgleich. Im Legacy-Server ist
`CALENDAR_SYNC_MINUTES` jedoch standardmäßig 5; derselbe Hintergrundpfad bearbeitet
auch Schulferien. Der Wert 0 schaltet den automatischen Kalenderlauf ab. Aus diesen
Code-Defaults lässt sich die tatsächliche NAS-Einstellung nicht ableiten.

## Noch offene Integrationsgrenzen

Konten-/Mitgliedsbearbeitung mit zentralem Login, Google-Neuanbindung und MCP-
Schreibtransport sind im neuen Testserver ausdrücklich gesperrt, solange ihre
zentralen Transaktions-/OAuth-/Wiederholungswege fehlen. Das sind bekannte
Release-Blocker und keine versteckten alten Einstellungen. Vor Produktivbetrieb
folgen außerdem per-family Hintergrundjobs, Provisionierungs-/Restore-Probelauf
und Freigabe der konkreten QNAP-Umstellung.
