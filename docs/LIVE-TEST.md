# Erster Live-Test

Dieser Stand ist die Grundlage fuer den Familientest. `main` ist der Live-Branch;
`develop` bleibt fuer weitere Entwicklung, insbesondere Geld und Bankanbindung.
Eine Bankanbindung ist in diesem Stand nicht enthalten.

Der Umfang der ersten stabilen Familienversion (#16–#23), die Levelmigration und
die Abnahmeschritte stehen in [STABLE-1.md](STABLE-1.md). Dort ist auch der neue,
ausschließlich lesende Konsistenzbericht beschrieben.

## Aktuelles Verhalten

- Anmeldung und Berechtigungen sind kontobasiert. Kinder sehen ihre eigenen Aufgaben,
  Punkte und Kinderbelohnungen; Eltern verwalten die Familie.
- Einstellungen enthalten Profil, Familie, Aufgaben, Haushalt und Belohnungen.
  Die feste Kopfzeile fuehrt zur Startseite zurueck.
- Haushaltsaufgaben werden einmal gepflegt und koennen fuer bestimmte Kinder freigegeben
  werden. Wiederholbare Aufgaben erlauben getrennte Erledigungen am selben Tag.
- Erwachsene erhalten die eingestellten XP beim Erledigen. Kindererledigungen werden
  durch Eltern bestaetigt. Rueckgaengigmachen hebt die zugehoerige Gutschrift auf.
- Belohnungen fuer Kinder und Eltern sind getrennt. Eltern koennen Einloesungen mit
  Begruendung stornieren; die ausgegebenen Sterne werden einmalig zurueckgebucht.
- Bei mehreren Tageszeiten entstehen eigenstaendige Routinen. Bestehende doppelte
  Aufgaben werden nicht anhand ihres Namens automatisch zusammengefuehrt oder geloescht.

## Vor und nach einem Update

Vor jedem Update Datenbank, Uploads, Compose-Konfiguration und bisheriges Image sichern.
Den Docker-Build ausdruecklich mit `--target runtime` ausfuehren. Nach dem Start muessen
Migration, Container-Healthcheck und `/api/health` erfolgreich sein.

Im Familientest Anmeldung als Elternteil und Kind, Tag/Woche, wiederholte Haushaltserledigung,
Kinderfreigabe sowie Einloesung und Stornierung einer Belohnung ausprobieren. Dabei die
Punktestaende und den Verlauf abgleichen. Schmale Hochformatansichten mitpruefen.

Eine Rueckkehr nach Datenbankmigrationen braucht ein zusammenpassendes Datenbankbackup
und Image; ein altes Image allein setzt eine Migration nicht zurueck.

## Dokumentationsstand

Die umfangreichen README-Dateien und Screenshots enthalten noch Beschreibungen der
urspruenglichen Anwendung (zum Beispiel Eltern-PIN und alte Menuepunkte). Fuer diesen
Familienzweig gilt die Beschreibung oben. Die Ueberarbeitung dieser historischen
Anleitungen kann unabhaengig vom Familientest erfolgen.
