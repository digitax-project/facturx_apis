# DigiTax-Demo: automatisierte Rechnungsvorpruefung

## Was wird gezeigt?

Flow 1a verarbeitet synthetische Factur-X-/ZUGFeRD-Rechnungen als PDF mit
eingebettetem XML. Das System prueft das strukturierte Format, ausgewaehlte
Rechnungsinhalte und die zum Unternehmen gehoerenden Stammdaten. Das Ergebnis
ist ein erklaerbarer Kontrollbericht fuer die menschliche Pruefung. Es erfolgt
keine automatische Freigabe, Buchung oder Zahlung.

Start und Bedienung sind in [demo_ablauf.md](demo_ablauf.md) beschrieben. Die
vollstaendige Profilmatrix steht in
[demo_profile_matrix.md](demo_profile_matrix.md).

## Unternehmensprofile

- Unternehmen X verwendet das Starterprofil `inbound-starter-de-v1` mit 16
  ausgewaehlten DigiTax-Kontrollen.
- Unternehmen Y verwendet `inbound-operating-de-v1` mit allen 17 Kontrollen.
  Es prueft mit `ORG-002` zusaetzlich freigegebene Lieferantenstammdaten.

Die gemeinsame technische und fachliche Basis bleibt gleich. Das Profil legt
fest, welche zusaetzlichen organisatorischen Kontrollen fuer ein Unternehmen
ausgefuehrt werden.

## Implementierte Kontrollkategorien

| Kategorie | Kontrollen | Gegenstand |
|---|---|---|
| Dokument | `DOC-001`, `DOC-007` | Lesbarkeit, Unterstuetzung und belastbare Extraktion |
| Struktur | `STR-003`, `STR-004` | EN16931-XSD und offizielle Schematron-Regeln |
| Form | `FRM-001` bis `FRM-007` | erforderliche Rechnungsangaben |
| Berechnung | `CAL-001` bis `CAL-004` | Positionen, Steuer, Zahlbetrag und Waehrung |
| Organisation | `ORG-001`, `ORG-002` | Rechnungsempfaenger und freigegebene Lieferanten |

Der aktuell implementierte Katalog enthaelt 17 DigiTax-Kontrollen. Der groessere
Kandidatenkatalog in [control_catalog.md](control_catalog.md) dokumentiert auch
Kontrollen, die noch nicht implementiert oder keinem Profil zugeordnet sind.

## Was bedeuten die 427 Schematron-Assertions?

`STR-004` ist eine DigiTax-Kontrolle und kapselt den
Factur-X-1.09-/EN16931-Schematron-Regelsatz. Der verwendete Stand enthaelt 427
ausfuehrbare Einzelpruefungen: 424 blockierende Assertions und drei Warnungen.
Sie sind keine 427 zusaetzlichen Profilkontrollen. Das Profil waehlt `STR-004`,
und die API fuehrt darunter den gesamten Regelsatz aus. Regel-ID, Erklaerung und
XML-Fundstelle bleiben im Kontrollbericht erhalten. `STR-003` prueft dagegen
primaer XML-Struktur und Datentypen ueber das XSD.

## Was zeigt der Profilvergleich?

Der Profilvergleich erzeugt zwei Rechnungen mit gleichem Lieferanten, gleicher
Leistung und gleichen Betraegen. Empfaengerspezifische Angaben unterscheiden
sich, weil jede Rechnung ihren tatsaechlichen Empfaenger nennen muss.

- Bei Unternehmen X ist `ORG-002` nicht ausgewaehlt; der Vergleichsfall bleibt
  `unauffaellig`.
- Bei Unternehmen Y gleicht `ORG-002` den Lieferanten mit der Freigabeliste ab
  und erzeugt `klaerung_erforderlich / prioritized_review`.

Die Aussage lautet nicht, dass eine Rechnung universell richtig und die andere
falsch ist. Verfuegbare Stammdaten und das versionierte Kontrollprofil bestimmen
die zusaetzlich erkennbaren Abweichungen.

## Flow 1b, DigiTax Risk Review und Flow 2

Flow 1b soll normale PDF-Rechnungen per OCR/LLM erfassen und danach denselben
kanonischen Datenrahmen, dieselben Kontroll-IDs und dieselbe Ergebnisstruktur
wie Flow 1a verwenden. Er bleibt aktuell ein inaktiver Entwurf.

DigiTax Risk Review, vormals unter dem Prototypnamen Reqeli gefuehrt, soll
zwischen technischem Kontrollbericht und operativem Anwender liegen. Der Dienst
kann Befunde erklaeren, priorisieren und Handlungsoptionen vorschlagen, trifft
aber keine abschliessende Rechnungsentscheidung.

Flow 2 soll anschliessend Human-in-the-Loop orchestrieren: Kontrollbericht
zuweisen, Rueckfragen oder Nachweise einholen, eine Entscheidung dokumentieren
und den Vorgang an die folgenden Prozessschritte uebergeben.
