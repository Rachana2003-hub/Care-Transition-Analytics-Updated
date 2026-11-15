# Resubmission testing record

## Valid dataset
- Input: packaged `data/uac_care_data.csv`, cleaned from the supplied HHS UAC CSV.
- Expected: all six required columns recognized; valid dates parsed; data displayed in dashboard.
- Outcome: validation logic designed to accept a non-empty CSV with the required fields.

## Empty file
- Expected: clear message that the uploaded file is empty or has no CSV header.
- Outcome: rejected before chart rendering.

## Missing required columns
- Expected: error lists the missing fields and requests the UAC CSV with all six required fields.
- Outcome: rejected before chart rendering.

## Incorrect file format
- Expected: clear CSV read/format error.
- Outcome: rejected before chart rendering.

## Invalid dates / numeric values
- Expected: invalid-date rows excluded and data-quality notes shown; non-numeric count values reported as missing.
- Outcome: warning shown; ratios omit unavailable values.

## Duplicate dates
- Expected: duplicate dates reported; last record per date retained.
- Outcome: warning shown and dates de-duplicated.

Note: Run these checks in the deployed Streamlit app using the file uploader before claiming live deployment acceptance. This document describes expected validation behavior; it is not a claim that every test was executed in the hosted environment.
