Dieses Kapitel beschreibt den ganzen Weg eines Geräts: vom Eintragen ins Inventar über das Etikett
bis zur Ausleihe und Rückgabe. Die Bildschirmfotos zeigen Beispieldaten („Max Mustermann“,
„Videokamera Sony PXW-Z90 (Demo)“).

[TOC]

## 1. Begriffe {#begriffe}

| Begriff | Bedeutung |
|---|---|
| **Inventarartikel** | Ein Eintrag im Inventar mit einer **Inventarnummer** (z. B. `OK-001136`). Gleiche Geräte werden unter *einer* Nummer geführt. |
| **Gerät** | Ein einzelnes Stück eines Inventarartikels mit eigener **Seriennummer**, eigenem Status und eigenen Prüfungen. Zwei gleiche Kameras = ein Inventarartikel mit zwei Geräten. |
| **Menge** | Anzahl der Geräte auf Lager. Sie wird aus den Geräten automatisch berechnet. |
| **Standort** | Wo das Gerät liegt, z. B. *Ausleihe → Schrank 1 → Fach A*. |
| **Eigentümer** | Wem das Gerät gehört: dem OK, der MSA, einem Projekt, einer Spende … |
| **Für Verleih verfügbar** | Nur so markierte Artikel erscheinen in der Ausleihe. |
| **Verbrauchsmaterial** | Kleinteile, die nicht im Inventar stehen (Akkus, Kabel, SD-Karten). Sie werden pro Ausleihe notiert und bei der Rückgabe abgehakt. |

## 2. Neues Gerät ins Inventar aufnehmen {#inventar}

**Menü:** *Tagesgeschäft → Inventarartikel* → **+** (oben rechts).

![Formular Neuer Inventarartikel](bilder/a01-neuer-inventarartikel.jpg "Das leere Formular. Die Inventarnummer ist schon vorgeschlagen.")

### 2.1 Grunddaten {#inventar-grunddaten}

