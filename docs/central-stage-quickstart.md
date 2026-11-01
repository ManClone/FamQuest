# FamQuest: getrennter Zwei-Familien-Test

Dieses Paket startet eine neue, isolierte Testanwendung für **@@ORIGIN@@**.
Die bisherige Einfamilien-Testinstanz auf 11901 und produktive Daten bleiben erhalten.
Es werden weder vorhandene Familien übernommen noch Sicherungen zurückgespielt.

## Was bereits testbar ist

Zentrale Anmeldung mit separater Benutzer-Datenbank, zwei getrennte Familien-Datenbanken,
Eltern-/Kinderrechte, Kontenverwaltung innerhalb der eigenen Familie, getrennte Fach- und
Bildzugriffe sowie Sperrung einer Familie auch bei bereits bestehender Anmeldung.

**Eine globale Superadmin-Weboberfläche ist noch nicht implementiert.** Die vier Zugänge
sind Eltern- und Kinderzugänge zweier Testfamilien, keine Betreiber-Administratoren.
Familien anlegen, sperren oder löschen ist daher noch kein fertiger Web-Verwaltungsablauf.
Die automatisierte Sperrprüfung erfolgt ausschließlich im neu angelegten isolierten Testcluster.

## Vorbereitung auf QNAP

1. Paket in einen **neuen** Ordner `@@DIR@@` kopieren. Vorhandene `.env`-Dateien und
   FamQuest-Daten nicht hinein kopieren. Dieses Paket enthält private neue Testkennwörter;
   nicht ins Git-Repository oder in einen öffentlichen Chat hochladen.
2. In Container Station eine **zusätzliche** Anwendung `famquest-central-stage` aus
   `compose.yml` erstellen. Die dortigen absoluten Dateipfade beziehen sich auf den Ordner
   aus Schritt 1. Bei anderem Zielordner nur die Dateipfade entsprechend anpassen.
3. Beim ersten Start wird ein eigener PostgreSQL-Server mit den Volumes
   `famquest-central-stage-db-v1` und `famquest-central-stage-uploads-v1` verwendet.
   `central-stage-init` legt Benutzer-DB und Testfamilien A/B an und beendet sich danach
   erfolgreich. Das ist beabsichtigt. Anschließend startet die Anwendung.
4. QNAP-Reverse-Proxy einrichten: **HTTPS für den Host aus @@ORIGIN@@**, gültiges Zertifikat,
   Ziel **HTTP 127.0.0.1:11902**. Den ursprünglichen Hostnamen weiterreichen. Der lokale
   Gateway nimmt nur diesen Host an; Datenbank und App haben keine veröffentlichten Ports.
5. Erst dann **@@ORIGIN@@** öffnen. Den lokalen Port nicht als normale LAN-HTTP-Anmeldeseite
   verwenden. Die zentrale Anmeldung setzt geschützte HTTPS-Sitzungscookies.
6. Die vier getrennten Zugangsdaten stehen lokal in `TESTZUGAENGE-PRIVAT.txt`.
   Bestehende Papa-/Kinderkennwörter der bisherigen Testinstanz werden nicht übernommen.

Der App-Prozess vertraut ausschließlich der aufgelösten Adresse seines privaten Gateways,
nicht beliebigen weitergereichten Headern. Gateway und Anwendung zusammen neu starten,
wenn Container neu erstellt wurden. Der PostgreSQL-Superuser steht nur dem einmaligen
Initialisierungscontainer zur Verfügung, nicht der laufenden App.

## Abnahme im Browser

- Mit Eltern A anmelden: nur „Testfamilie A“, „Eltern A“ und „Kind A“ sichtbar.
- Eine eindeutig benannte Aufgabe oder Hausarbeit anlegen; anschließend abmelden.
- Mit Eltern B anmelden: A-Aufgabe darf nicht sichtbar sein. B besitzt eigene Daten.
- Mit Kind A anmelden: nur eigene Aufgaben; kein Zugriff auf Elternverwaltung.
- Wechsel zwischen A und B: keine alten Namen, Bilder oder Buchungen aus der anderen Familie.
- Zwei unterschiedliche Browserprofile für parallele Logins verwenden. Normale Tabs im
  selben Profil teilen sich die Anmeldung.
- Gesamte neue Staging-Anwendung neu starten: Testfamilien und Zuordnungen bleiben erhalten.

Die automatische Container-Prüfung testet zusätzlich direkte PostgreSQL-Abschottung,
Header-Manipulation, Sperrung bestehender Sitzungen, CSRF, Abmeldung und erneuten Start.
Sie ersetzt noch keine Prüfung des externen Zertifikats, DNS oder deines QNAP-Reverse-Proxys.

## Schutz vor unbeabsichtigter Änderung

Die Initialisierung läuft nur im ausdrücklich bezeichneten isolierten Cluster. Sie verweigert
fremde oder teilweise vorhandene Datenbanken und Rollen. Nach erfolgreichem Erststart wird
bei Wiederholung nur geprüft; Kennwörter, Familien und Daten werden nicht neu erzeugt.
Fehlt nach einem Teilfehler die Abschlussmarkierung, bricht der nächste Start ab. Keine Volumes
auf Verdacht löschen; zuerst die Staging-Protokolle prüfen. Ein abweichender Datenbankstand
oder geänderter Ursprung wird nicht automatisch migriert bzw. überschrieben.

Das App-Image ist festgelegt auf:

`@@IMAGE@@`

Die echte Wiederherstellungsprobe mit Bildern, Bestandsmigration, Provisionierung realer
Familien und globale Superadmin-Oberfläche bleiben weitere Arbeitsschritte. Dieses Paket
erteilt keine produktive Mehrfamilien-Freigabe.
