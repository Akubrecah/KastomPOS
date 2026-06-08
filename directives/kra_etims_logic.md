# KRA eTIMS Compliance Logic (SOP)

## Overview
This module handles compliance with the Kenya Revenue Authority (KRA) eTIMS/TIMS requirements for electronic tax invoicing.

## Data Structure
Each KRA-compliant invoice must contain:
1. **Business PIN**: Your tax identification number.
2. **Device ID**: Assigned by KRA for your specific POS terminal.
3. **Control Unit Number**: Unique identifier for the transaction.
4. **Digital Signature**: A hash generated from the invoice details and a private key.
5. **QR Code Data**: URL for verifying the invoice on the KRA portal.

## Workflow
1. **Validation**: Check if `kraIntegration` is enabled in settings.
2. **Data Preparation**: Format the sale items according to the eTIMS schema (HS codes, tax categories).
3. **Signing**: Call the `signInvoice` function to generate the digital signature.
4. **Submission**: 
   - **Online**: Send directly to the KRA middleware endpoint.
   - **Offline**: Store in `db.kraQueue` and retry once connectivity is restored.
5. **Receipt Printing**: Append the KRA Control Unit Number and QR code to the bottom of the thermal/A4 receipt.

## Tax Categories (Kenya)
- **A**: Standard Rate (16%)
- **B**: Zero Rated (0%)
- **C**: Exempt (0%)
- **D**: Non-VAT (8%)
- **E**: Export (0%)