1. **Inventarnummer** – wird automatisch vorgeschlagen (nächste freie Nummer der Serie `OK-`). Nur ändern, wenn das Gerät schon eine Nummer hat.
2. **Beschreibung** – so, wie das Gerät in der Ausleihe heißen soll, z. B. *Videokamera Sony PXW-Z90*. Bei Sets: was dazugehört.
3. **Hersteller** und **Kategorie** aus der Liste wählen. Fehlt ein Eintrag, über die Schaltfläche **⋮** neben dem Feld einen neuen anlegen.
4. **Standort** wählen (siehe [2.3](#inventar-standort)).
5. **Für Verleih verfügbar** einschalten, wenn das Gerät ausgeliehen werden darf.
6. **Barcode-Etikett aufgeklebt** erst einschalten, wenn das Etikett wirklich klebt (siehe [Kapitel 3](#etikett)).

### 2.2 Geräte und Seriennummern {#inventar-geraete}

In der Tabelle **Geräte** wird jedes einzelne Stück mit seiner **Seriennummer** eingetragen. Für jedes weitere
gleiche Gerät **„Gerät hinzufügen“** klicken – es bleibt dieselbe Inventarnummer, nur die Seriennummer ist
verschieden. Kaufdatum, Kaufpreis und Notiz sind optional.

![Ausgefülltes Formular mit zwei Geräten](bilder/a02-inventarartikel-ausgefuellt.jpg "Zwei gleiche Kameras unter einer Inventarnummer, je mit eigener Seriennummer.")

!!! hinweis ""
    Hat ein Gerät keine Seriennummer, das Feld leer lassen – es wird dann als „Gerät 1“, „Gerät 2“ … geführt.
    Die **Menge** muss nicht eingetragen werden: Sobald Geräte erfasst sind, zählt OK-Tools die Geräte auf Lager selbst.
    Weiter unten lassen sich **Prüfungen** (z. B. DGUV) je Gerät eintragen.

### 2.3 Standort festlegen {#inventar-standort}

Standorte sind verschachtelt: *Raum → Schrank/Regal → Fach*. Das Gerät bekommt den genauesten Platz, an dem es
zurückgelegt wird. Neue Standorte werden unter *Ausleihe & Inventar → Standorte* angelegt; im Feld
**Übergeordnet** steht der Schrank oder Raum, in dem der neue Platz liegt.

![Liste der Standorte](bilder/a08-standorte.jpg "Standorte mit vollem Pfad.")

### 2.4 Eigentümer {#inventar-eigentuemer}

Im Abschnitt **Eigentum & Reservierungen** den **Eigentümer** wählen:

- **OKMQ** (bzw. euer Kanal) – aus eigenen Mitteln gekauft,
- **MSA** – von der Medienanstalt Sachsen-Anhalt zur Verfügung gestellt,
- ein **Projekt**, eine **Spende** oder eine Dauerleihgabe.

Hat der Eigentümer eine eigene Inventarnummer (z. B. die MSA), diese unter **Inventarnummer des Eigentümers**
eintragen. Reservierte und verliehene Mengen rechnet OK-Tools selbst. Neue Eigentümer (z. B. ein neues Projekt)
werden unter *Ausleihe & Inventar → Organisationen* angelegt.

![Abschnitt Eigentum](bilder/a04-eigentuemer.jpg "Eigentümer und Inventarnummer des Eigentümers.")

### 2.5 Speichern {#inventar-speichern}

**„Sichern und weiter bearbeiten“** klicken. Die Menge zeigt jetzt die Zahl der Geräte (hier 2).

![Gespeicherter Inventarartikel](bilder/a03-inventarartikel-gespeichert.jpg "Gespeichert: Menge 2, Status „Auf Lager“.")

!!! hinweis ""
    **Fotos** werden nicht hochgeladen, sondern aus dem Inventar-Fotoordner gelesen: dort einen Unterordner mit der
    Inventarnummer anlegen (z. B. `OK-001136`), die Fotos hineinlegen und in der Liste die Aktion
    **„Fotos aus eingebundenem Ordner neu einlesen“** ausführen.

    **Ähnliche Artikel:** Die Aktion **„Ausgewählte Inventarartikel kopieren“** legt eine Kopie mit der nächsten
    freien Nummer an.

## 3. Etikett drucken und aufkleben {#etikett}

### 3.1 Drucken {#etikett-drucken}

1. In *Inventarartikel* den Artikel suchen und links **anhaken** (mehrere gleichzeitig sind möglich).
2. Unten die Aktion **„Barcodes drucken“** wählen und **Start** klicken.

![Aktion Barcodes drucken](bilder/a05-aktion-barcodes-drucken.jpg "Artikel angehakt, Aktion „Barcodes drucken“ gewählt.")

3. Format wählen – für den Etikettendrucker **Rollenetikett (51 × 25 mm)**. Die Vorschau zeigt Inventarnummer,
   Eigentümer, Barcode, Beschreibung und Standort.
4. **„An Etikettendrucker senden“** druckt direkt auf dem Etikettendrucker. **„Drucken“** öffnet den Druckdialog
   des Browsers (z. B. für A4-Bögen).

![Dialog Barcode-Etiketten](bilder/a06-etiketten-dialog.png "Format und Vorschau des Etiketts.")

!!! hinweis ""
    Ein Etikett gilt für den **Inventarartikel**. Bei mehreren gleichen Geräten unter einer Nummer bekommt jedes
    Gerät dasselbe Etikett – entsprechend oft drucken.

### 3.2 Aufkleben {#etikett-aufkleben}

- Auf eine **glatte, saubere Stelle**, die beim Benutzen **nicht abgerieben** wird und nicht stört – z. B. Unter-
  oder Rückseite, nicht auf Griffe, Tasten oder Lüftungsschlitze.
- Der Barcode muss für den Scanner **gut erreichbar** bleiben.
- Besteht ein Gerät aus **mehreren Teilen**, die getrennt werden können (Kamera, Netzteil, Ladegerät …),
  **jedes Teil bekleben**.
- Wird ein Gerät **dauerhaft in einer Tasche oder Kiste** aufbewahrt, auch die Kiste bekleben.

### 3.3 Als aufgeklebt markieren {#etikett-markieren}

Den Artikel in der Liste anhaken, Aktion **„Barcode-Etikett als aufgeklebt markieren“** → **Start**. In der Spalte
*Barcode-Etikett aufgeklebt* steht dann ein grüner Haken. Über den Filter *Barcode-Etikett aufgeklebt: Nein*
findet man jederzeit alle Geräte ohne Etikett.

![Etikett als aufgeklebt markiert](bilder/a07-etikett-aufgeklebt.jpg "Verfügbar für den Verleih und mit Etikett.")

## 4. Ausleihe – geführter Weg {#ausleihe}

**Menü:** *Tagesgeschäft → Ausleihprozess* (öffnet die Ausleihverwaltung, Modus **Geführt**). Der Assistent hat
vier Schritte.

### Schritt 1 – Nutzer {#ausleihe-nutzer}

Name, E-Mail oder Matrikelnummer eintippen und den Nutzer anklicken. Ist die Person noch nicht registriert, über
**„Neuer Nutzer“** anlegen. Hat die Person aus einer früheren Ausleihe noch etwas nicht zurückgebracht, steht das
rot unter dem Namen (*Fehlendes Material*) – gleich ansprechen.

![Schritt 1 Nutzer](bilder/b01-nutzer-waehlen.jpg)

### Schritt 2 – Zeitraum {#ausleihe-zeitraum}

**Abholung** und **Rückgabe bis** eintragen oder eine **Schnellauswahl** nehmen (*Heute/Morgen, Nachmittag,
Wochenende, Nächste 7 Tage*). Es gelten die Öffnungszeiten; Mitarbeitende können auch außerhalb buchen.

![Schritt 2 Zeitraum](bilder/b02-zeitraum.jpg)

### Schritt 3 – Artikel und Räume {#ausleihe-artikel}

Links nach Kategorie filtern oder oben suchen und mit **+** hinzufügen. Angezeigt wird, wie viele Stück im
gewählten Zeitraum frei sind (z. B. *2/2 verfügbar*). Bei mehreren Geräten unter einer Nummer die **Anzahl** oben
bei *Ausgewählte Artikel* einstellen. Über **Sets** lassen sich ganze Gerätesätze, über **Räume** Räume dazubuchen.

![Schritt 3 Artikel](bilder/b03-artikel-waehlen.jpg)

### Schritt 4 – Prüfen und bestätigen {#ausleihe-pruefen}

- **Projekt** (Pflicht) und **Zweck** eintragen.
- **Verbrauchsmaterial (nicht im Inventar):** alles, was zusätzlich mitgegeben wird – **eine Zeile pro Sache, die
  Zahl am Ende ist die Menge**:

        Akku NP-F970 - 2
        SD-Karte 64 GB - 2
        XLR-Kabel 5 m - 1

    Diese Liste wird bei der Rückgabe abgehakt. Was nicht zurückkommt, bleibt als *fehlend* sichtbar.

- **E-Mail-Benachrichtigung** anhaken, wenn der Nutzer eine Bestätigung bekommen soll.
- **„Bestätigen & senden“** klicken.

![Schritt 4 Prüfen und Verbrauchsmaterial](bilder/b04-pruefen-verbrauchsmaterial.jpg)

Die Ausleihe ist jetzt **reserviert**. Ihre Seite zeigt oben den Ablauf *Erstellt → Reserviert → Ausgegeben →
Zurückgegeben → Geschlossen*, rechts Nutzer, Zeitraum, Verbrauchsmaterial und die **interne Notiz**.

![Reservierte Ausleihe](bilder/b05-ausleihe-reserviert.jpg)

## 5. Ausgabe, wenn der Nutzer kommt {#ausgabe}

1. Die Ausleihe öffnen (*Alle Ausleihen* oder links *Heute fällig*).
2. Die Geräte mit dem Nutzer **durchgehen**: Sind alle Teile da, stimmen die Seriennummern, ist alles heil? Fehlt
   ein Kleinteil, unter *Verbrauchsmaterial* ergänzen; Auffälligkeiten in die **interne Notiz** schreiben und
   **„Notiz speichern“** klicken.
3. **„Unterschrift anfordern“** – der Nutzer unterschreibt:
    - **Hier zeichnen** – direkt auf dem Tablet oder Bildschirm,
    - **Mit Telefon unterschreiben** – QR-Code mit dem eigenen Handy scannen,
    - **Auf Papier unterschreiben** – Ausgabeschein drucken und von Hand unterschreiben lassen.

![Signaturmethode wählen](bilder/b06-signatur-methode.jpg)

![Unterschrift zeichnen](bilder/b07-unterschrift.jpg)

4. **„Als ausgegeben markieren“** und die Rückfrage bestätigen. Die Ausleihe steht jetzt auf **Ausgegeben**, mit
   dem Rückgabetermin.

![Ausgegebene Ausleihe](bilder/b08-ausgegeben.jpg "Ausgegeben und unterschrieben.")

!!! hinweis ""
    **Beleg drucken** (oben rechts) druckt den Ausgabeschein, **Packliste drucken** eine Liste zum Zusammenstellen.
    Über **Verlängern** wird der Rückgabetermin verschoben.

## 6. Ausleihe – schneller Weg mit dem Scanner {#schnell}

Für Ausleihen, die sofort mitgenommen werden. **Menü:** *Ausleihprozess*, oben rechts **„Schnell“**.

1. **Nutzer** suchen und auswählen.
2. **Abholung** und **Rückgabe bis** prüfen (vorbelegt).
3. In das Feld **Artikel scannen** klicken und die Etiketten der Geräte **nacheinander scannen**. Jedes Gerät
   erscheint sofort in der Liste; bei mehreren Geräten unter einer Nummer erhöht ein weiterer Scan die Anzahl
   (oder **+** / **−**).
4. **Verbrauchsmaterial** wie beim geführten Weg eintragen.

![Schnelle Ausleihe mit Scanner](bilder/c01-schnell-gescannt.jpg)

5. **„Jetzt ausgeben“** – die Ausleihe wird angelegt und sofort ausgegeben. Danach öffnet sich die Unterschrift
   (hier, per Telefon oder auf Papier).

![Unterschrift bei schneller Ausleihe](bilder/c02-schnell-signatur.jpg)

!!! hinweis ""
    Der Scanner arbeitet wie eine Tastatur: Er „tippt“ die Inventarnummer und drückt Enter. Ohne Scanner kann die
    Nummer auch von Hand eingegeben werden.

## 7. Rückgabe {#rueckgabe}

**Menü:** In der Ausleihverwaltung links **Rückgabe**. Alternativ auf der Seite der Ausleihe **„Rückgabe starten“**.

### 7.1 Ausleihe finden {#rueckgabe-finden}

1. Den Namen oder die E-Mail des Nutzers eintippen und **Suche** klicken (oder den Nutzer aus der Liste *Nutzer
   mit aktiven Ausleihen* wählen).
2. Bei der richtigen Ausleihe auf **Rückgabe** klicken.

![Nutzer für die Rückgabe suchen](bilder/d01-rueckgabe-nutzer-suchen.jpg)

![Aktive Ausleihen des Nutzers](bilder/d02-rueckgabe-aktive-ausleihen.jpg "Alle aktiven Ausleihen des Nutzers mit Zeitraum und Status.")

### 7.2 Normaler Weg: von Hand abhaken {#rueckgabe-normal}

Die Rückgabeseite zeigt oben das Scanfeld, darunter die Geräte, das Verbrauchsmaterial und die Optionen.

![Rückgabeseite](bilder/d03-rueckgabe-seite.jpg)

1. **Geräte:** jedes zurückgegebene Gerät links **anhaken** und den **Zustand** wählen:
    - **OK** – alles in Ordnung,
    - **Geringfügig** – kleiner Mangel,
    - **Schaden** – beschädigt. Es öffnet sich ein Feld für die Beschreibung; dort lässt sich auch festlegen, ob der
      Schaden dem Nutzer in Rechnung gestellt und ob das Gerät bis zur Prüfung aus dem Verleih genommen wird.

    Ist alles da und heil: **„Alles zurückgegeben, alles OK“** hakt alle Geräte auf einmal ab.

2. **Verbrauchsmaterial:** Kreis anklicken, wenn alles zurück ist; bei Teilmengen mit **–** / **+** die
   zurückgegebene Anzahl einstellen und im Feld daneben notieren, warum etwas fehlt.
3. Bei Bedarf eine **Rückgabenotiz (intern)** schreiben.
4. Optionen prüfen:
    - **Rückgabebeleg per E-Mail an Nutzer senden**,
    - **Ausleihe nach Rückgabe schließen** – schließt die Ausleihe sofort, wenn alle Geräte zurück sind,
    - **Für Inventarprüfung markieren** – legt für jedes zurückgegebene Gerät eine Prüfaufgabe an.
5. **„Rückgabe abschließen“** klicken.

![Rückgabe abgehakt](bilder/d04-rueckgabe-abgehakt.jpg "Kamera zurück (OK), Akkus und Kabel vollständig, eine SD-Karte fehlt noch – mit Begründung.")

### 7.3 Was fehlt, bleibt sichtbar {#rueckgabe-fehlend}

Nicht zurückgegebenes Verbrauchsmaterial bleibt als **fehlend** an der Ausleihe stehen („1 von 2 fehlen“), wird
links unter *Achtung → Fehlendes Material* gezählt und erscheint bei der nächsten Ausleihe derselben Person als
Hinweis. Kommt es später zurück, wird es auf der Seite der Ausleihe abgehakt; ist es endgültig weg, über
**„Abschreiben“**.

![Abgeschlossene Ausleihe mit fehlendem Material](bilder/d05-rueckgabe-abgeschlossen.jpg "Geschlossen, die fehlende SD-Karte bleibt rot markiert.")

### 7.4 Schneller Weg: mit dem Scanner {#rueckgabe-schnell}

1. Die Rückgabe der Ausleihe öffnen (wie in 7.1).
2. Der Cursor steht schon im Feld **Barcode scannen**: die Etiketten der Geräte **nacheinander scannen**. Jedes
   gescannte Gerät wird sofort als zurück gezählt („1/1 zurück“), ein Ton bestätigt den Scan. Gehört das Gerät
   nicht zu dieser Ausleihe, ertönt ein tiefer Ton und eine Meldung erscheint.
3. Wird kein Zustand gewählt, gilt das Gerät als **OK**. Nur bei Mängeln *Geringfügig* oder *Schaden* anklicken.
4. Verbrauchsmaterial abhaken und **„Rückgabe abschließen“** klicken.

![Rückgabe mit Scanner](bilder/d06-rueckgabe-gescannt.jpg "Nach dem Scan: Kamera „1/1 zurück“, Fortschritt 1/1.")

!!! hinweis ""
    Der Scan wird erst mit **„Rückgabe abschließen“** gespeichert. Wer die Seite vorher verlässt, verliert nichts –
    die Rückgabe kann einfach neu begonnen werden.

![Hinweis auf fehlendes Material aus anderen Ausleihen](bilder/d07-rueckgabe-fehlt-noch.jpg "Auch in anderen Ausleihen derselben Person erscheint der Hinweis „Fehlt noch aus anderen Ausleihen“.")

## 8. Häufige Fragen {#fragen}

**Ein Gerät taucht in der Ausleihe nicht auf.**
Prüfen, ob *Für Verleih verfügbar* eingeschaltet ist, ob der Status *Auf Lager* ist und ob es im Zeitraum nicht
schon verliehen oder reserviert ist.

**Zwei gleiche Mikrofone – eine Nummer oder zwei?**
Eine Inventarnummer, zwei Geräte mit je eigener Seriennummer ([2.2](#inventar-geraete)).

**Ein Gerät ist kaputt.**
Im Inventarartikel beim betroffenen Gerät den Status auf *Defekt* setzen. Es wird dann nicht mehr verliehen; die
Menge passt sich an.

**Wo sehe ich, was jemand nicht zurückgebracht hat?**
In der Ausleihverwaltung links unter *Achtung → Fehlendes Material* und *Überfällig*.
