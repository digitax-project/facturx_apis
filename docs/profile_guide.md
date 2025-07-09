# Factur-X Profile Guide

## Overview of Factur-X Profiles

Factur-X/ZUGFeRD 2.0 defines several profiles (or conformance levels) with increasing capabilities:

1. **Minimum**: Contains only the most basic information required for accounting
2. **Basic WL** (Basic Without Lines): Contains invoice details but without line items
3. **Basic**: Contains invoice details with line items
4. **EN16931**: Complies with the European standard EN 16931 for electronic invoicing
5. **Extended**: Includes all EN16931 requirements plus additional business processes

## What Each Profile Validates

### XSD Validation

XML Schema Definition (XSD) validation checks that the XML file:
- Has the correct structure
- Contains required elements in the right places
- Has properly formatted data types (dates, numbers, codes, etc.)
- Follows the rules defined in the Factur-X/ZUGFeRD specification

For each profile level, a specific XSD file defines the validation rules:

- Minimum: `facturx-minimum/Factur-X_1.07.2_MINIMUM.xsd`
- Basic WL: `facturx-basicwl/Factur-X_1.07.2_BASICWL.xsd`
- Basic: `facturx-basic/Factur-X_1.07.2_BASIC.xsd`
- EN16931: `facturx-en16931/Factur-X_1.07.2_EN16931.xsd`
- Extended: `facturx-extended/Factur-X_1.07.2_EXTENDED.xsd`

### Content Validation

Beyond the XSD validation, we also validate specific business requirements:

#### Minimum Profile

- Payment reference information
- Seller tax registration information

#### Basic WL Profile (includes all from Minimum)

- Buyer name information
- Additional party details

#### Basic Profile (includes all from Basic WL)

- Line item details
- Delivery date information
- Product descriptions

#### EN16931 Profile (includes all from Basic)

- Buyer reference information
- Payment terms
- VAT breakdown
- Allowances and charges
- All fields required by the European standard

#### Extended Profile (includes all from EN16931)

Extended profile includes all EN16931 requirements plus additional fields for:
- Detailed delivery information
- Payment instructions
- Additional party information
- Order reference details
- Advanced pricing structures

## Using the API for Validation

When using the `/facturx-xmlcheck` endpoint, you can:

1. Pass a Factur-X XML file for validation
2. Specify the profile level or let it autodetect
3. Enable detailed validation to check for specific field requirements

For example:

```bash
curl -X POST "http://localhost:6969/facturx-xmlcheck" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "xml_file=@invoice.xml" \
  -F "level=en16931" \
  -F "detailed_validation=true"
```

This will validate the XML against both the XSD schema and the business requirements for the EN16931 profile.

## Common Validation Issues

1. **Missing Required Fields**: The most common issue is missing required fields for a specific profile.

2. **Incorrect Format**: Date formats, currency codes, or country codes in incorrect format.

3. **Invalid References**: Referenced documents (PO numbers, etc.) without proper structure.

4. **Tax Calculations**: Incorrect tax calculations or missing tax breakdown information.

When validation fails, the API provides specific error messages to help identify and fix the issues.
