# Factur-X 1.09 EN16931 Schematron rule inventory

This file is generated from the exact vendored compiled Schematron XSL.
Do not edit it manually; run `python tools/generate_schematron_rule_inventory.py`.

## Interpretation

- Assertion templates: `427`
- Unique technical `FX-SCH-A-*` IDs: `302`
- Assertions with an explicit standard-rule reference: `209`
- Additional profile/structure constraints without such a reference: `218`
- Severity: `424` blocking, `3` warning
- Source SHA-256: `ad17794b088dfb89a5e92c9e3b9a2f6663b95bd12b23677667e3e7996d1c4b1f`

The 427 entries are context-specific executable assertion templates, not
427 independent user-selectable DigiTax controls. `STR-004` executes the
artifact as a whole. This inventory is the basis for later grouping, mock
coverage, and control-profile decisions.

## Families

| Family | Assertion templates |
| --- | ---: |
| CII syntax rule | 4 |
| EN16931 VAT-category rule | 76 |
| EN16931 common rule | 24 |
| EN16931 decimal rule | 21 |
| EN16931 general rule | 80 |
| Factur-X extension rule | 3 |
| Factur-X profile/structure constraint | 218 |
| PEPPOL recommendation | 1 |

## Complete inventory

The JSON companion additionally contains the test and context XPath,
template mode, source line, and explicit null values.

