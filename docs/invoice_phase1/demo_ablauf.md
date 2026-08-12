# Deutscher Demo-Ablauf

## Ziel

Die Demo zeigt DigiTax Flow 1a: synthetische Factur-X-/ZUGFeRD-Rechnungen
werden ueber n8n an die Phase-1-API uebergeben. Die API wendet ein
versioniertes Kontrollprofil an und erzeugt einen erklaerbaren Kontrollbericht
fuer die menschliche Pruefung. Die Demo endet vor Freigabe, Buchung und
Zahlung. Flow 1b bleibt als inaktiver PDF-OCR-/LLM-Entwurf sichtbar.

## Start

Docker Desktop muss laufen. In PowerShell in das Repository wechseln und den
isolierten Praesentationsstack starten:

```powershell
cd "C:\Users\Tyto\Desktop\diss\ResearchAssistant\work\repos\facturx_apis_standard_correction"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\examples\n8n\scripts\Manage-Phase1UploadDemo.ps1" -Action Start
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\examples\n8n\scripts\Manage-Phase1UploadDemo.ps1" -Action Status
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\examples\n8n\scripts\Manage-Phase1UploadDemo.ps1" -Action SmokeTest
```

Der Entwicklerstack `compose.dev.yml` darf nicht gleichzeitig laufen, weil
beide Stacks die Ports `6970` und `5679` verwenden.

## Mock-Rechnungen erzeugen

```powershell
python .\examples\demo\generate_demo_invoices.py --output-dir .\.demo-output
```

Optional prueft der Matrix-Test alle sieben Faelle ueber den realen n8n-Pfad:

```powershell
.\examples\n8n\scripts\Test-Phase1DemoMatrix.ps1
```

Erwartete Abschlussmeldung: `All 7 generated demo cases passed through n8n.`

## Oberflaechen

- Batch-Demo: <http://localhost:6970/demo/batch>
- n8n: <http://localhost:5679>
- API-Dokumentation: <http://localhost:6970/docs>

## Vorfuehrung

1. Im X-Batch die vier Dateien `.demo-output\demo_invoice_*_unternehmen_x.pdf`
   auswaehlen und **Run X batch** starten.
2. Im Y-Batch die drei Dateien `.demo-output\demo_invoice_*_unternehmen_y.pdf`
   auswaehlen und **Run Y batch** starten.
3. In der Ergebnistabelle Kontrollprofil, Status, Routing, Finding-Anzahl und
   Kategorien erklaeren.
4. Einen Fall mit `CAL-003` oder mehreren Abweichungen oeffnen, um Reason Code,
   Sollwert, Istwert, Differenz und Toleranz zu zeigen.
5. Die Ergebnistabelle mit **Export to Excel** exportieren.
6. **Run paired profile comparison** ausfuehren: Bei X ist `ORG-002` nicht
   aktiv; bei Y erkennt dieselbe zusaetzliche Lieferantenkontrolle den nicht
   freigegebenen Lieferanten.
7. Optional **Generate and run X batch** zeigen. Der Generator ist aktuell
   deterministisch und templatebasiert, nicht LLM-basiert.
8. In n8n Flow 1a zeigen. Flow 1b darf kurz als inaktiver Entwurf gezeigt,
   aber nicht aktiviert oder als fertig bezeichnet werden.

## Erwartete Faelle

| Fall | Erwarteter Status | Wesentlicher Befund |
|---|---|---|
| X gueltig | `unauffaellig` | gemeinsame Basiskontrollen bestanden |
| X Lieferantenkennung fehlt | `klaerung_erforderlich` | `FRM-003` und Schematron-Befunde |
| X Zahlbetrag falsch | `klaerung_erforderlich` | `BR-CO-16` und `CAL-003` |
| X Vergleichslieferant | `unauffaellig` | `ORG-002` im Starterprofil nicht aktiv |
| Y gueltig | `unauffaellig` | Basis plus `ORG-002` bestanden |
| Y Lieferant nicht freigegeben | `klaerung_erforderlich` | `ORG-002 / SUPPLIER_NOT_APPROVED` |
| Y mehrere Abweichungen | `klaerung_erforderlich` | mehrere Kontrollfamilien betroffen |

## Aussage und Grenze

Die Demo zeigt automatisierte Vorpruefung, versionierte Regeln,
unternehmensspezifische Kontrollprofile, nachvollziehbare Evidenz und Routing
zur menschlichen Pruefung. Sie genehmigt, bucht oder bezahlt keine Rechnung
und kontaktiert keinen Lieferanten.

## Beenden

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\examples\n8n\scripts\Manage-Phase1UploadDemo.ps1" -Action Stop
```

`Stop` erhaelt das dedizierte n8n-Volume und die importierten Workflows.
`Reset -Confirm` ist kein normaler Beenden-Befehl; es loescht das Demo-Volume
und ist nur fuer einen bewusst gewuenschten Neuaufbau bestimmt.
