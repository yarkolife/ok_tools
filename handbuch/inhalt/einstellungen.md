Dieses Kapitel ist für Administratorinnen und Administratoren. Es erklärt alle
Einstellungen, die OK-Tools im Browser anbietet: wo sie stehen, was jedes Feld
bewirkt und welche Werte sich bewährt haben. Was nur der Server-Betreuer in der
Datei `.env` einstellen kann, steht am Ende.

[TOC]

## 1. Wo die Einstellungen sind {#ueberblick}

Menü: *Einstellungen & Stammdaten → Konfiguration*. Die Seite zeigt eine Kachel
pro Einstellungsformular; ein Klick öffnet das Formular direkt.

![Die Seite „Konfiguration“ mit einer Kachel pro Formular](bilder/e01-konfiguration.jpg "Konfiguration: jede Kachel öffnet ein Formular.")

- **Nur aktive Module erscheinen.** Ist ein Modul auf diesem Server
  ausgeschaltet (zum Beispiel Ausleihe oder Austausch), fehlen seine Kachel und
  sein Abschnitt in diesem Kapitel gilt hier nicht.
- **Wer sie sieht.** Superuser sehen alle Formulare. Andere Mitarbeitende sehen
  nur Formulare, für die ihnen die Rechte „anzeigen“ oder „ändern“ gegeben
  wurden. Die Benachrichtigungseinstellungen sind nur für Superuser.
- **Jedes Formular gibt es einmal.** Es gibt keine Liste und kein „Hinzufügen“:
  Man ändert immer dieselben Einstellungen und speichert unten rechts mit
  **Speichern** oder **Sichern und weiter bearbeiten**. Über **Geschichte**
  oben rechts sieht man, wer wann etwas geändert hat.
- Unten in der Seitenleiste steht die installierte Version, z. B.
  „OK-Tools 4.73.0 · d0594f9“. Sie hilft bei Rückfragen an den Support.

## 2. Was für alle Formulare gilt {#grundsaetze}

**Pflichtfelder** sind mit einem roten Stern markiert. Fehlt etwas, bleibt das
Formular offen und das Feld wird rot markiert.

**Passwörter, API-Schlüssel und Zugriffstoken** werden nie wieder angezeigt.
Das Feld bleibt leer, darunter steht „Ein Wert ist gespeichert“.

- Feld leer lassen und speichern: Der gespeicherte Wert bleibt.
- Neuen Wert eintragen und speichern: Er ersetzt den alten.

**Pfade** wie `/mnt/nas/Mediathek` sind Pfade auf dem Server, so wie OK-Tools
sie sieht, nicht Laufwerksbuchstaben am eigenen PC. Welche Ordner es gibt, weiß
der Server-Betreuer.

**Speicherort oder Pfad.** Viele Formulare bieten beides: eine Auswahl unter den
*Speicherorten* (Menü *Archiv & Medien → Speicherorte*) und darunter ein
Pfadfeld. Ist ein Speicherort gewählt, gilt er, und das Pfadfeld wird nur als
Ersatz benutzt. Speicherorte sind besser: Ihr Zustand wird überwacht, und eine
Änderung am Speicherort wirkt überall.