| # | Technical ID | Standard reference | Severity | Family | Message |
| ---: | --- | --- | --- | --- | --- |
| 1 | FX-SCH-A-000372 | PEPPOL-EN16931-R008 | warning | PEPPOL recommendation | [PEPPOL-EN16931-R008]-Document MUST not contain empty elements. (still status warning) |
| 2 | FX-SCH-A-000280 | BR-52 | blocking | EN16931 general rule | [BR-52]-Each Additional supporting document (BG-24) shall contain a Supporting document reference (BT-122). |
| 3 | FX-SCH-A-000047 | BR-45 | blocking | EN16931 general rule | [BR-45]-Each VAT breakdown (BG-23) shall have a VAT category taxable amount (BT-116). |
| 4 | FX-SCH-A-000048 | BR-46 | blocking | EN16931 general rule | [BR-46]-Each VAT breakdown (BG-23) shall have a VAT category tax amount (BT-117). |
| 5 | FX-SCH-A-000049 | BR-47 | blocking | EN16931 general rule | [BR-47]-Each VAT breakdown (BG-23) shall be defined through a VAT category code (BT-118). |
| 6 | FX-SCH-A-000050 | BR-48 | blocking | EN16931 general rule | [BR-48]-Each VAT breakdown (BG-23) shall have a VAT category rate (BT-119), except if the Invoice is not subject to VAT. |
| 7 | FX-SCH-A-000051 | BR-CO-03 | blocking | EN16931 common rule | [BR-CO-03]-Value added tax point date (BT-7) and Value added tax point date code (BT-8) are mutually exclusive. |
| 8 | FX-SCH-A-000052 | BR-CO-17 | blocking | EN16931 common rule | [BR-CO-17]-VAT category tax amount (BT-117) = VAT category taxable amount (BT-116) x (VAT category rate (BT-119) / 100), rounded to two decimals. |
| 9 | FX-SCH-A-000053 | BR-DEC-19 | blocking | EN16931 decimal rule | [BR-DEC-19]-The allowed maximum number of decimals for the VAT category taxable amount (BT-116) is 2. |
| 10 | FX-SCH-A-000054 | BR-DEC-20 | blocking | EN16931 decimal rule | [BR-DEC-20]-The allowed maximum number of decimals for the VAT category tax amount (BT-117) is 2. |
| 11 | FX-SCH-A-000197 | BR-Z-08 | blocking | EN16931 VAT-category rule | [BR-Z-08]-In a VAT breakdown (BG-23) where VAT category code (BT-118) is "Zero rated" the VAT category taxable amount (BT-116) shall equal the sum of Invoice line net amount (BT-131) minus the sum of Document level allowance amounts (BT-92) plus the sum of Document level charge amounts (BT-99) where the VAT category codes (BT-151, BT-95, BT-102) are "Zero rated". |
| 12 | FX-SCH-A-000055 | BR-Z-09 | blocking | EN16931 VAT-category rule | [BR-Z-09]-The VAT category tax amount (BT-117) in a VAT breakdown (BG-23) where VAT category code (BT-118) is "Zero rated" shall equal 0 (zero). |
| 13 | FX-SCH-A-000056 | BR-Z-10 | blocking | EN16931 VAT-category rule | [BR-Z-10]-A VAT Breakdown (BG-23) with VAT Category code (BT-118) "Zero rated" shall not have a VAT exemption reason code (BT-121) or VAT exemption reason text (BT-120). |
| 14 | FX-SCH-A-000057 | BR-S-09 | blocking | EN16931 VAT-category rule | [BR-S-09]-The VAT category tax amount (BT-117) in a VAT breakdown (BG-23) where VAT category code (BT-118) is "Standard rated" shall equal the VAT category taxable amount (BT-116) multiplied by the VAT category rate (BT-119). |
| 15 | FX-SCH-A-000058 | BR-S-10 | blocking | EN16931 VAT-category rule | [BR-S-10]-A VAT Breakdown (BG-23) with VAT Category code (BT-118) "Standard rate" shall not have a VAT exemption reason code (BT-121) or VAT exemption reason text (BT-120). |
| 16 | FX-SCH-A-000198 | BR-S-08 | blocking | EN16931 VAT-category rule | [BR-S-08]-For each different value of VAT category rate (BT-119) where the VAT category code (BT-118) is "Standard rated", the VAT category taxable amount (BT-116) in a VAT breakdown (BG-23) shall equal the sum of Invoice line net amounts (BT-131) plus the sum of document level charge amounts (BT-99) minus the sum of document level allowance amounts (BT-92) where the VAT category code (BT-151, BT-102, BT-95) is "Standard rated" and the VAT rate (BT-152, BT-103, BT-96) equals the VAT category rate (BT-119). |
| 17 | FX-SCH-A-000399 | BR-FXEXT-Z-08rev | warning | Factur-X extension rule | [BR-FXEXT-Z-08rev] - With Exemption reason EN16931_2026 - In a VAT breakdown (BG-23) where VAT category code (BT-118) is equal to “Z” ("Zero Rated"), Absolute Value of (VAT category taxable amount (BT-116) - ∑ Invoice line net amounts (BT-131) + Σ Document level allowance amounts (BT-92) - Σ Document level charge amounts (BT-99) - Σ Logistics Service fee amounts (BT-X-272)) <= 0,01 * ((Number of line net amounts (BT-131) + Number of Document level allowance amounts (BT-92) + Number of Document level charge amounts (BT-99) + Number of Logistics Service fee amounts (BT-X-272)), where the VAT category code (BT-151, BT-95, BT-102, BT-X-273) is "Zero Rated" (Z). |
| 18 | FX-SCH-A-000059 | BR-29 | blocking | EN16931 general rule | [BR-29]-If both Invoicing period start date (BT-73) and Invoicing period end date (BT-74) are given then the Invoicing period end date (BT-74) shall be later or equal to the Invoicing period start date (BT-73). |
| 19 | FX-SCH-A-000060 | BR-CO-19 | blocking | EN16931 common rule | [BR-CO-19]-If Invoicing period (BG-14) is used, the Invoicing period start date (BT-73) or the Invoicing period end date (BT-74) shall be filled, or both. |
| 20 | FX-SCH-A-000061 | BR-31 | blocking | EN16931 general rule | [BR-31]-Each Document level allowance (BG-20) shall have a Document level allowance amount (BT-92). |
| 21 | FX-SCH-A-000062 | BR-32 | blocking | EN16931 general rule | [BR-32]-Each Document level allowance (BG-20) shall have a Document level allowance VAT category code (BT-95). |
| 22 | FX-SCH-A-000063 | BR-33 | blocking | EN16931 general rule | [BR-33]-Each Document level allowance (BG-20) shall have a Document level allowance reason (BT-97) or a Document level allowance reason code (BT-98). |
| 23 | FX-SCH-A-000064 | BR-CO-05 | blocking | EN16931 common rule | [BR-CO-05]-Document level allowance reason code (BT-98) and Document level allowance reason (BT-97) shall indicate the same type of allowance. |
| 24 | FX-SCH-A-000065 | BR-CO-21 | blocking | EN16931 common rule | [BR-CO-21]-Each Document level allowance (BG-20) shall contain a Document level allowance reason (BT-97) or a Document level allowance reason code (BT-98), or both. |
| 25 | FX-SCH-A-000066 | BR-DEC-01 | blocking | EN16931 decimal rule | [BR-DEC-01]-The allowed maximum number of decimals for the Document level allowance amount (BT-92) is 2. |
| 26 | FX-SCH-A-000067 | BR-DEC-02 | blocking | EN16931 decimal rule | [BR-DEC-02]-The allowed maximum number of decimals for the Document level allowance base amount (BT-93) is 2. |
| 27 | FX-SCH-A-000068 | BR-36 | blocking | EN16931 general rule | [BR-36]-Each Document level charge (BG-21) shall have a Document level charge amount (BT-99). |
| 28 | FX-SCH-A-000069 | BR-37 | blocking | EN16931 general rule | [BR-37]-Each Document level charge (BG-21) shall have a Document level charge VAT category code (BT-102). |
| 29 | FX-SCH-A-000070 | BR-38 | blocking | EN16931 general rule | [BR-38]-Each Document level charge (BG-21) shall have a Document level charge reason (BT-104) or a Document level charge reason code (BT-105). |
| 30 | FX-SCH-A-000071 | BR-CO-06 | blocking | EN16931 common rule | [BR-CO-06]-Document level charge reason code (BT-105) and Document level charge reason (BT-104) shall indicate the same type of charge. |
| 31 | FX-SCH-A-000072 | BR-CO-22 | blocking | EN16931 common rule | [BR-CO-22]-Each Document level charge (BG-21) shall contain a Document level charge reason (BT-104) or a Document level charge reason code (BT-105), or both. |
| 32 | FX-SCH-A-000073 | BR-DEC-05 | blocking | EN16931 decimal rule | [BR-DEC-05]-The allowed maximum number of decimals for the Document level charge amount (BT-99) is 2. |
| 33 | FX-SCH-A-000074 | BR-DEC-06 | blocking | EN16931 decimal rule | [BR-DEC-06]-The allowed maximum number of decimals for the Document level charge base amount (BT-100) is 2. |
| 34 | FX-SCH-A-000199 | BR-54 | blocking | EN16931 general rule | [BR-54]-Each Item attribute (BG-32) shall contain an Item attribute name (BT-160) and an Item attribute value (BT-161). |
| 35 | FX-SCH-A-000281 | BR-51 | blocking | EN16931 general rule | [BR-51]-In accordance with card payments security standards an invoice should never include a full card primary account number (BT-87). At the moment PCI Security Standards Council has defined that the first 6 digits and last 4 digits are the maximum number of digits to be shown. |
| 36 | FX-SCH-A-000200 | BR-21 | blocking | EN16931 general rule | [BR-21]-Each Invoice line (BG-25) shall have an Invoice line identifier (BT-126). |
| 37 | FX-SCH-A-000201 | BR-22 | blocking | EN16931 general rule | [BR-22]-Each Invoice line (BG-25) shall have an Invoiced quantity (BT-129). |
| 38 | FX-SCH-A-000202 | BR-23 | blocking | EN16931 general rule | [BR-23]-An Invoice line (BG-25) shall have an Invoiced quantity unit of measure code (BT-130). |
| 39 | FX-SCH-A-000203 | BR-24 | blocking | EN16931 general rule | [BR-24]-Each Invoice line (BG-25) shall have an Invoice line net amount (BT-131). |
| 40 | FX-SCH-A-000204 | BR-25 | blocking | EN16931 general rule | [BR-25]-Each Invoice line (BG-25) shall contain the Item name (BT-153). |
| 41 | FX-SCH-A-000205 | BR-26 | blocking | EN16931 general rule | [BR-26]-Each Invoice line (BG-25) shall contain the Item net price (BT-146). |
| 42 | FX-SCH-A-000206 | BR-27 | blocking | EN16931 general rule | [BR-27]-The Item net price (BT-146) shall NOT be negative. |
| 43 | FX-SCH-A-000207 | BR-28 | blocking | EN16931 general rule | [BR-28]-The Item gross price (BT-148) shall NOT be negative. |
| 44 | FX-SCH-A-000208 | BR-64 | blocking | EN16931 general rule | [BR-64]-The Item standard identifier (BT-157) shall have a Scheme identifier. |
| 45 | FX-SCH-A-000209 | BR-65 | blocking | EN16931 general rule | [BR-65]-The Item classification identifier (BT-158) shall have a Scheme identifier. |
| 46 | FX-SCH-A-000210 | BR-CO-04 | blocking | EN16931 common rule | [BR-CO-04]-Each Invoice line (BG-25) shall be categorized with an Invoiced item VAT category code (BT-151). |
| 47 | FX-SCH-A-000211 | BR-DEC-23 | blocking | EN16931 decimal rule | [BR-DEC-23]-The allowed maximum number of decimals for the Invoice line net amount (BT-131) is 2. |
| 48 | FX-SCH-A-000414 | BR-FXEXT-12 | blocking | Factur-X extension rule | [BR-FXEXT-12]-If the "Subtype of invoice line item" (EXT-FR-FE-163 / BT-X-8) has the value "GROUP" and if the "Invoice line net amount" (BT-131) is specified, all lower levels which has "Subtype of invoice line item" (EXT-FR-FE-163) equal to "GROUP" MUST contain a "Invoice line net amount" (BT-131) value. |
| 49 | FX-SCH-A-000075 | BR-17 | blocking | EN16931 general rule | [BR-17]-The Payee name (BT-59) shall be provided in the Invoice, if the Payee (BG-10) is different from the Seller (BG-4). |
| 50 | FX-SCH-A-000076 | BR-18 | blocking | EN16931 general rule | [BR-18]-The Seller tax representative name (BT-62) shall be provided in the Invoice, if the Seller (BG-4) has a Seller tax representative party (BG-11). |
| 51 | FX-SCH-A-000077 | BR-19 | blocking | EN16931 general rule | [BR-19]-The Seller tax representative postal address (BG-12) shall be provided in the Invoice, if the Seller (BG-4) has a Seller tax representative party (BG-11). |
| 52 | FX-SCH-A-000078 | BR-20 | blocking | EN16931 general rule | [BR-20]-The Seller tax representative postal address (BG-12) shall contain a Tax representative country code (BT-69), if the Seller (BG-4) has a Seller tax representative party (BG-11). |
| 53 | FX-SCH-A-000079 | BR-56 | blocking | EN16931 general rule | [BR-56]-Each Seller tax representative party (BG-11) shall have a Seller tax representative VAT identifier (BT-63). |
| 54 | FX-SCH-A-000001 | BR-CO-26 | blocking | EN16931 common rule | [BR-CO-26]-In order for the buyer to automatically identify a supplier, the Seller identifier (BT-29), the Seller legal registration identifier (BT-30) and/or the Seller VAT identifier (BT-31) shall be present. |
| 55 | FX-SCH-A-000212 | BR-30 | blocking | EN16931 general rule | [BR-30]-If both Invoice line period start date (BT-134) and Invoice line period end date (BT-135) are given then the Invoice line period end date (BT-135) shall be later or equal to the Invoice line period start date (BT-134). |
| 56 | FX-SCH-A-000213 | BR-CO-20 | blocking | EN16931 common rule | [BR-CO-20]-If Invoice line period (BG-26) is used, the Invoice line period start date (BT-134) or the Invoice line period end date (BT-135) shall be filled, or both. |
| 57 | FX-SCH-A-000214 | BR-42 | blocking | EN16931 general rule | [BR-42]-Each Invoice line allowance (BG-27) shall have an Invoice line allowance reason (BT-139) or an Invoice line allowance reason code (BT-140). |
| 58 | FX-SCH-A-000215 | BR-41 | blocking | EN16931 general rule | [BR-41]-Each Invoice line allowance (BG-27) shall have an Invoice line allowance amount (BT-136). |
| 59 | FX-SCH-A-000216 | BR-CO-07 | blocking | EN16931 common rule | [BR-CO-07]-Invoice line allowance reason code (BT-140) and Invoice line allowance reason (BT-139) shall indicate the same type of allowance reason. |
| 60 | FX-SCH-A-000217 | BR-CO-23 | blocking | EN16931 common rule | [BR-CO-23]-Each Invoice line allowance (BG-27) shall contain an Invoice line allowance reason (BT-139) or an Invoice line allowance reason code (BT-140), or both. |
| 61 | FX-SCH-A-000218 | BR-DEC-24 | blocking | EN16931 decimal rule | [BR-DEC-24]-The allowed maximum number of decimals for the Invoice line allowance amount (BT-136) is 2. |
| 62 | FX-SCH-A-000219 | BR-DEC-25 | blocking | EN16931 decimal rule | [BR-DEC-25]-The allowed maximum number of decimals for the Invoice line allowance base amount (BT-137) is 2. |
| 63 | FX-SCH-A-000220 | BR-43 | blocking | EN16931 general rule | [BR-43]-Each Invoice line charge (BG-28) shall have an Invoice line charge amount (BT-141). |
| 64 | FX-SCH-A-000221 | BR-44 | blocking | EN16931 general rule | [BR-44]-Each Invoice line charge (BG-28) shall have an Invoice line charge reason (BT-144) or an Invoice line charge reason code (BT-145). |
| 65 | FX-SCH-A-000222 | BR-CO-08 | blocking | EN16931 common rule | [BR-CO-08]-Invoice line charge reason code (BT-145) and Invoice line charge reason (BT-144) shall indicate the same type of charge reason. |
| 66 | FX-SCH-A-000223 | BR-CO-24 | blocking | EN16931 common rule | [BR-CO-24]-Each Invoice line charge (BG-28) shall contain an Invoice line charge reason (BT-144) or an Invoice line charge reason code (BT-145), or both. |
| 67 | FX-SCH-A-000224 | BR-DEC-27 | blocking | EN16931 decimal rule | [BR-DEC-27]-The allowed maximum number of decimals for the Invoice line charge amount (BT-141) is 2. |
| 68 | FX-SCH-A-000225 | BR-DEC-28 | blocking | EN16931 decimal rule | [BR-DEC-28]-The allowed maximum number of decimals for the Invoice line charge base amount (BT-142) is 2. |
| 69 | FX-SCH-A-000002 | BR-CO-09 | blocking | EN16931 common rule | [BR-CO-09]-The Seller VAT identifier (BT-31), the Seller tax representative VAT identifier (BT-63) and the Buyer VAT identifier (BT-48) shall have a prefix in accordance with ISO code ISO 3166-1 alpha-2 by which the country of issue may be identified. Nevertheless, Greece may use the prefix ‘EL’. |
| 70 | FX-SCH-A-000348 | CII-SR-463 | blocking | CII syntax rule | [CII-SR-463]-Each Specified Trade Allowance Charge (BG-20)(BG-21) shall contain a Charge Indicator. |
| 71 | FX-SCH-A-000081 | BR-AE-03 | blocking | EN16931 VAT-category rule | [BR-AE-03]-An Invoice that contains a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Reverse charge" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63) and the Buyer VAT identifier (BT-48) and/or the Buyer legal registration identifier (BT-47). |
| 72 | FX-SCH-A-000082 | BR-AE-06 | blocking | EN16931 VAT-category rule | [BR-AE-06]-In a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Reverse charge" the Document level allowance VAT rate (BT-96) shall be 0 (zero). |
| 73 | FX-SCH-A-000083 | BR-E-03 | blocking | EN16931 VAT-category rule | [BR-E-03]-An Invoice that contains a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Exempt from VAT" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 74 | FX-SCH-A-000084 | BR-E-06 | blocking | EN16931 VAT-category rule | [BR-E-06]-In a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Exempt from VAT", the Document level allowance VAT rate (BT-96) shall be 0 (zero). |
| 75 | FX-SCH-A-000085 | BR-G-03 | blocking | EN16931 VAT-category rule | [BR-G-03]-An Invoice that contains a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Export outside the EU" shall contain the Seller VAT Identifier (BT-31) or the Seller tax representative VAT identifier (BT-63). |
| 76 | FX-SCH-A-000086 | BR-G-06 | blocking | EN16931 VAT-category rule | [BR-G-06]-In a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Export outside the EU" the Document level allowance VAT rate (BT-96) shall be 0 (zero). |
| 77 | FX-SCH-A-000087 | BR-IC-03 | blocking | EN16931 VAT-category rule | [BR-IC-03]-An Invoice that contains a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Intra-community supply" shall contain the Seller VAT Identifier (BT-31) or the Seller tax representative VAT identifier (BT-63) and the Buyer VAT identifier (BT-48). |
| 78 | FX-SCH-A-000088 | BR-IC-06 | blocking | EN16931 VAT-category rule | [BR-IC-06]-In a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Intra-community supply" the Document level allowance VAT rate (BT-96) shall be 0 (zero). |
| 79 | FX-SCH-A-000089 | BR-AF-03 | blocking | EN16931 general rule | [BR-AF-03]-An Invoice that contains a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "IGIC" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 80 | FX-SCH-A-000090 | BR-AF-06 | blocking | EN16931 general rule | [BR-AF-06]-In a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "IGIC" the Document level allowance VAT rate (BT-96) shall be 0 (zero) or greater than zero. |
| 81 | FX-SCH-A-000091 | BR-AG-03 | blocking | EN16931 general rule | [BR-AG-03]-An Invoice that contains a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "IPSI" shall contain the Seller VAT Identifier (BT-31), the Seller Tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 82 | FX-SCH-A-000092 | BR-AG-06 | blocking | EN16931 general rule | [BR-AG-06]-In a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "IPSI" the Document level allowance VAT rate (BT-96) shall be 0 (zero) or greater than zero. |
| 83 | FX-SCH-A-000093 | BR-O-03 | blocking | EN16931 VAT-category rule | [BR-O-03]-An Invoice that contains a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Not subject to VAT" shall not contain the Seller VAT identifier (BT-31), the Seller tax representative VAT identifier (BT-63) or the Buyer VAT identifier (BT-48). |
| 84 | FX-SCH-A-000094 | BR-O-06 | blocking | EN16931 VAT-category rule | [BR-O-06]-A Document level allowance (BG-20) where VAT category code (BT-95) is "Not subject to VAT" shall not contain a Document level allowance VAT rate (BT-96). |
| 85 | FX-SCH-A-000095 | BR-S-03 | blocking | EN16931 VAT-category rule | [BR-S-03]-An Invoice that contains a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Standard rated" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 86 | FX-SCH-A-000096 | BR-S-06 | blocking | EN16931 VAT-category rule | [BR-S-06]-In a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Standard rated" the Document level allowance VAT rate (BT-96) shall be greater than zero. |
| 87 | FX-SCH-A-000097 | BR-Z-03 | blocking | EN16931 VAT-category rule | [BR-Z-03]-An Invoice that contains a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Zero rated" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 88 | FX-SCH-A-000098 | BR-Z-06 | blocking | EN16931 VAT-category rule | [BR-Z-06]-In a Document level allowance (BG-20) where the Document level allowance VAT category code (BT-95) is "Zero rated" the Document level allowance VAT rate (BT-96) shall be 0 (zero). |
| 89 | FX-SCH-A-000099 | BR-AE-04 | blocking | EN16931 VAT-category rule | [BR-AE-04]-An Invoice that contains a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "Reverse charge" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63) and the Buyer VAT identifier (BT-48) and/or the Buyer legal registration identifier (BT-47). |
| 90 | FX-SCH-A-000100 | BR-AE-07 | blocking | EN16931 VAT-category rule | [BR-AE-07]-In a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "Reverse charge" the Document level charge VAT rate (BT-103) shall be 0 (zero). |
| 91 | FX-SCH-A-000101 | BR-E-04 | blocking | EN16931 VAT-category rule | [BR-E-04]-An Invoice that contains a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "Exempt from VAT" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 92 | FX-SCH-A-000102 | BR-E-07 | blocking | EN16931 VAT-category rule | [BR-E-07]-In a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "Exempt from VAT", the Document level charge VAT rate (BT-103) shall be 0 (zero). |
| 93 | FX-SCH-A-000103 | BR-G-04 | blocking | EN16931 VAT-category rule | [BR-G-04]-An Invoice that contains a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "Export outside the EU" shall contain the Seller VAT Identifier (BT-31) or the Seller tax representative VAT identifier (BT-63). |
| 94 | FX-SCH-A-000104 | BR-G-07 | blocking | EN16931 VAT-category rule | [BR-G-07]-In a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "Export outside the EU" the Document level charge VAT rate (BT-103) shall be 0 (zero). |
| 95 | FX-SCH-A-000105 | BR-IC-04 | blocking | EN16931 VAT-category rule | [BR-IC-04]-An Invoice that contains a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "Intra-community supply" shall contain the Seller VAT Identifier (BT-31) or the Seller tax representative VAT identifier (BT-63) and the Buyer VAT identifier (BT-48). |
| 96 | FX-SCH-A-000106 | BR-IC-07 | blocking | EN16931 VAT-category rule | [BR-IC-07]-In a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "Intra-community supply" the Document level charge VAT rate (BT-103) shall be 0 (zero). |
| 97 | FX-SCH-A-000107 | BR-AF-04 | blocking | EN16931 general rule | [BR-AF-04]-An Invoice that contains a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "IGIC" shall contain the Seller VAT Identifier (BT-31), the Seller Tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 98 | FX-SCH-A-000108 | BR-AF-07 | blocking | EN16931 general rule | [BR-AF-07]-In a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "IGIC" the Document level charge VAT rate (BT-103) shall be 0 (zero) or greater than zero. |
| 99 | FX-SCH-A-000109 | BR-AG-04 | blocking | EN16931 general rule | [BR-AG-04]-An Invoice that contains a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "IPSI" shall contain the Seller VAT Identifier (BT-31), the Seller Tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 100 | FX-SCH-A-000110 | BR-AG-07 | blocking | EN16931 general rule | [BR-AG-07]-In a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "IPSI" the Document level charge VAT rate (BT-103) shall be 0 (zero) or greater than zero. |
| 101 | FX-SCH-A-000111 | BR-O-04 | blocking | EN16931 VAT-category rule | [BR-O-04]-An Invoice that contains a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "Not subject to VAT" shall not contain the Seller VAT identifier (BT-31), the Seller tax representative VAT identifier (BT-63) or the Buyer VAT identifier (BT-48). |
| 102 | FX-SCH-A-000112 | BR-O-07 | blocking | EN16931 VAT-category rule | [BR-O-07]-A Document level charge (BG-21) where the VAT category code (BT-102) is "Not subject to VAT" shall not contain a Document level charge VAT rate (BT-103). |
| 103 | FX-SCH-A-000113 | BR-S-04 | blocking | EN16931 VAT-category rule | [BR-S-04]-An Invoice that contains a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "Standard rated" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 104 | FX-SCH-A-000114 | BR-S-07 | blocking | EN16931 VAT-category rule | [BR-S-07]-In a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "Standard rated" the Document level charge VAT rate (BT-103) shall be greater than zero. |
| 105 | FX-SCH-A-000115 | BR-Z-04 | blocking | EN16931 VAT-category rule | [BR-Z-04]-An Invoice that contains a Document level charge where the Document level charge VAT category code (BT-102) is "Zero rated" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 106 | FX-SCH-A-000116 | BR-Z-07 | blocking | EN16931 VAT-category rule | [BR-Z-07]-In a Document level charge (BG-21) where the Document level charge VAT category code (BT-102) is "Zero rated" the Document level charge VAT rate (BT-103) shall be 0 (zero). |
| 107 | FX-SCH-A-000226 | BR-CO-10 | blocking | EN16931 common rule | [BR-CO-10]-Sum of Invoice line net amount (BT-106) = Σ Invoice line net amount (BT-131). |
| 108 | FX-SCH-A-000117 | BR-12 | blocking | EN16931 general rule | [BR-12]-An Invoice shall have the Sum of Invoice line net amount (BT-106). |
| 109 | FX-SCH-A-000003 | BR-13 | blocking | EN16931 general rule | [BR-13]-An Invoice shall have the Invoice total amount without VAT (BT-109). |
| 110 | FX-SCH-A-000004 | BR-14 | blocking | EN16931 general rule | [BR-14]-An Invoice shall have the Invoice total amount with VAT (BT-112). |
| 111 | FX-SCH-A-000005 | BR-15 | blocking | EN16931 general rule | [BR-15]-An Invoice shall have the Amount due for payment (BT-115). |
| 112 | FX-SCH-A-000118 | BR-CO-11 | blocking | EN16931 common rule | [BR-CO-11]-Sum of allowances on document level (BT-107) = Σ Document level allowance amount (BT-92). |
| 113 | FX-SCH-A-000119 | BR-CO-12 | blocking | EN16931 common rule | [BR-CO-12]-Sum of charges on document level (BT-108) = Σ Document level charge amount (BT-99). |
| 114 | FX-SCH-A-000120 | BR-CO-13 | blocking | EN16931 common rule | [BR-CO-13]-Invoice total amount without VAT (BT-109) = Σ Invoice line net amount (BT-131) - Sum of allowances on document level (BT-107) + Sum of charges on document level (BT-108). |
| 115 | FX-SCH-A-000121 | BR-CO-15 | blocking | EN16931 common rule | [BR-CO-15]-Invoice total amount with VAT (BT-112) = Invoice total amount without VAT (BT-109) + Invoice total VAT amount (BT-110). |
| 116 | FX-SCH-A-000122 | BR-CO-16 | blocking | EN16931 common rule | [BR-CO-16]-Amount due for payment (BT-115) = Invoice total amount with VAT (BT-112) -Paid amount (BT-113) +Rounding amount (BT-114). |
| 117 | FX-SCH-A-000123 | BR-DEC-09 | blocking | EN16931 decimal rule | [BR-DEC-09]-The allowed maximum number of decimals for the Sum of Invoice line net amount (BT-106) is 2. |
| 118 | FX-SCH-A-000374 | BR-DEC-10 | blocking | EN16931 decimal rule | [BR-DEC-10]-The allowed maximum number of decimals for the Sum of allowances on document level (BT-107) is 2. |
| 119 | FX-SCH-A-000125 | BR-DEC-11 | blocking | EN16931 decimal rule | [BR-DEC-11]-The allowed maximum number of decimals for the Sum of charges on document level (BT-108) is 2. |
| 120 | FX-SCH-A-000006 | BR-DEC-12 | blocking | EN16931 decimal rule | [BR-DEC-12]-The allowed maximum number of decimals for the Invoice total amount without VAT (BT-109) is 2. |
| 121 | FX-SCH-A-000007 | BR-DEC-13 | blocking | EN16931 decimal rule | [BR-DEC-13]-The allowed maximum number of decimals for the Invoice total VAT amount (BT-110) is 2. |
| 122 | FX-SCH-A-000008 | BR-DEC-14 | blocking | EN16931 decimal rule | [BR-DEC-14]-The allowed maximum number of decimals for the Invoice total amount with VAT (BT-112) is 2. |
| 123 | FX-SCH-A-000126 | BR-DEC-15 | blocking | EN16931 decimal rule | [BR-DEC-15]-The allowed maximum number of decimals for the Invoice total VAT amount in accounting currency (BT-111) is 2. |
| 124 | FX-SCH-A-000127 | BR-DEC-16 | blocking | EN16931 decimal rule | [BR-DEC-16]-The allowed maximum number of decimals for the Paid amount (BT-113) is 2. |
| 125 | FX-SCH-A-000128 | BR-DEC-17 | blocking | EN16931 decimal rule | [BR-DEC-17]-The allowed maximum number of decimals for the Rounding amount (BT-114) is 2. |
| 126 | FX-SCH-A-000009 | BR-DEC-18 | blocking | EN16931 decimal rule | [BR-DEC-18]-The allowed maximum number of decimals for the Amount due for payment (BT-115) is 2. |
| 127 | FX-SCH-A-000129 | BR-53 | blocking | EN16931 general rule | [BR-53]-If the VAT accounting currency code (BT-6) is present, then the Invoice total VAT amount in accounting currency (BT-111) shall be provided. |
| 128 | FX-SCH-A-000130 | BR-CO-14 | blocking | EN16931 common rule | [BR-CO-14]-Invoice total VAT amount (BT-110) = Σ VAT category tax amount (BT-117). |
| 129 | FX-SCH-A-000131 | BR-49 | blocking | EN16931 general rule | [BR-49]-A Payment instruction (BG-16) shall specify the Payment means type code (BT-81). |
| 130 | FX-SCH-A-000349 | CII-SR-464 | blocking | CII syntax rule | [CII-SR-464]-Only one BT-86 element is allowed on an invoice. |
| 131 | FX-SCH-A-000133 | BR-50 | blocking | EN16931 general rule | [BR-50]-A Payment account identifier (BT-84) shall be present if Credit transfer (BG-16) information is provided in the Invoice. |
| 132 | FX-SCH-A-000134 | BR-61 | blocking | EN16931 general rule | [BR-61]-If the Payment means type code (BT-81) means SEPA credit transfer, Local credit transfer or Non-SEPA international credit transfer, the Payment account identifier (BT-84) shall be present. |
| 133 | FX-SCH-A-000132 | BR-CO-27 | blocking | EN16931 common rule | [BR-CO-27]-Either the IBAN or a Proprietary ID (BT-84) shall be used. |
| 134 | FX-SCH-A-000135 | BR-CO-18 | blocking | EN16931 common rule | [BR-CO-18]-An Invoice shall at least have one VAT breakdown group (BG-23). |
| 135 | FX-SCH-A-000227 | BR-AE-08 | blocking | EN16931 VAT-category rule | [BR-AE-08]-In a VAT breakdown (BG-23) where the VAT category code (BT-118) is "Reverse charge" the VAT category taxable amount (BT-116) shall equal the sum of Invoice line net amounts (BT-131) minus the sum of Document level allowance amounts (BT-92) plus the sum of Document level charge amounts (BT-99) where the VAT category codes (BT-151, BT-95, BT-102) are "Reverse charge". |
| 136 | FX-SCH-A-000136 | BR-AE-09 | blocking | EN16931 VAT-category rule | [BR-AE-09]-The VAT category tax amount (BT-117) in a VAT breakdown (BG-23) where the VAT category code (BT-118) is "Reverse charge" shall be 0 (zero). |
| 137 | FX-SCH-A-000137 | BR-AE-10 | blocking | EN16931 VAT-category rule | [BR-AE-10]-A VAT Breakdown (BG-23) with VAT Category code (BT-118) "Reverse charge" shall have a VAT exemption reason code (BT-121), meaning "Reverse charge" or the VAT exemption reason text (BT-120) "Reverse charge" (or the equivalent standard text in another language). |
| 138 | FX-SCH-A-000228 | BR-E-08 | blocking | EN16931 VAT-category rule | [BR-E-08]-In a VAT breakdown (BG-23) where the VAT category code (BT-118) is "Exempt from VAT" the VAT category taxable amount (BT-116) shall equal the sum of Invoice line net amounts (BT-131) minus the sum of Document level allowance amounts (BT-92) plus the sum of Document level charge amounts (BT-99) where the VAT category codes (BT-151, BT-95, BT-102) are "Exempt from VAT". |
| 139 | FX-SCH-A-000375 | BR-E-09 | blocking | EN16931 VAT-category rule | [BR-E-09]-The VAT category tax amount (BT-117) in a VAT breakdown (BG-23) where the VAT category code (BT-118) equals "Exempt from VAT" shall equal 0 (zero). |
| 140 | FX-SCH-A-000139 | BR-E-10 | blocking | EN16931 VAT-category rule | [BR-E-10]-A VAT Breakdown (BG-23) with VAT Category code (BT-118) "Exempt from VAT" shall have a VAT exemption reason code (BT-121) or a VAT exemption reason text (BT-120). |
| 141 | FX-SCH-A-000229 | BR-G-08 | blocking | EN16931 VAT-category rule | [BR-G-08]-In a VAT breakdown (BG-23) where the VAT category code (BT-118) is "Export outside the EU" the VAT category taxable amount (BT-116) shall equal the sum of Invoice line net amounts (BT-131) minus the sum of Document level allowance amounts (BT-92) plus the sum of Document level charge amounts (BT-99) where the VAT category codes (BT-151, BT-95, BT-102) are "Export outside the EU". |
| 142 | FX-SCH-A-000140 | BR-G-09 | blocking | EN16931 VAT-category rule | [BR-G-09]-The VAT category tax amount (BT-117) in a VAT breakdown (BG-23) where the VAT category code (BT-118) is "Export outside the EU" shall be 0 (zero). |
| 143 | FX-SCH-A-000141 | BR-G-10 | blocking | EN16931 VAT-category rule | [BR-G-10]-A VAT Breakdown (BG-23) with the VAT Category code (BT-118) "Export outside the EU" shall have a VAT exemption reason code (BT-121), meaning "Export outside the EU" or the VAT exemption reason text (BT-120) "Export outside the EU" (or the equivalent standard text in another language). |
| 144 | FX-SCH-A-000230 | BR-IC-08 | blocking | EN16931 VAT-category rule | [BR-IC-08]-In a VAT breakdown (BG-23) where the VAT category code (BT-118) is "Intra-community supply" the VAT category taxable amount (BT-116) shall equal the sum of Invoice line net amounts (BT-131) minus the sum of Document level allowance amounts (BT-92) plus the sum of Document level charge amounts (BT-99) where the VAT category codes (BT-151, BT-95, BT-102) are "Intra-community supply". |
| 145 | FX-SCH-A-000142 | BR-IC-09 | blocking | EN16931 VAT-category rule | [BR-IC-09]-The VAT category tax amount (BT-117) in a VAT breakdown (BG-23) where the VAT category code (BT-118) is "Intra-community supply" shall be 0 (zero). |
| 146 | FX-SCH-A-000143 | BR-IC-10 | blocking | EN16931 VAT-category rule | [BR-IC-10]-A VAT Breakdown (BG-23) with the VAT Category code (BT-118) "Intra-community supply" shall have a VAT exemption reason code (BT-121), meaning "Intra-community supply" or the VAT exemption reason text (BT-120) "Intra-community supply" (or the equivalent standard text in another language). |
| 147 | FX-SCH-A-000144 | BR-IC-11 | blocking | EN16931 VAT-category rule | [BR-IC-11]-In an Invoice with a VAT breakdown (BG-23) where the VAT category code (BT-118) is "Intra-community supply" the Actual delivery date (BT-72) or the Invoicing period (BG-14) shall not be blank. |
| 148 | FX-SCH-A-000145 | BR-IC-12 | blocking | EN16931 VAT-category rule | [BR-IC-12]-In an Invoice with a VAT breakdown (BG-23) where the VAT category code (BT-118) is "Intra-community supply" the Deliver to country code (BT-80) shall not be blank. |
| 149 | FX-SCH-A-000231 | BR-AF-08 | blocking | EN16931 general rule | [BR-AF-08]-For each different value of VAT category rate (BT-119) where the VAT category code (BT-118) is "IGIC", the VAT category taxable amount (BT-116) in a VAT breakdown (BG-23) shall equal the sum of Invoice line net amounts (BT-131) plus the sum of document level charge amounts (BT-99) minus the sum of document level allowance amounts (BT-92) where the VAT category code (BT-151, BT-102, BT-95) is "IGIC" and the VAT rate (BT-152, BT-103, BT-96) equals the VAT category rate (BT-119). |
| 150 | FX-SCH-A-000146 | BR-AF-09 | blocking | EN16931 general rule | [BR-AF-09]-The VAT category tax amount (BT-117) in a VAT breakdown (BG-23) where VAT category code (BT-118) is "IGIC" shall equal the VAT category taxable amount (BT-116) multiplied by the VAT category rate (BT-119). |
| 151 | FX-SCH-A-000147 | BR-AF-10 | blocking | EN16931 general rule | [BR-AF-10]-A VAT Breakdown (BG-23) with VAT Category code (BT-118) "IGIC" shall not have a VAT exemption reason code (BT-121) or VAT exemption reason text (BT-120). |
| 152 | FX-SCH-A-000232 | BR-AG-08 | blocking | EN16931 general rule | [BR-AG-08]-For each different value of VAT category rate (BT-119) where the VAT category code (BT-118) is "IPSI", the VAT category taxable amount (BT-116) in a VAT breakdown (BG-23) shall equal the sum of Invoice line net amounts (BT-131) plus the sum of document level charge amounts (BT-99) minus the sum of document level allowance amounts (BT-92) where the VAT category code (BT-151, BT-102, BT-95) is "IPSI" and the VAT rate (BT-152, BT-103, BT-96) equals the VAT category rate (BT-119). |
| 153 | FX-SCH-A-000148 | BR-AG-09 | blocking | EN16931 general rule | [BR-AG-09]-The VAT category tax amount (BT-117) in a VAT breakdown (BG-23) where VAT category code (BT-118) is "IPSI" shall equal the VAT category taxable amount (BT-116) multiplied by the VAT category rate (BT-119). |
| 154 | FX-SCH-A-000149 | BR-AG-10 | blocking | EN16931 general rule | [BR-AG-10]-A VAT Breakdown (BG-23) with VAT Category code (BT-118) "IPSI" shall not have a VAT exemption reason code (BT-121) or VAT exemption reason text (BT-120). |
| 155 | FX-SCH-A-000233 | BR-O-08 | blocking | EN16931 VAT-category rule | [BR-O-08]-In a VAT breakdown (BG-23) where the VAT category code (BT-118) is " Not subject to VAT" the VAT category taxable amount (BT-116) shall equal the sum of Invoice line net amounts (BT-131) minus the sum of Document level allowance amounts (BT-92) plus the sum of Document level charge amounts (BT-99) where the VAT category codes (BT-151, BT-95, BT-102) are "Not subject to VAT". |
| 156 | FX-SCH-A-000150 | BR-O-09 | blocking | EN16931 VAT-category rule | [BR-O-09]-The VAT category tax amount (BT-117) in a VAT breakdown (BG-23) where the VAT category code (BT-118) is "Not subject to VAT" shall be 0 (zero). |
| 157 | FX-SCH-A-000151 | BR-O-10 | blocking | EN16931 VAT-category rule | [BR-O-10]-A VAT Breakdown (BG-23) with VAT Category code (BT-118) " Not subject to VAT" shall have a VAT exemption reason code (BT-121), meaning " Not subject to VAT" or a VAT exemption reason text (BT-120) " Not subject to VAT" (or the equivalent standard text in another language). |
| 158 | FX-SCH-A-000152 | BR-O-11 | blocking | EN16931 VAT-category rule | [BR-O-11]-An Invoice that contains a VAT breakdown group (BG-23) with a VAT category code (BT-118) "Not subject to VAT" shall not contain other VAT breakdown groups (BG-23). |
| 159 | FX-SCH-A-000234 | BR-O-12 | blocking | EN16931 VAT-category rule | [BR-O-12]-An Invoice that contains a VAT breakdown group (BG-23) with a VAT category code (BT-118) "Not subject to VAT" shall not contain an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is not "Not subject to VAT". |
| 160 | FX-SCH-A-000153 | BR-O-13 | blocking | EN16931 VAT-category rule | [BR-O-13]-An Invoice that contains a VAT breakdown group (BG-23) with a VAT category code (BT-118) "Not subject to VAT" shall not contain Document level allowances (BG-20) where Document level allowance VAT category code (BT-95) is not "Not subject to VAT". |
| 161 | FX-SCH-A-000154 | BR-O-14 | blocking | EN16931 VAT-category rule | [BR-O-14]-An Invoice that contains a VAT breakdown group (BG-23) with a VAT category code (BT-118) "Not subject to VAT" shall not contain Document level charges (BG-21) where Document level charge VAT category code (BT-102) is not "Not subject to VAT". |
| 162 | FX-SCH-A-000235 | BR-AE-02 | blocking | EN16931 VAT-category rule | [BR-AE-02]-An Invoice that contains an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "Reverse charge" shall contain the Seller VAT Identifier (BT-31), the Seller Tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63) and the Buyer VAT identifier (BT-48) and/or the Buyer legal registration identifier (BT-47). |
| 163 | FX-SCH-A-000236 | BR-AE-05 | blocking | EN16931 VAT-category rule | [BR-AE-05]-In an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "Reverse charge" the Invoiced item VAT rate (BT-152) shall be 0 (zero). |
| 164 | FX-SCH-A-000237 | BR-E-02 | blocking | EN16931 VAT-category rule | [BR-E-02]-An Invoice that contains an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "Exempt from VAT" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 165 | FX-SCH-A-000238 | BR-E-05 | blocking | EN16931 VAT-category rule | [BR-E-05]-In an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "Exempt from VAT", the Invoiced item VAT rate (BT-152) shall be 0 (zero). |
| 166 | FX-SCH-A-000239 | BR-G-02 | blocking | EN16931 VAT-category rule | [BR-G-02]-An Invoice that contains an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "Export outside the EU" shall contain the Seller VAT Identifier (BT-31) or the Seller tax representative VAT identifier (BT-63). |
| 167 | FX-SCH-A-000240 | BR-G-05 | blocking | EN16931 VAT-category rule | [BR-G-05]-In an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "Export outside the EU" the Invoiced item VAT rate (BT-152) shall be 0 (zero). |
| 168 | FX-SCH-A-000241 | BR-IC-02 | blocking | EN16931 VAT-category rule | [BR-IC-02]-An Invoice that contains an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "Intra-community supply" shall contain the Seller VAT Identifier (BT-31) or the Seller tax representative VAT identifier (BT-63) and the Buyer VAT identifier (BT-48). |
| 169 | FX-SCH-A-000242 | BR-IC-05 | blocking | EN16931 VAT-category rule | [BR-IC-05]-In an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "Intracommunity supply" the Invoiced item VAT rate (BT-152) shall be 0 (zero). |
| 170 | FX-SCH-A-000243 | BR-AF-02 | blocking | EN16931 general rule | [BR-AF-02]-An Invoice that contains an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "IGIC" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 171 | FX-SCH-A-000244 | BR-AF-05 | blocking | EN16931 general rule | [BR-AF-05]-In an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "IGIC" the invoiced item VAT rate (BT-152) shall be greater than 0 (zero). |
| 172 | FX-SCH-A-000245 | BR-AG-02 | blocking | EN16931 general rule | [BR-AG-02]-An Invoice that contains an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "IPSI" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 173 | FX-SCH-A-000246 | BR-AG-05 | blocking | EN16931 general rule | [BR-AG-05]-In an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "IPSI" the Invoiced item VAT rate (BT-152) shall be 0 (zero) or greater than zero. |
| 174 | FX-SCH-A-000247 | BR-O-02 | blocking | EN16931 VAT-category rule | [BR-O-02]-An Invoice that contains an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "Not subject to VAT" shall not contain the Seller VAT identifier (BT-31), the Seller tax representative VAT identifier (BT-63) or the Buyer VAT identifier (BT-46). |
| 175 | FX-SCH-A-000248 | BR-O-05 | blocking | EN16931 VAT-category rule | [BR-O-05]-An Invoice line (BG-25) where the VAT category code (BT-151) is "Not subject to VAT" shall not contain an Invoiced item VAT rate (BT-152). |
| 176 | FX-SCH-A-000249 | BR-S-02 | blocking | EN16931 VAT-category rule | [BR-S-02]-An Invoice that contains an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "Standard rated" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 177 | FX-SCH-A-000250 | BR-S-05 | blocking | EN16931 VAT-category rule | [BR-S-05]-In an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "Standard rated" the Invoiced item VAT rate (BT-152) shall be greater than zero. |
| 178 | FX-SCH-A-000251 | BR-Z-02 | blocking | EN16931 VAT-category rule | [BR-Z-02]-An Invoice that contains an Invoice line where the Invoiced item VAT category code (BT-151) is "Zero rated" shall contain the Seller VAT Identifier (BT-31), the Seller tax registration identifier (BT-32) and/or the Seller tax representative VAT identifier (BT-63). |
| 179 | FX-SCH-A-000252 | BR-Z-05 | blocking | EN16931 VAT-category rule | [BR-Z-05]-In an Invoice line (BG-25) where the Invoiced item VAT category code (BT-151) is "Zero rated" the Invoiced item VAT rate (BT-152) shall be 0 (zero). |
| 180 | FX-SCH-A-000253 | BR-16 | blocking | EN16931 general rule | [BR-16]-An Invoice shall have at least one Invoice line (BG-25). |
| 181 | FX-SCH-A-000010 | BR-01 | blocking | EN16931 general rule | [BR-01]-An Invoice shall have a Specification identifier (BT-24). |
| 182 | FX-SCH-A-000011 | BR-02 | blocking | EN16931 general rule | [BR-02]-An Invoice shall have an Invoice number (BT-1). |
| 183 | FX-SCH-A-000012 | BR-03 | blocking | EN16931 general rule | [BR-03]-An Invoice shall have an Invoice issue date (BT-2). |
| 184 | FX-SCH-A-000013 | BR-04 | blocking | EN16931 general rule | [BR-04]-An Invoice shall have an Invoice type code (BT-3). |
| 185 | FX-SCH-A-000014 | BR-05 | blocking | EN16931 general rule | [BR-05]-An Invoice shall have an Invoice currency code (BT-5). |
| 186 | FX-SCH-A-000015 | BR-06 | blocking | EN16931 general rule | [BR-06]-An Invoice shall contain the Seller name (BT-27). |
| 187 | FX-SCH-A-000016 | BR-07 | blocking | EN16931 general rule | [BR-07]-An Invoice shall contain the Buyer name (BT-44). |
| 188 | FX-SCH-A-000017 | BR-08 | blocking | EN16931 general rule | [BR-08]-An Invoice shall contain the Seller postal address (BG-5). |
| 189 | FX-SCH-A-000018 | BR-09 | blocking | EN16931 general rule | [BR-09]-The Seller postal address (BG-5) shall contain a Seller country code (BT-40). |
| 190 | FX-SCH-A-000156 | BR-10 | blocking | EN16931 general rule | [BR-10]-An Invoice shall contain the Buyer postal address (BG-8). |
| 191 | FX-SCH-A-000157 | BR-11 | blocking | EN16931 general rule | [BR-11]-The Buyer postal address shall contain a Buyer country code (BT-55). |
| 192 | FX-SCH-A-000158 | BR-62 | blocking | EN16931 general rule | [BR-62]-The Seller electronic address (BT-34) shall have a Scheme identifier. |
| 193 | FX-SCH-A-000159 | BR-63 | blocking | EN16931 general rule | [BR-63]-The Buyer electronic address (BT-49) shall have a Scheme identifier. |
| 194 | FX-SCH-A-000254 | BR-S-01 | blocking | EN16931 VAT-category rule | [BR-S-01]-An Invoice that contains an Invoice line (BG-25), a Document level allowance (BG-20) or a Document level charge (BG-21) where the VAT category code (BT-151, BT-95 or BT-102) is "Standard rated" shall contain in the VAT breakdown (BG-23) at least one VAT category code (BT-118) equal with "Standard rated". |
| 195 | FX-SCH-A-000255 | BR-Z-01 | blocking | EN16931 VAT-category rule | [BR-Z-01]-An Invoice that contains an Invoice line (BG-25), a Document level allowance (BG-20) or a Document level charge (BG-21) where the VAT category code (BT-151, BT-95 or BT-102) is "Zero rated" shall contain in the VAT breakdown (BG-23) exactly one VAT category code (BT-118) equal with "Zero rated". |
| 196 | FX-SCH-A-000256 | BR-E-01 | blocking | EN16931 VAT-category rule | [BR-E-01]-An Invoice that contains an Invoice line (BG-25), a Document level allowance (BG-20) or a Document level charge (BG-21) where the VAT category code (BT-151, BT-95 or BT-102) is “Exempt from VAT” shall contain exactly one VAT breakdown (BG-23) with the VAT category code (BT-118) equal to "Exempt from VAT". |
| 197 | FX-SCH-A-000257 | BR-AE-01 | blocking | EN16931 VAT-category rule | [BR-AE-01]-An Invoice that contains an Invoice line (BG-25), a Document level allowance (BG-20) or a Document level charge (BG-21) where the VAT category code (BT-151, BT-95 or BT-102) is "Reverse charge" shall contain in the VAT breakdown (BG-23) exactly one VAT category code (BT-118) equal with "VAT reverse charge". |
| 198 | FX-SCH-A-000258 | BR-IC-01 | blocking | EN16931 VAT-category rule | [BR-IC-01]-An Invoice that contains an Invoice line (BG-25), a Document level allowance (BG-20) or a Document level charge (BG-21) where the VAT category code (BT-151, BT-95 or BT-102) is "Intra-community supply" shall contain in the VAT breakdown (BG-23) exactly one VAT category code (BT-118) equal with "Intra-community supply". |
| 199 | FX-SCH-A-000259 | BR-G-01 | blocking | EN16931 VAT-category rule | [BR-G-01]-An Invoice that contains an Invoice line (BG-25), a Document level allowance (BG-20) or a Document level charge (BG-21) where the VAT category code (BT-151, BT-95 or BT-102) is "Export outside the EU" shall contain in the VAT breakdown (BG-23) exactly one VAT category code (BT-118) equal with "Export outside the EU". |
| 200 | FX-SCH-A-000260 | BR-O-01 | blocking | EN16931 VAT-category rule | [BR-O-01]-An Invoice that contains an Invoice line (BG-25), a Document level allowance (BG-20) or a Document level charge (BG-21) where the VAT category code (BT-151, BT-95 or BT-102) is "Not subject to VAT" shall contain exactly one VAT breakdown group (BG-23) with the VAT category code (BT-118) equal to "Not subject to VAT". |
| 201 | FX-SCH-A-000261 | BR-AF-01 | blocking | EN16931 general rule | [BR-AF-01]-An Invoice that contains an Invoice line (BG-25), a Document level allowance (BG-20) or a Document level charge (BG-21) where the VAT category code (BT-151, BT-95 or BT-102) is "IGIC" shall contain in the VAT breakdown (BG-23) at least one VAT category code (BT-118) equal with "IGIC". |
| 202 | FX-SCH-A-000262 | BR-AG-01 | blocking | EN16931 general rule | [BR-AG-01]-An Invoice that contains an Invoice line (BG-25), a Document level allowance (BG-20) or a Document level charge (BG-21) where the VAT category code (BT-151, BT-95 or BT-102) is "IPSI" shall contain in the VAT breakdown (BG-23) at least one VAT category code (BT-118) equal with "IPSI". |
| 203 | FX-SCH-A-000263 | BR-B-01 | blocking | EN16931 general rule | [BR-B-01]-An Invoice where the VAT category code (BT-151, BT-95 or BT-102) is “Split payment” shall be a domestic Italian invoice. |
| 204 | FX-SCH-A-000264 | BR-B-02 | blocking | EN16931 general rule | [BR-B-02]-An Invoice that contains an Invoice line (BG-25), a Document level allowance (BG-20) or a Document level charge (BG-21) where the VAT category code (BT-151, BT-95 or BT-102) is “Split payment" shall not contain an invoice line (BG-25), a Document level allowance (BG-20) or a Document level charge (BG-21) where the VAT category code (BT-151, BT-95 or BT-102) is “Standard rated”. |
| 205 | FX-SCH-A-000350 | CII-SR-465 | blocking | CII syntax rule | [CII-SR-465]-Only one BT-41 element is allowed on an invoice. |
| 206 | FX-SCH-A-000351 | CII-SR-466 | blocking | CII syntax rule | [CII-SR-466]-Only one BT-56 element is allowed on an invoice. |
| 207 | FX-SCH-A-000027 | - | blocking | Factur-X profile/structure constraint | Element 'ram:SellerTradeParty' must occur exactly 1 times. |
| 208 | FX-SCH-A-000028 | - | blocking | Factur-X profile/structure constraint | Element 'ram:BuyerTradeParty' must occur exactly 1 times. |
| 209 | FX-SCH-A-000170 | BR-57 | blocking | EN16931 general rule | [BR-57]-Each Deliver to address (BG-15) shall contain a Deliver to country code (BT-80). |
| 210 | FX-SCH-A-000182 | BR-55 | blocking | EN16931 general rule | [BR-55]-Each Preceding Invoice reference (BG-3) shall contain a Preceding Invoice reference (BT-25). |
| 211 | FX-SCH-A-000029 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IssuerAssignedID' must occur exactly 1 times. |
| 212 | FX-SCH-A-000354 | BR-FX-EN-04 | warning | Factur-X extension rule | [BR-FX-EN-04]-An invoice that is not a down payment invoice (code 386) must contain either BT-72 "Actual delivery date", BG-14 "Invoicing period" or BG-26 "Invoice line period" in each invoice item to indicate the delivery/service date. If BT-72 is not used, at least the country of delivery (BT-80) must be specified for technical reasons. |
| 213 | FX-SCH-A-000019 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ID' must occur exactly 1 times. |
| 214 | FX-SCH-A-000020 | - | blocking | Factur-X profile/structure constraint | Element 'ram:TypeCode' must occur exactly 1 times. |
| 215 | FX-SCH-A-000160 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Content' must occur exactly 1 times. |
| 216 | FX-SCH-A-000161 | - | blocking | Factur-X profile/structure constraint | Element 'ram:SubjectCode' may occur at maximum 1 times. |
| 217 | FX-SCH-A-000162 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:SubjectCode' is not allowed. |
| 218 | FX-SCH-A-000021 | - | blocking | Factur-X profile/structure constraint | Attribute '@format' is required in this context. |
| 219 | FX-SCH-A-000022 | - | blocking | Factur-X profile/structure constraint | Value of '@format' is not allowed. |
| 220 | FX-SCH-A-000023 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:TypeCode' is not allowed. |
| 221 | FX-SCH-A-000024 | - | blocking | Factur-X profile/structure constraint | Element 'ram:BusinessProcessSpecifiedDocumentContextParameter' may occur at maximum 1 times. |
| 222 | FX-SCH-A-000025 | - | blocking | Factur-X profile/structure constraint | Element 'ram:GuidelineSpecifiedDocumentContextParameter' must occur exactly 1 times. |
| 223 | FX-SCH-A-000019 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ID' must occur exactly 1 times. |
| 224 | FX-SCH-A-000019 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ID' must occur exactly 1 times. |
| 225 | FX-SCH-A-000026 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:ID' is not allowed. |
| 226 | FX-SCH-A-000265 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IncludedSupplyChainTradeLineItem' must occur at least 1 times. |
| 227 | FX-SCH-A-000029 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IssuerAssignedID' must occur exactly 1 times. |
| 228 | FX-SCH-A-000020 | - | blocking | Factur-X profile/structure constraint | Element 'ram:TypeCode' must occur exactly 1 times. |
| 229 | FX-SCH-A-000282 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:ReferenceTypeCode' is not allowed. |
| 230 | FX-SCH-A-000023 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:TypeCode' is not allowed. |
| 231 | FX-SCH-A-000029 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IssuerAssignedID' must occur exactly 1 times. |
| 232 | FX-SCH-A-000020 | - | blocking | Factur-X profile/structure constraint | Element 'ram:TypeCode' must occur exactly 1 times. |
| 233 | FX-SCH-A-000023 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:TypeCode' is not allowed. |
| 234 | FX-SCH-A-000029 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IssuerAssignedID' must occur exactly 1 times. |
| 235 | FX-SCH-A-000020 | - | blocking | Factur-X profile/structure constraint | Element 'ram:TypeCode' must occur exactly 1 times. |
| 236 | FX-SCH-A-000283 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Name' may occur at maximum 1 times. |
| 237 | FX-SCH-A-000284 | - | blocking | Factur-X profile/structure constraint | Element 'ram:AttachmentBinaryObject' may occur at maximum 1 times. |
| 238 | FX-SCH-A-000285 | - | blocking | Factur-X profile/structure constraint | Attribute '@mimeCode' is required in this context. |
| 239 | FX-SCH-A-000287 | - | blocking | Factur-X profile/structure constraint | Value of '@mimeCode' is not allowed. |
| 240 | FX-SCH-A-000286 | - | blocking | Factur-X profile/structure constraint | Attribute '@filename' is required in this context. |
| 241 | FX-SCH-A-000023 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:TypeCode' is not allowed. |
| 242 | FX-SCH-A-000029 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IssuerAssignedID' must occur exactly 1 times. |
| 243 | FX-SCH-A-000163 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ID' may occur at maximum 1 times. |
| 244 | FX-SCH-A-000164 | - | blocking | Factur-X profile/structure constraint | Element 'ram:GlobalID' may occur at maximum 1 times. |
| 245 | FX-SCH-A-000030 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Name' must occur exactly 1 times. |
| 246 | FX-SCH-A-000288 | - | blocking | Factur-X profile/structure constraint | Element 'ram:DefinedTradeContact' may occur at maximum 1 times. |
| 247 | FX-SCH-A-000032 | - | blocking | Factur-X profile/structure constraint | Element 'ram:PostalTradeAddress' must occur exactly 1 times. |
| 248 | FX-SCH-A-000165 | - | blocking | Factur-X profile/structure constraint | Element 'ram:URIUniversalCommunication' may occur at maximum 1 times. |
| 249 | FX-SCH-A-000166 | - | blocking | Factur-X profile/structure constraint | Element 'ram:SpecifiedTaxRegistration' may occur at maximum 1 times. |
| 250 | FX-SCH-A-000168 | - | blocking | Factur-X profile/structure constraint | Element 'ram:URIID' must occur exactly 1 times. |
| 251 | FX-SCH-A-000289 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CompleteNumber' must occur exactly 1 times. |
| 252 | FX-SCH-A-000037 | - | blocking | Factur-X profile/structure constraint | Attribute '@schemeID' is required in this context. |
| 253 | FX-SCH-A-000031 | - | blocking | Factur-X profile/structure constraint | Value of '@schemeID' is not allowed. |
| 254 | FX-SCH-A-000035 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CountryID' must occur exactly 1 times. |
| 255 | FX-SCH-A-000167 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CountrySubDivisionName' may occur at maximum 1 times. |
| 256 | FX-SCH-A-000036 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:CountryID' is not allowed. |
| 257 | FX-SCH-A-000031 | - | blocking | Factur-X profile/structure constraint | Value of '@schemeID' is not allowed. |
| 258 | FX-SCH-A-000019 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ID' must occur exactly 1 times. |
| 259 | FX-SCH-A-000037 | - | blocking | Factur-X profile/structure constraint | Attribute '@schemeID' is required in this context. |
| 260 | FX-SCH-A-000031 | - | blocking | Factur-X profile/structure constraint | Value of '@schemeID' is not allowed. |
| 261 | FX-SCH-A-000168 | - | blocking | Factur-X profile/structure constraint | Element 'ram:URIID' must occur exactly 1 times. |
| 262 | FX-SCH-A-000037 | - | blocking | Factur-X profile/structure constraint | Attribute '@schemeID' is required in this context. |
| 263 | FX-SCH-A-000031 | - | blocking | Factur-X profile/structure constraint | Value of '@schemeID' is not allowed. |
| 264 | FX-SCH-A-000029 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IssuerAssignedID' must occur exactly 1 times. |
| 265 | FX-SCH-A-000029 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IssuerAssignedID' must occur exactly 1 times. |
| 266 | FX-SCH-A-000030 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Name' must occur exactly 1 times. |
| 267 | FX-SCH-A-000032 | - | blocking | Factur-X profile/structure constraint | Element 'ram:PostalTradeAddress' must occur exactly 1 times. |
| 268 | FX-SCH-A-000169 | - | blocking | Factur-X profile/structure constraint | Element 'ram:SpecifiedTaxRegistration' must occur exactly 1 times. |
| 269 | FX-SCH-A-000035 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CountryID' must occur exactly 1 times. |
| 270 | FX-SCH-A-000167 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CountrySubDivisionName' may occur at maximum 1 times. |
| 271 | FX-SCH-A-000036 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:CountryID' is not allowed. |
| 272 | FX-SCH-A-000019 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ID' must occur exactly 1 times. |
| 273 | FX-SCH-A-000037 | - | blocking | Factur-X profile/structure constraint | Attribute '@schemeID' is required in this context. |
| 274 | FX-SCH-A-000031 | - | blocking | Factur-X profile/structure constraint | Value of '@schemeID' is not allowed. |
| 275 | FX-SCH-A-000030 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Name' must occur exactly 1 times. |
| 276 | FX-SCH-A-000187 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Description' may occur at maximum 1 times. |
| 277 | FX-SCH-A-000288 | - | blocking | Factur-X profile/structure constraint | Element 'ram:DefinedTradeContact' may occur at maximum 1 times. |
| 278 | FX-SCH-A-000032 | - | blocking | Factur-X profile/structure constraint | Element 'ram:PostalTradeAddress' must occur exactly 1 times. |
| 279 | FX-SCH-A-000165 | - | blocking | Factur-X profile/structure constraint | Element 'ram:URIUniversalCommunication' may occur at maximum 1 times. |
| 280 | FX-SCH-A-000033 | - | blocking | Factur-X profile/structure constraint | Element variant 'ram:SpecifiedTaxRegistration[ram:ID/@schemeID="VA"]' may occur at maximum 1 times. |
| 281 | FX-SCH-A-000034 | - | blocking | Factur-X profile/structure constraint | Element variant 'ram:SpecifiedTaxRegistration[ram:ID/@schemeID="FC"]' may occur at maximum 1 times. |
| 282 | FX-SCH-A-000168 | - | blocking | Factur-X profile/structure constraint | Element 'ram:URIID' must occur exactly 1 times. |
| 283 | FX-SCH-A-000289 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CompleteNumber' must occur exactly 1 times. |
| 284 | FX-SCH-A-000037 | - | blocking | Factur-X profile/structure constraint | Attribute '@schemeID' is required in this context. |
| 285 | FX-SCH-A-000031 | - | blocking | Factur-X profile/structure constraint | Value of '@schemeID' is not allowed. |
| 286 | FX-SCH-A-000035 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CountryID' must occur exactly 1 times. |
| 287 | FX-SCH-A-000167 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CountrySubDivisionName' may occur at maximum 1 times. |
| 288 | FX-SCH-A-000036 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:CountryID' is not allowed. |
| 289 | FX-SCH-A-000031 | - | blocking | Factur-X profile/structure constraint | Value of '@schemeID' is not allowed. |
| 290 | FX-SCH-A-000019 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ID' must occur exactly 1 times. |
| 291 | FX-SCH-A-000037 | - | blocking | Factur-X profile/structure constraint | Attribute '@schemeID' is required in this context. |
| 292 | FX-SCH-A-000019 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ID' must occur exactly 1 times. |
| 293 | FX-SCH-A-000037 | - | blocking | Factur-X profile/structure constraint | Attribute '@schemeID' is required in this context. |
| 294 | FX-SCH-A-000168 | - | blocking | Factur-X profile/structure constraint | Element 'ram:URIID' must occur exactly 1 times. |
| 295 | FX-SCH-A-000037 | - | blocking | Factur-X profile/structure constraint | Attribute '@schemeID' is required in this context. |
| 296 | FX-SCH-A-000031 | - | blocking | Factur-X profile/structure constraint | Value of '@schemeID' is not allowed. |
| 297 | FX-SCH-A-000171 | - | blocking | Factur-X profile/structure constraint | Element 'ram:OccurrenceDateTime' must occur exactly 1 times. |
| 298 | FX-SCH-A-000021 | - | blocking | Factur-X profile/structure constraint | Attribute '@format' is required in this context. |
| 299 | FX-SCH-A-000022 | - | blocking | Factur-X profile/structure constraint | Value of '@format' is not allowed. |
| 300 | FX-SCH-A-000029 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IssuerAssignedID' must occur exactly 1 times. |
| 301 | FX-SCH-A-000029 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IssuerAssignedID' must occur exactly 1 times. |
| 302 | FX-SCH-A-000163 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ID' may occur at maximum 1 times. |
| 303 | FX-SCH-A-000164 | - | blocking | Factur-X profile/structure constraint | Element 'ram:GlobalID' may occur at maximum 1 times. |
| 304 | FX-SCH-A-000037 | - | blocking | Factur-X profile/structure constraint | Attribute '@schemeID' is required in this context. |
| 305 | FX-SCH-A-000031 | - | blocking | Factur-X profile/structure constraint | Value of '@schemeID' is not allowed. |
| 306 | FX-SCH-A-000035 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CountryID' must occur exactly 1 times. |
| 307 | FX-SCH-A-000167 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CountrySubDivisionName' may occur at maximum 1 times. |
| 308 | FX-SCH-A-000036 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:CountryID' is not allowed. |
| 309 | FX-SCH-A-000172 | - | blocking | Factur-X profile/structure constraint | Element 'ram:PaymentReference' may occur at maximum 1 times. |
| 310 | FX-SCH-A-000038 | - | blocking | Factur-X profile/structure constraint | Element 'ram:InvoiceCurrencyCode' must occur exactly 1 times. |
| 311 | FX-SCH-A-000173 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ApplicableTradeTax' must occur at least 1 times. |
| 312 | FX-SCH-A-000174 | - | blocking | Factur-X profile/structure constraint | Element 'ram:SpecifiedTradePaymentTerms' may occur at maximum 1 times. |
| 313 | FX-SCH-A-000039 | - | blocking | Factur-X profile/structure constraint | Element 'ram:SpecifiedTradeSettlementHeaderMonetarySummation' must occur exactly 1 times. |
| 314 | FX-SCH-A-000175 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ReceivableSpecifiedTradeAccountingAccount' may occur at maximum 1 times. |
| 315 | FX-SCH-A-000176 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CalculatedAmount' must occur exactly 1 times. |
| 316 | FX-SCH-A-000020 | - | blocking | Factur-X profile/structure constraint | Element 'ram:TypeCode' must occur exactly 1 times. |
| 317 | FX-SCH-A-000177 | - | blocking | Factur-X profile/structure constraint | Element 'ram:BasisAmount' must occur exactly 1 times. |
| 318 | FX-SCH-A-000178 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CategoryCode' must occur exactly 1 times. |
| 319 | FX-SCH-A-000179 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:CategoryCode' is not allowed. |
| 320 | FX-SCH-A-000180 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:DueDateTypeCode' is not allowed. |
| 321 | FX-SCH-A-000181 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:ExemptionReasonCode' is not allowed. |
| 322 | FX-SCH-A-000021 | - | blocking | Factur-X profile/structure constraint | Attribute '@format' is required in this context. |
| 323 | FX-SCH-A-000022 | - | blocking | Factur-X profile/structure constraint | Value of '@format' is not allowed. |
| 324 | FX-SCH-A-000023 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:TypeCode' is not allowed. |
| 325 | FX-SCH-A-000021 | - | blocking | Factur-X profile/structure constraint | Attribute '@format' is required in this context. |
| 326 | FX-SCH-A-000022 | - | blocking | Factur-X profile/structure constraint | Value of '@format' is not allowed. |
| 327 | FX-SCH-A-000021 | - | blocking | Factur-X profile/structure constraint | Attribute '@format' is required in this context. |
| 328 | FX-SCH-A-000022 | - | blocking | Factur-X profile/structure constraint | Value of '@format' is not allowed. |
| 329 | FX-SCH-A-000040 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:InvoiceCurrencyCode' is not allowed. |
| 330 | FX-SCH-A-000021 | - | blocking | Factur-X profile/structure constraint | Attribute '@format' is required in this context. |
| 331 | FX-SCH-A-000022 | - | blocking | Factur-X profile/structure constraint | Value of '@format' is not allowed. |
| 332 | FX-SCH-A-000163 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ID' may occur at maximum 1 times. |
| 333 | FX-SCH-A-000164 | - | blocking | Factur-X profile/structure constraint | Element 'ram:GlobalID' may occur at maximum 1 times. |
| 334 | FX-SCH-A-000030 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Name' must occur exactly 1 times. |
| 335 | FX-SCH-A-000037 | - | blocking | Factur-X profile/structure constraint | Attribute '@schemeID' is required in this context. |
| 336 | FX-SCH-A-000031 | - | blocking | Factur-X profile/structure constraint | Value of '@schemeID' is not allowed. |
| 337 | FX-SCH-A-000031 | - | blocking | Factur-X profile/structure constraint | Value of '@schemeID' is not allowed. |
| 338 | FX-SCH-A-000183 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ChargeIndicator' must occur exactly 1 times. |
| 339 | FX-SCH-A-000184 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ActualAmount' must occur exactly 1 times. |
| 340 | FX-SCH-A-000185 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CategoryTradeTax' must occur exactly 1 times. |
| 341 | FX-SCH-A-000020 | - | blocking | Factur-X profile/structure constraint | Element 'ram:TypeCode' must occur exactly 1 times. |
| 342 | FX-SCH-A-000178 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CategoryCode' must occur exactly 1 times. |
| 343 | FX-SCH-A-000179 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:CategoryCode' is not allowed. |
| 344 | FX-SCH-A-000023 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:TypeCode' is not allowed. |
| 345 | FX-SCH-A-000186 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:ReasonCode' is not allowed. |
| 346 | FX-SCH-A-000183 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ChargeIndicator' must occur exactly 1 times. |
| 347 | FX-SCH-A-000184 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ActualAmount' must occur exactly 1 times. |
| 348 | FX-SCH-A-000185 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CategoryTradeTax' must occur exactly 1 times. |
| 349 | FX-SCH-A-000020 | - | blocking | Factur-X profile/structure constraint | Element 'ram:TypeCode' must occur exactly 1 times. |
| 350 | FX-SCH-A-000178 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CategoryCode' must occur exactly 1 times. |
| 351 | FX-SCH-A-000179 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:CategoryCode' is not allowed. |
| 352 | FX-SCH-A-000023 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:TypeCode' is not allowed. |
| 353 | FX-SCH-A-000376 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:ReasonCode[not (@listID)]' is not allowed. |
| 354 | FX-SCH-A-000187 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Description' may occur at maximum 1 times. |
| 355 | FX-SCH-A-000188 | - | blocking | Factur-X profile/structure constraint | Element 'ram:DirectDebitMandateID' may occur at maximum 1 times. |
| 356 | FX-SCH-A-000021 | - | blocking | Factur-X profile/structure constraint | Attribute '@format' is required in this context. |
| 357 | FX-SCH-A-000022 | - | blocking | Factur-X profile/structure constraint | Value of '@format' is not allowed. |
| 358 | FX-SCH-A-000189 | - | blocking | Factur-X profile/structure constraint | Element 'ram:LineTotalAmount' must occur exactly 1 times. |
| 359 | FX-SCH-A-000190 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ChargeTotalAmount' may occur at maximum 1 times. |
| 360 | FX-SCH-A-000191 | - | blocking | Factur-X profile/structure constraint | Element 'ram:AllowanceTotalAmount' may occur at maximum 1 times. |
| 361 | FX-SCH-A-000041 | - | blocking | Factur-X profile/structure constraint | Element 'ram:TaxBasisTotalAmount' must occur exactly 1 times. |
| 362 | FX-SCH-A-000042 | - | blocking | Factur-X profile/structure constraint | Element variant 'ram:TaxTotalAmount[@currencyID=../../ram:InvoiceCurrencyCode]' may occur at maximum 1 times. |
| 363 | FX-SCH-A-000192 | - | blocking | Factur-X profile/structure constraint | Element variant 'ram:TaxTotalAmount[@currencyID=../../ram:TaxCurrencyCode]' may occur at maximum 1 times. |
| 364 | FX-SCH-A-000290 | - | blocking | Factur-X profile/structure constraint | Element 'ram:RoundingAmount' may occur at maximum 1 times. |
| 365 | FX-SCH-A-000043 | - | blocking | Factur-X profile/structure constraint | Element 'ram:GrandTotalAmount' must occur exactly 1 times. |
| 366 | FX-SCH-A-000193 | - | blocking | Factur-X profile/structure constraint | Element 'ram:TotalPrepaidAmount' may occur at maximum 1 times. |
| 367 | FX-SCH-A-000044 | - | blocking | Factur-X profile/structure constraint | Element 'ram:DuePayableAmount' must occur exactly 1 times. |
| 368 | FX-SCH-A-000045 | - | blocking | Factur-X profile/structure constraint | Value of '@currencyID' is not allowed. |
| 369 | FX-SCH-A-000045 | - | blocking | Factur-X profile/structure constraint | Value of '@currencyID' is not allowed. |
| 370 | FX-SCH-A-000020 | - | blocking | Factur-X profile/structure constraint | Element 'ram:TypeCode' must occur exactly 1 times. |
| 371 | FX-SCH-A-000291 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Information' may occur at maximum 1 times. |
| 372 | FX-SCH-A-000194 | - | blocking | Factur-X profile/structure constraint | Element 'ram:PayeePartyCreditorFinancialAccount' may occur at maximum 1 times. |
| 373 | FX-SCH-A-000019 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ID' must occur exactly 1 times. |
| 374 | FX-SCH-A-000292 | - | blocking | Factur-X profile/structure constraint | Element 'ram:BICID' must occur exactly 1 times. |
| 375 | FX-SCH-A-000195 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IBANID' must occur exactly 1 times. |
| 376 | FX-SCH-A-000023 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:TypeCode' is not allowed. |
| 377 | FX-SCH-A-000196 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:TaxCurrencyCode' is not allowed. |
| 378 | FX-SCH-A-000266 | - | blocking | Factur-X profile/structure constraint | Element 'ram:AssociatedDocumentLineDocument' must occur exactly 1 times. |
| 379 | FX-SCH-A-000267 | - | blocking | Factur-X profile/structure constraint | Element 'ram:SpecifiedTradeProduct' must occur exactly 1 times. |
| 380 | FX-SCH-A-000268 | - | blocking | Factur-X profile/structure constraint | Element 'ram:SpecifiedLineTradeAgreement' must occur exactly 1 times. |
| 381 | FX-SCH-A-000269 | - | blocking | Factur-X profile/structure constraint | Element 'ram:SpecifiedLineTradeDelivery' must occur exactly 1 times. |
| 382 | FX-SCH-A-000270 | - | blocking | Factur-X profile/structure constraint | Element 'ram:LineID' must occur exactly 1 times. |
| 383 | FX-SCH-A-000271 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IncludedNote' may occur at maximum 1 times. |
| 384 | FX-SCH-A-000160 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Content' must occur exactly 1 times. |
| 385 | FX-SCH-A-000272 | - | blocking | Factur-X profile/structure constraint | Element 'ram:NetPriceProductTradePrice' must occur exactly 1 times. |
| 386 | FX-SCH-A-000273 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ChargeAmount' must occur exactly 1 times. |
| 387 | FX-SCH-A-000274 | - | blocking | Factur-X profile/structure constraint | Element variant 'ram:AppliedTradeAllowanceCharge[ram:ChargeIndicator/udt:Indicator="false"]' may occur at maximum 1 times. |
| 388 | FX-SCH-A-000183 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ChargeIndicator' must occur exactly 1 times. |
| 389 | FX-SCH-A-000184 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ActualAmount' must occur exactly 1 times. |
| 390 | FX-SCH-A-000275 | - | blocking | Factur-X profile/structure constraint | Value of '@unitCode' is not allowed. |
| 391 | FX-SCH-A-000273 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ChargeAmount' must occur exactly 1 times. |
| 392 | FX-SCH-A-000275 | - | blocking | Factur-X profile/structure constraint | Value of '@unitCode' is not allowed. |
| 393 | FX-SCH-A-000276 | - | blocking | Factur-X profile/structure constraint | Element 'ram:BilledQuantity' must occur exactly 1 times. |
| 394 | FX-SCH-A-000275 | - | blocking | Factur-X profile/structure constraint | Value of '@unitCode' is not allowed. |
| 395 | FX-SCH-A-000278 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ApplicableTradeTax' must occur exactly 1 times. |
| 396 | FX-SCH-A-000279 | - | blocking | Factur-X profile/structure constraint | Element 'ram:SpecifiedTradeSettlementLineMonetarySummation' must occur exactly 1 times. |
| 397 | FX-SCH-A-000293 | - | blocking | Factur-X profile/structure constraint | Element 'ram:AdditionalReferencedDocument' may occur at maximum 1 times. |
| 398 | FX-SCH-A-000175 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ReceivableSpecifiedTradeAccountingAccount' may occur at maximum 1 times. |
| 399 | FX-SCH-A-000029 | - | blocking | Factur-X profile/structure constraint | Element 'ram:IssuerAssignedID' must occur exactly 1 times. |
| 400 | FX-SCH-A-000020 | - | blocking | Factur-X profile/structure constraint | Element 'ram:TypeCode' must occur exactly 1 times. |
| 401 | FX-SCH-A-000282 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:ReferenceTypeCode' is not allowed. |
| 402 | FX-SCH-A-000023 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:TypeCode' is not allowed. |
| 403 | FX-SCH-A-000020 | - | blocking | Factur-X profile/structure constraint | Element 'ram:TypeCode' must occur exactly 1 times. |
| 404 | FX-SCH-A-000178 | - | blocking | Factur-X profile/structure constraint | Element 'ram:CategoryCode' must occur exactly 1 times. |
| 405 | FX-SCH-A-000179 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:CategoryCode' is not allowed. |
| 406 | FX-SCH-A-000023 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:TypeCode' is not allowed. |
| 407 | FX-SCH-A-000021 | - | blocking | Factur-X profile/structure constraint | Attribute '@format' is required in this context. |
| 408 | FX-SCH-A-000022 | - | blocking | Factur-X profile/structure constraint | Value of '@format' is not allowed. |
| 409 | FX-SCH-A-000021 | - | blocking | Factur-X profile/structure constraint | Attribute '@format' is required in this context. |
| 410 | FX-SCH-A-000022 | - | blocking | Factur-X profile/structure constraint | Value of '@format' is not allowed. |
| 411 | FX-SCH-A-000183 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ChargeIndicator' must occur exactly 1 times. |
| 412 | FX-SCH-A-000184 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ActualAmount' must occur exactly 1 times. |
| 413 | FX-SCH-A-000186 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:ReasonCode' is not allowed. |
| 414 | FX-SCH-A-000183 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ChargeIndicator' must occur exactly 1 times. |
| 415 | FX-SCH-A-000184 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ActualAmount' must occur exactly 1 times. |
| 416 | FX-SCH-A-000376 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:ReasonCode[not (@listID)]' is not allowed. |
| 417 | FX-SCH-A-000189 | - | blocking | Factur-X profile/structure constraint | Element 'ram:LineTotalAmount' must occur exactly 1 times. |
| 418 | FX-SCH-A-000030 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Name' must occur exactly 1 times. |
| 419 | FX-SCH-A-000187 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Description' may occur at maximum 1 times. |
| 420 | FX-SCH-A-000294 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Description' must occur exactly 1 times. |
| 421 | FX-SCH-A-000295 | - | blocking | Factur-X profile/structure constraint | Element 'ram:Value' must occur exactly 1 times. |
| 422 | FX-SCH-A-000296 | - | blocking | Factur-X profile/structure constraint | Attribute '@listID' is required in this context. |
| 423 | FX-SCH-A-000297 | - | blocking | Factur-X profile/structure constraint | Value of '@listID' is not allowed. |
| 424 | FX-SCH-A-000037 | - | blocking | Factur-X profile/structure constraint | Attribute '@schemeID' is required in this context. |
| 425 | FX-SCH-A-000031 | - | blocking | Factur-X profile/structure constraint | Value of '@schemeID' is not allowed. |
| 426 | FX-SCH-A-000019 | - | blocking | Factur-X profile/structure constraint | Element 'ram:ID' must occur exactly 1 times. |
| 427 | FX-SCH-A-000026 | - | blocking | Factur-X profile/structure constraint | Value of 'ram:ID' is not allowed. |
