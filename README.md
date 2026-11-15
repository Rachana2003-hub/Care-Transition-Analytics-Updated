# Care Transition Efficiency & Placement Outcome Analytics

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub / Streamlit deployment
- Repository root must contain `app.py` and `requirements.txt`.
- The cleaned CSV must be at `data/uac_care_data.csv`.
- In Streamlit Community Cloud select branch `main` and main file `app.py`.

## CSV validation
The application checks for empty files, unreadable/non-CSV files, missing required columns, invalid dates, missing/non-numeric counts, negative counts and duplicate dates. It displays actionable error messages and a data validation report.

## Metrics
- Transfer flow-to-stock indicator = daily transfers / same-day CBP custody stock.
- Discharge flow-to-stock indicator = daily HHS discharges / same-day HHS care stock.
- Selected-period discharge-to-intake volume ratio = sum of HHS discharges / sum of apprehensions.
- Intake-discharge pressure proxy = daily apprehensions - daily HHS discharges.

These measures are descriptive. They are not cohort transition probabilities, elapsed-time measures, placement success rates or reconciled backlog balances.