**Zeitpläne.** Wann etwas automatisch läuft (Scans, Synchronisierung, Backups),
steht nicht in diesen Formularen, sondern unter *System → Periodische
Aufgaben* (siehe [Abschnitt 13](#system)).

!!! hinweis ""
    Eine Einstellung wirkt ab dem Speichern. Läuft gerade eine Aufgabe (ein
    Export, ein Scan), arbeitet sie mit den alten Werten zu Ende.

## 3. Organisation und Registrierung {#organisation}

### Organisationskonfiguration {#organisation-daten}

Name, Logos und Kontaktdaten des Kanals. Sie erscheinen in der Seitenleiste,
auf Formularen, in E-Mails und in den Austausch-Metadaten.

![Organisationskonfiguration mit Name, Kurzname, Beschreibung und Logos](bilder/e02-organisation.jpg "Organisationskonfiguration: Grundinformationen.")

| Bereich | Felder | Wirkung |
|---|---|---|
| Grundinformationen | Organisationsname, Kurzname, Beschreibung | Voller Name auf Formularen und in E-Mails; Kurzname dort, wo wenig Platz ist; die Beschreibung ist ein Begrüßungstext. |
| | Großes Logo, Kleines Logo | Großes Logo für die ausgeklappte Seitenleiste, kleines (quadratisch oder SVG) für die eingeklappte. Hochladen mit dem Pfeil rechts, „Löschen“ entfernt das Logo. |
| Kontaktinformationen | Webseite, E-Mail, Telefon, Fax, Adresse, Öffnungszeiten | Erscheinen auf Formularen und in E-Mails an Nutzende. Adresse und Öffnungszeiten sind mehrzeilig. |
| Regulierung & Trägerschaft | Landesmedienanstalt, Träger, Bundesland | Kürzel der Landesmedienanstalt (z. B. MSA) und des Trägers; das Bundesland wird in die Austausch-Metadaten geschrieben. |
| Sendeplan | Sendestart, Sendeende | Standard-Sendezeit eines Tages in der Planung. |
| Integration | PeerTube-Kanal | Kennung des eigenen PeerTube-Kanals. |
| Rechtstexte | Datenschutzerklärung, Impressum, AGB | Optional. Eine eigene Datenschutzerklärung ersetzt den Standardtext auf der Datenschutzseite der Registrierung. Impressum und AGB werden gespeichert, aber derzeit auf keiner Seite angezeigt. |

### Registrierungskonfiguration {#registrierung}

| Feld | Wirkung |
|---|---|
| Registrierungsformular-Typ | Ob das Anmeldeformular als PDF, HTML oder Text erzeugt wird. |
| Registrierungsformular-PDF | Dateiname der PDF-Vorlage im Ordner `files/` auf dem Server. Eine neue Vorlage legt der Server-Betreuer dort ab. |

## 4. Ausleihe {#ausleihe}

Menü-Kachel *Ausleih-Konfiguration*. Gilt für Ausleihe, Rückgabe, Erinnerungen
und den Etikettendrucker.

### Genehmigung {#ausleihe-genehmigung}

| Feld | Wirkung |
|---|---|
| Nutzeranfrage erfordert Genehmigung | An: Anfragen, die Nutzende selbst stellen, müssen per E-Mail-Link genehmigt werden, bevor sie gelten. |
| Basis-URL der Website | Adresse, mit der die Links in den Genehmigungs-E-Mails beginnen, z. B. `https://portal.okmq.de`. Muss die echte Adresse des Servers sein, sonst führen die Links ins Leere. |
| URL-Vorlage für Ausleihanfragen | Link zur Anfrage für Nutzende; `{rental_id}` wird durch die Nummer ersetzt. |
| E-Mail-Adressen für Genehmigungsbenachrichtigungen | Wer die Genehmigungs-Mails bekommt, durch Komma getrennt. Leer: alle Mitarbeitenden. |
| Maximales Alter des Genehmigungs-Tokens | Wie lange ein Genehmigen- oder Ablehnen-Link gilt, in Sekunden. 604800 = 7 Tage. |

### Erinnerungen, Fotos, Scannen {#ausleihe-erinnerungen}

| Feld | Wirkung |
|---|---|
| Automatische Rückgabe-Erinnerungen | An: Nutzende bekommen vor dem Rückgabetermin eine E-Mail. |
| Erinnerungsstunden vor Rückgabe | Wie viele Stunden vorher, Standard 24. |
| Erinnerung an fehlendes Material (Tage) | Fehlt nach der Rückgabe Verbrauchsmaterial, wird die Person alle so viele Tage erinnert. 0 = nie. |
| Artikelfotos anzeigen, Raumfotos anzeigen | Fotos in der Ausleihe und auf dem Dashboard. Die Inventarfotos selbst kommen aus den Inventar-Foto-Einstellungen ([Abschnitt 5](#inventar)). |
| Signalton beim Scannen | Kurzer Ton bei gelungenem oder fehlgeschlagenem Scan. Standardmäßig aus, weil es am Tresen sonst laut wird. |

### Etikettendrucker {#ausleihe-drucker}

Ein Netzwerk-Etikettendrucker mit TSPL (z. B. TSC TE210). Ist eine Adresse
eingetragen, schickt OK-Tools Rollenetiketten direkt an ihn. Leer: Etiketten
werden nur über den Browser gedruckt.

![Abschnitt Etikettendrucker der Ausleih-Konfiguration](bilder/e03-ausleihe-etikettendrucker.jpg "Etikettendrucker: Adresse, Auflösung, Abstand, Schwärzung und Versatz.")

| Feld | Wirkung |
|---|---|
| Etikettendrucker-Adresse, -Port | IP-Adresse oder Name des Druckers im Netz; Port meist 9100. |
| Auflösung | 203 oder 300 dpi, steht auf dem Typenschild des Druckers. |
| Etikettenabstand (mm) | Abstand zwischen zwei Etiketten auf der Rolle. **Nachmessen:** Ein falscher Wert lässt den Drucker über das nächste Etikett hinausfahren. |
| Schwärzung | 0 bis 15. Höher, wenn die Balken grau bleiben; niedriger, wenn sie verlaufen. |
| Druckgeschwindigkeit | Zoll pro Sekunde; langsamer druckt sauberer. |
| Horizontaler / Oberer Versatz (mm) | Verschiebt den Druck nach rechts bzw. nach unten, wenn er nicht mittig sitzt. |

Die Etikettengrößen selbst stehen unter *Etikettenformate*
([Abschnitt 12](#stammdaten)).

### Arbeitszeiten und Organisationszugriff {#ausleihe-zeiten}

**Arbeitszeiten:** Öffnungs- und Schließzeit pro Wochentag. Abholung und
Rückgabe einer Ausleihe müssen in diese Zeiten fallen. Beide Felder eines Tages leer lassen, wenn
an diesem Tag geschlossen ist.

**Organisationszugriff:** Technik welcher Eigentümer (Organisationen im
Inventar) jede Nutzerart ausleihen kann: Nutzende, Mitglieder, Mitarbeitende
und „Nur-Ausleihe“. Eine leere Liste bedeutet: Es gelten die Standardorganisationen
dieser Nutzerart.

## 5. Inventar-Fotos {#inventar}

Kachel *Inventar-Foto-Einstellungen*.

| Feld | Wirkung |
|---|---|
| Aktiviert | Fotos von Inventarartikeln werden gesucht und angezeigt. |
| Media-Files-Speicherort | Ordner mit den Fotos als Speicherort; geht vor dem Fotoordner darunter. |
| Fotoordner | Pfad, unter dem es **einen Unterordner pro Inventarnummer** gibt, z. B. `/mnt/inventar/OK-001136/`. |
| Unterstützte Bildformate | Dateiendungen, die als Foto gelten. |
| Vorschaubilder neben den Originalen speichern | An: Vorschaubilder landen im Unterordner `.thumbnails` neben den Fotos (Ordner muss beschreibbar sein). Aus: Sie liegen auf dem Server von OK-Tools. |

Unter dem Formular zeigt **Aufgelöster Fotoordner**, welchen Ordner OK-Tools
gerade tatsächlich benutzt und ob es ihn gibt.

## 6. Freistellungen {#freistellungen}

Kachel *Freistellungen-Konfiguration*.

| Feld | Wirkung |
|---|---|
| Status-E-Mails senden | E-Mails an Nutzende über den Stand ihres Videos (hochgeladen, geplant, Sendezeiten). |
| Benachrichtigungen an (Medienanstalten) | Status-E-Mails nur an Nutzende dieser Medienanstalten. Leer: an alle. So bleiben Mails auf den eigenen Kanal beschränkt. |
| Download-Speicherpfad | Wohin Videos aus Nextcloud geladen werden. |
| Nextcloud-Dateien automatisch herunterladen | Ein nach Nextcloud hochgeladenes Video wird ohne Klick heruntergeladen. |
| VideoFile beim Nextcloud-Download anlegen | Nach dem Download erscheint das Video sofort mit Player in der Freistellungsliste. Der Download-Pfad muss dafür in einem Speicherort liegen. |
| Bildschirm-Board-Dauer | Wie lange ein Eintrag auf dem Bildschirm-Board steht, in Sekunden. |
| Ort im Freistellungsformular | Ortsname für „Ort, Datum“ auf dem gedruckten Formular. |

## 7. Mediendateien {#mediendateien}

Kachel *Mediendateien-Konfiguration*.

**Kopieren und Speicher**

| Feld | Wirkung |
|---|---|
| Automatisch kopieren bei Planung | Beim Speichern eines Sendeplans werden die Videos kopiert, und zwar ins Archiv und/oder ins Playout, je nach den zwei Schaltern darunter. |
| Wöchentliche Ordner verwenden | Im Playout-Speicher wird pro Woche ein Ordner `JJJJ_KW_WW` angelegt. |
| Archiv geschützt | Dateien im Archiv-Speicher können nicht gelöscht werden. **Anlassen.** |
| Automatisches Löschen aus Custom | Nach dem Kopieren wird das Video aus dem Eingangsspeicher (Typ „Custom“) gelöscht. |
| Benutzerdefinierte Tage für Quellpräferenz | So lange gilt eine Datei im Eingangsspeicher als die aktuelle Fassung. |
| Standard-Playout-Speichername / -pfad | Leer lassen: wird automatisch erkannt. |
| Prüfsumme beim Kopieren verifizieren | Jede Kopie wird mit SHA256 geprüft; für Archivquellen geht mit „MD5 für Archiv“ das schnellere MD5. |
| Unterstützte Videoformate | Dateiendungen, die als Video erkannt werden. |

**Umwandeln und Rendern**

| Feld | Wirkung |
|---|---|
| Overlay-Rendering aktiviert | Text-Overlays auf Videos. |
| HEVC automatisch transkodieren | H.265-Videos werden in H.264 umgewandelt, damit Browser sie abspielen. |
| Encoding-Preset für Umwandlung, Render-Encoding-Preset | Welches Preset (Auflösung, Bitrate) beim Umwandeln bzw. bei „Video rendern“ gilt, z. B. `1080p25_9000k`. Die Presets stehen unter *Video-Kodierungspresets*. |

**Cover**

| Feld | Wirkung |
|---|---|
| Cover-Generierung aktiviert | Cover-Bilder werden aus einem Videobild, den Angaben der Freistellung und dem Logo erzeugt. |
| Cover-Logo / Cover-Logo-Pfad | Logo als PNG mit Transparenz hochladen; der Pfad ist nur die Alternative. Leer: mitgeliefertes Logo. |
| Schriftart Titel / Fließtext | Pfad zu einer `.ttf`-Schrift; leer: Roboto. |
| Cover-Kategoriefarben | Akzentfarbe je Kategorie, z. B. `{"Magazin": "#E6007E"}`. |
| Cover-Vorlagenregeln | Vorlage je Kategorie: `base`, `journal` oder `trailer`, z. B. `{"Trailer": "trailer"}`. |
| Cover-Speicherort, -Unterordner, -Ausgabeverzeichnis | Wohin die Cover geschrieben werden; der Speicherort geht vor dem manuellen Pfad. |

## 8. Planung {#planung}

Kachel *Planungskonfiguration*.

**Playout-Import und Sendeplan.** Die Aktion *Plan!* schickt die Angaben der
geplanten Videos und den Tagesplan an das Playout.

| Feld | Wirkung |
|---|---|
| Playout-Import-URL, API-Schlüssel, Zeitüberschreitung | Adresse und Schlüssel des Playout-Servers für die Video-Angaben. |
| Playout-URL für fehlende Metadaten | Wo das Playout Dateien ohne Angaben meldet; leer: Import-URL mit `/missing`. |
| Periodische Prüfung auf fehlende Metadaten, Prüfintervall, Seitengröße | OK-Tools fragt regelmäßig nach Dateien, die noch Angaben brauchen. |
| Playout-Sendeplan-URL | Wohin der Tagesplan geschickt wird. |

**Programm-Mail.** Empfänger und Texte der wöchentlichen Programm-Mail (Menü
*Weitere → Programm-Mail*).

| Feld | Wirkung |
|---|---|
| Empfänger, BCC | Eine Adresse pro Zeile. BCC für Verteiler, damit niemand die anderen Adressen sieht. |
| Absender, Antwort an | Leer: Standardabsender des Servers bzw. die Person, die sendet. |
| Betreff, Betreff bei Änderungen | Platzhalter `{von}`, `{bis}`, `{name}`; bei Änderungen zusätzlich `{betreff}`. Text ohne Platzhalter wie „ÄNDERUNG: “ wird vor den normalen Betreff gesetzt. |
| Text vor / nach dem Programm, Text bei Änderung | Das Programm steht zwischen dem Text davor und danach. `{name}` ist die sendende Person. |

**Anchor-Render.** Erzeugt aus einem geplanten Tag eine Programmvorschau.
URL, API-Schlüssel und Timeout des Renderers; Länge des Clips je Beitrag;
Dateiname (`{number}`, `{date}`) und Zielordner im Playout; Platzhaltervideo
und Regeln für Beiträge ohne Video (z. B. Live-Sendungen).

!!! hinweis ""
    Planung, Anchor und Reel-Studio sprechen mit Servern im Sendenetz. Adressen
    und Schlüssel bekommt man vom Betreuer des Playouts.

## 9. Austausch {#austausch}

Kachel *Austausch-Konfiguration*.

| Bereich | Wirkung |
|---|---|
| Nextcloud-Einstellungen | Adresse, Benutzer und App-Passwort des Dienstkontos, mit dem OK-Tools die Austauschordner liest. |
| Ordner-Muster | Wie Kanal- und Austauschordner heißen; `{channel}` wird durch den Kanalnamen ersetzt. |
| Synchronisierung | Wie viele Tage zurück und wie viele Datumsordner durchsucht werden; in welchen Nextcloud-Ordnern Kanäle liegen; welche Kanäle synchronisiert bzw. übersprungen werden; welche Kanäle wie das eigene Bundesland behandelt werden. Den Zeitplan steuert die periodische Aufgabe `sync_exchange_folders`. |
| Speicher | Speicherort für importierte Dateien; leer: wird automatisch angelegt. |
| Auto-Import | Importierte Beiträge kommen automatisch in die PeerTube-Warteschlange. |
| Export zum Server | Ziel des Exports (Nextcloud oder Netzwerkfreigabe), Pfade, Windows-Pfad für `files.txt`, Standard-Medienanstalt, Ordner mit unsignierten Freistellungen, Vorschaubilder. |
| Absicherung des Exports | Schutz vor einem hängenden Speicher: Kopieren in Stücken, Abbruch bei Stillstand, Aufräumen alter `.tmp_`-Dateien, Ersatzquelle, kein doppelter Export. **Standardwerte lassen**, außer Exporte brechen oft ab. |

In der Tabelle **Kanal-Zugänge** unten im Formular stehen pro Kanal die Adresse
und der Token der OK-Tools-Schnittstelle anderer Kanäle.

## 10. Werkzeuge, Reel-Studio und Instagram {#werkzeuge}

Kachel *Werkzeuge-Konfiguration*.

| Bereich | Wirkung |
|---|---|
| Lager | Wo hochgeladene und erzeugte Dateien der Werkzeuge liegen; maximale Upload-Größe in MB. |
| Erlaubte Formate | Dateiendungen für Bilder, Videos und Audio. |
| FFmpeg | Pfade zu `ffmpeg` und `ffprobe`; nur ändern, wenn der Server-Betreuer es sagt. |
| Audio-Normalisierung | Ein- und Ausgabeordner, Standard-Preset und Bitrate, Modell für die Rauschentfernung. |

### Reel-Studio {#reel-studio}

Das Reel-Studio erscheint nur, wenn **Reel-Studio aktiviert** an ist **und**
URL und API-Schlüssel eingetragen sind.

![Abschnitt Reel-Studio mit Schalter, URL und leerem Feld für den API-Schlüssel](bilder/e05-werkzeuge-reel-studio.jpg "Reel-Studio: Der gespeicherte API-Schlüssel wird nicht angezeigt.")

| Feld | Wirkung |
|---|---|
| Reel-Render-URL, API-Schlüssel, Timeout | Adresse und Schlüssel des Renderers. Timeout großzügig lassen (360 s). |
| Ausgabedateinamen-Muster | Vorschlag für den Dateinamen, mit `{number}` und `{date}`. |
| Mediathek-Zeile 1 und 2 | Standardtext der Mediathek-Plakette im Reel. |
| Ausgabespeicher, Unterverzeichnis | Wohin fertige Reels geschrieben werden. |
| Tägliche Reel-Erinnerung, Empfänger, Uhrzeit | Morgens eine E-Mail mit den Reels des Tages. Zur selben Uhrzeit werden freigegebene Instagram-Posts veröffentlicht. |

### Instagram {#instagram}

Erscheint erst, wenn das Reel-Studio eingerichtet ist.

| Feld | Wirkung |
|---|---|
| Instagram-Posting aktiviert | Für jedes Reel wird ein Post-Entwurf angelegt; freigegebene Posts werden zur Uhrzeit der Reel-Erinnerung veröffentlicht. Aus: Es bleibt bei der E-Mail mit Download-Link. |
| Instagram-API, Version | Instagram-Login (`graph.instagram.com`, Token gilt 60 Tage und wird automatisch erneuert) oder Facebook-Login. |
| Konto-ID, Zugriffstoken | Aus der Meta-App des Kontos. Der Token wird nie angezeigt; „Token erneuert am“ zeigt die letzte Erneuerung. |
| Bildunterschrift (Vorlage) | Platzhalter `{titel}`, `{untertitel}`, `{beschreibung}`, `{autor}`, `{sendetermin}`, `{uhrzeit}`, `{mediathek}`, `{hashtags}`. Zeilen, deren Platzhalter leer sind, entfallen. |
| Auch im Feed zeigen | Aus: Das Reel erscheint nur im Reels-Tab. |
| Verbindung | **Verbindung testen** prüft Konto-ID und Token bei Instagram, ohne etwas zu veröffentlichen. |

## 11. Benachrichtigungen {#benachrichtigungen}

**Benachrichtigungs-Konfiguration** (Kachel): Hauptschalter für alle
Benachrichtigungen, Uhrzeit der Tagesübersicht und wie viele Tage alte
Ereignisse aufbewahrt werden (Standard 90).

**Benachrichtigungseinstellungen** (Kachel, nur Superuser): Jede automatische
Prüfung lässt sich einzeln ausschalten und einstellen.

![Benachrichtigungseinstellungen mit Prüfungen nach Modul und ihren Parametern](bilder/e04-benachrichtigungen.jpg "Benachrichtigungseinstellungen: links die Prüfung, rechts ihre Parameter.")

- **Häkchen weg:** Die Prüfung läuft gar nicht und ist für niemanden sichtbar.
  Ausschalten, was der Kanal nicht macht.
- **Parameter** rechts: Fristen in Tagen oder Stunden, Vorlauf vor der
  Sendung, Grenzwert für freien Speicherplatz, beobachtete Speicherorte.
- Unten **Speichern**; die Änderung gilt ab der nächsten Prüfung.

Wer welche Benachrichtigungen bekommt, wählt jede Person selbst unter *Meine
Abonnements*. Admins sehen und ändern alle Abos unter
*Benachrichtigungsabonnements*. *Benachrichtigungs-Ausblendungen* listet
Einträge, bei denen jemand „nicht mehr melden“ gewählt hat; einen Eintrag
löschen, damit er wieder gemeldet wird.

## 12. Stammdaten {#stammdaten}

Listen, die in Auswahlfeldern anderer Seiten erscheinen. Neue Einträge über
**Hinzufügen** oben rechts in der jeweiligen Liste.

| Menüpunkt | Wofür | Hinweis |
|---|---|---|
| Kategorien (Freistellungen) | Kategorien von Beiträgen | Die „Numerische ID“ wird beim Import aus anderen Systemen gebraucht. |
| Jugendschutz-Sendezeitfenster | Wann Beiträge einer Jugendschutzkategorie laufen dürfen | „Fenster erzwingen“ aus: zu jeder Zeit erlaubt. Eine Endzeit vor der Startzeit reicht über Mitternacht (22:00 bis 06:00). |
| Etikettenformate | Etikettengrößen im Druckdialog | Breite, Höhe, Abstand; der „Schlüssel“ steht in Druck-Links und sollte nicht geändert werden. |
| Kategorien (Inventar) | Kategorien von Inventarartikeln | |
| Inventarnummernkreis | Präfix und Stellenzahl der Inventarnummern, z. B. `OK-` mit 6 Stellen | Inaktive Nummernkreise werden beim Import abgelehnt. |
| Projektkategorien, Zielgruppen | Auswahl in Projekten | |
| Video-Kodierungspresets | Auflösung, Bildrate, Codec und Bitrate zum Umwandeln und Rendern | Der Name (z. B. `1080p25_9000k`) wird in den Mediendateien-Einstellungen eingetragen. |
| Video-Presets, Preset-Overlays | Intro, Outro und Text-Einblendungen für das Overlay-Rendering | Nur nötig, wenn Overlay-Rendering genutzt wird. |
| Instagram-Partner | Partner, deren Konten bei passenden Reels als Collab eingeladen werden | Nur sichtbar, wenn Instagram-Posting an ist. Stichwörter werden in Titel und Beschreibung gesucht; Konten ohne @. |

## 13. System und was nur der Server-Betreuer einstellt {#system}

**Periodische Aufgaben** (*System → Periodische Aufgaben*, nur Superuser):
Hier stehen Zeitpläne der automatischen Aufgaben, z. B. `run_backup_db`
(Datenbank-Backup), `sync_exchange_folders` (Austausch), `auto_scan`
(Speicher-Scan), `send_return_reminders` (Rückgabe-Erinnerungen). Eine Aufgabe
lässt sich dort aus- und einschalten oder ihr Zeitplan ändern.

!!! warnung ""
    Das Backup (`run_backup_db`) nicht ausschalten. Läuft eine Aufgabe nicht,
    meldet das die Benachrichtigung „Hintergrundaufgaben schlagen fehl“.

**Benutzer und Rechte** stehen unter *Nutzer & Projekte*. Nur Konten, die als
Mitarbeitende markiert sind, können die Verwaltung öffnen; was sie dort dürfen,
legen Gruppen und Einzelrechte fest.

**Nicht im Browser einstellbar** (Datei `.env` auf dem Server, Änderung durch
den Server-Betreuer und Neustart):

- welche Module aktiv sind (Ausleihe, Inventar, Austausch, Planung …),
- Domain und HTTPS, Mail-Server und Standardabsender,
- Datenbank, Backup-Ziel, Zugangsdaten zu Diensten des Servers,
- Einbindung von Netzwerkordnern (`/mnt/...`).

## 14. Häufige Fragen {#fragen}

**Eine Kachel fehlt auf der Konfigurationsseite.**
Das Modul ist auf diesem Server ausgeschaltet, oder dem eigenen Konto fehlt
das Recht dafür.

**Ich sehe den API-Schlüssel nicht mehr. Ist er weg?**
Nein. Steht unter dem Feld „Ein Wert ist gespeichert“, ist er da; er wird nur
nicht angezeigt. Leer speichern behält ihn.

**Die Links in den Genehmigungs-E-Mails führen ins Leere.**
In der Ausleih-Konfiguration stimmt die *Basis-URL der Website* nicht mit der
Adresse des Servers überein.

**Der Etikettendrucker druckt über das Etikett hinaus.**
*Etikettenabstand* auf der Rolle nachmessen und eintragen; bei schiefem Druck
die Versatz-Felder anpassen.

**Benachrichtigungen kommen für Dinge, die wir nicht machen.**
In den Benachrichtigungseinstellungen die Prüfung ausschalten. Einzelne
Einträge lassen sich in der Benachrichtigung selbst mit „nicht mehr melden“
ausblenden.
