# Familie anlegen mit vorbereitetem Datenbankplatz

Unter `/operator` können Betreiber eine neue Familie mit einem eigenen Elternzugang
anlegen. Die Oberfläche zeigt die Anzahl freier Plätze. Jeder Platz ist eine **eigene,
vorher ausdrücklich vorbereitete PostgreSQL-Datenbank mit eigener Rolle**. Die Web-App
erhält weder Superuser- noch CREATE DATABASE-/CREATEROLE-Rechte. Es gibt kein unbegrenztes
automatisches Datenbank-Provisionieren über HTTP.

## Geplanter Staging-Updateablauf

Keine der folgenden NAS-Aktionen wurde durch Codex ausgeführt. Vor Ausführung Freigabe
für Benutzer-DB-Migration und zusätzliche leere Datenbanken einholen. Zuerst aktuelle
Compose-Datei und zentrale Benutzer-DB sichern; vorhandene Sicherungen behalten.

1. Nur die App der zentralen Testanwendung stoppen. Datenbank und Gateway weiterlaufen lassen.
2. Mit dem geprüften neuen Image, bestehender `runtime.env` und internem Staging-Datennetz
   die additive Auth-Migration `h20261102_creation` nach `g20261101_status` anwenden:

   ```text
   python -m app.operator_setup --apply-reviewed-creation-migration
   ```

   Sie ergänzt nur `family_creations` für Reservierung und Einrichtungsnachweis. Vorhandene
   Identitäten, Statusprotokolle und Familien-Datenbanken werden nicht verändert.
3. In einem **separaten einmaligen Hilfscontainer**, nicht in der laufenden Web-App,
   den bisherigen Staging-Konfigurationsordner privat nach `/stage-config` einbinden.
   Der Helper benötigt Schreibzugriff auf diesen Ordner und das interne Staging-Datennetz:

   ```text
   python -m app.family_slots --config-dir /stage-config
   ```

   Der Hilfscontainer kann als UID 0 laufen, damit er die privaten Konfigurationsdateien
   lesen/sichern kann. Er verwendet die ausschließlich dort gelesenen Staging-DB-Owner-
   Zugangsdaten aus `bootstrap.env`. Die Web-App erhält diese Zugangsdaten weiterhin nicht.

   Der Helper verweigert andere Hosts/Owner, ungeprüfte/teilweise vorhandene Cluster,
   abweichende Konfigurationen und vorhandene Backup-Dateien. Er erstellt exklusiv
   `runtime.env.before-family-create` und `bootstrap.env.before-family-create`, dann genau
   `famquest_stage_c` und `famquest_stage_d` mit unabhängigen Zufallskennwörtern. Ausschließlich
   diese **neuen leeren** Datenbanken werden migriert und auf leere Tabellen geprüft.

   Anschließend ergänzt er die beiden bestehenden privaten `.env`-Dateien um die neuen
   Rollen und `FAMILY_CREATION_DATABASES`. Die bisherigen A/B-Kennwörter und Einstellungen
   bleiben erhalten. Konfigurationsdateien werden mit privaten Berechtigungen ersetzt;
   weder alte noch neue Geheimnisse werden ausgegeben. Eine Wiederholung nach komplettem
   Erfolg prüft nur, ohne Datenbanken oder Kennwörter neu zu erzeugen.

   Bei Teilfehlern wird nichts gelöscht oder automatisch repariert. Vor einem erneuten
   Versuch Protokolle, Datenbank-/Rolleninventar und beide Konfigurationsdateien prüfen.
   Nicht auf Verdacht `.env`-Backups, Rollen oder Volumes löschen.
4. In der bestehenden Test-Compose beide App-Image-Verweise aktualisieren. Funktionierende
   Netzwerke, Dateipfade und Volumes behalten; Gateway und App zusammen neu starten.
5. Mit dem bestehenden Betreiberzugang anmelden. Nun sind zwei freie Plätze sichtbar.
   Keine neuen Betreiber- oder A/B-Kennwortdateien erzeugen.

Neue leere Staging-Pakete können die zwei Plätze schon beim ausdrücklich isolierten Erststart
vorbereiten. `--spare-families 0` lässt sie zunächst weg, damit CI den nachträglichen Helper prüft.

## Bedienablauf

- „Familie anlegen“ öffnen, Familienname und Name/E-Mail des Elternteils eingeben.
- Ein neues unabhängiges Anfangspasswort (16–128 Zeichen) zweimal eingeben, Sprache und
  Zeitzone wählen und die Anlage ausdrücklich bestätigen. Die tatsächliche Kennworteingabe
  erfolgt durch den Nutzer; das Passwort wird danach nicht wieder angezeigt.
- Die neue Familie erhält nur die Rolle `parent`, niemals Betreiberrechte. Zunächst gibt es
  ein Familienmitglied; Kinder und weitere Mitglieder werden im eigenen Familienbereich ergänzt.
- Nach Erfolg kann sich der Elternzugang an der normalen Familienanmeldung anmelden.
  Es wird keine E-Mail versendet; Einladungs-/Passwort-zurücksetzen-Flows fehlen noch.

## Fehler- und Wiederholungsverhalten

Der Einrichtungsauftrag reserviert Platz, Familienregistrierung und neue Identität zuerst.
Vor jeder Befüllung wird der Schema-Stand geprüft und jede Fachdatentabelle ohne Lesen
privater Inhalte auf vorhandene Zeilen geprüft. Belegte/unerwartete Datenbanken werden
verweigert, nicht geleert. Vorhandene E-Mail-Adressen werden nicht übernommen oder hochgestuft.

Die lokale Familienbefüllung nutzt ausschließlich die vorbereitete Familienrolle. Erst nach
erfolgreicher Befüllung werden Familienmitgliedschaft, lokaler Akteur und aktiver Status
zentral gemeinsam gespeichert. Der lokale Login-Hash bleibt `!`; die Kennwortprüfung liegt
ausschließlich in der zentralen Benutzer-DB.

Teilfehler bleiben als `failed` bzw. nach Prozessabbruch als `provisioning` sichtbar. Der Platz
bleibt reserviert. Wiederholung desselben Request-Schlüssels liefert den ursprünglichen Auftrag;
sie befüllt nicht erneut und ändert niemals das ursprüngliche Passwort. Abweichende öffentliche
Auftragsdaten mit demselben Schlüssel werden abgewiesen. Keine automatische Wiederaufnahme,
Löschung, Freigabe oder Wiederverwendung teilbefüllter Plätze. Manuelle Reparatur ist ein
weiterer explizit zu prüfender Schritt.

Der Betreiber sieht die letzten 20 Einrichtungsaufträge mit Status, Elternadresse und
auslösendem Betreiber. Klartextpasswörter werden weder dort noch im Auftragsdatensatz gespeichert.
Die zentrale Identität speichert nur den bestehenden Argon2-Kennworthash.

Zwei Plätze bedeuten zwei neue Familien ohne weitere Infrastrukturänderung; danach ist
erneute ausdrücklich vorbereitete Kapazität nötig. Familienlöschung, Wiederherstellung
einschließlich Bildern und Bestandsmigration realer Familien sind weiterhin offen.
