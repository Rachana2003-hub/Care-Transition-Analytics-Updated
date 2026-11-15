
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from io import BytesIO

st.set_page_config(page_title="Care Transition Analytics", page_icon="🧭", layout="wide")
st.title("🧭 Care Transition Efficiency & Placement Outcome Analytics")
st.caption("UAC care pipeline monitoring | CBP custody → HHS care → sponsor discharge")
st.info("This dashboard analyzes aggregate program counts. Ratios are operational indicators, not individual child outcomes, causal estimates, or direct measures of reunification quality.")

ROOT = Path(__file__).resolve().parent
DATA_CANDIDATES = [ROOT / "data" / "uac_care_data.csv", ROOT / "uac_care_data.csv"]
REQUIRED = {
    "Date": ["Date", "date", "Reporting Date", "reporting_date"],
    "Children apprehended and placed in CBP custody*": [
        "Children apprehended and placed in CBP custody*",
        "Children apprehended and placed in CBP custody",
        "Apprehensions", "Daily intake"
    ],
    "Children in CBP custody": ["Children in CBP custody", "CBP custody"],
    "Children transferred out of CBP custody": [
        "Children transferred out of CBP custody", "Transfers", "Children transferred"
    ],
    "Children in HHS Care": ["Children in HHS Care", "HHS care"],
    "Children discharged from HHS Care": [
        "Children discharged from HHS Care", "Discharges", "HHS discharges"
    ],
}
NUMERIC = [k for k in REQUIRED if k != "Date"]

def read_csv_checked(source):
    """Read uploaded or packaged CSV and return normalized dataframe + validation notes."""
    if hasattr(source, "getvalue"):
        payload = source.getvalue()
        name = getattr(source, "name", "uploaded file")
    else:
        path = Path(source)
        name = path.name
        if not path.exists():
            raise ValueError(f"Dataset not found: {path}. Upload a CSV or add data/uac_care_data.csv to the repository.")
        payload = path.read_bytes()

    if not payload or not payload.strip():
        raise ValueError(f"'{name}' is empty. Upload the original CSV containing the header row and data.")
    try:
        df = pd.read_csv(BytesIO(payload))
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(BytesIO(payload), encoding="latin-1")
        except Exception as exc:
            raise ValueError(f"'{name}' is not a readable CSV file: {exc}")
    except pd.errors.EmptyDataError:
        raise ValueError(f"'{name}' has no columns. The file is empty or has no CSV header.")
    except Exception as exc:
        raise ValueError(f"Could not read '{name}' as CSV. Check the file format. Details: {exc}")

    if df.empty and len(df.columns) == 0:
        raise ValueError(f"'{name}' contains no columns. Please upload a valid CSV.")
    if len(df.columns) == 1 and str(df.columns[0]).lower().startswith("unnamed"):
        raise ValueError(f"'{name}' does not contain the expected CSV columns.")

    rename = {}
    for standard, aliases in REQUIRED.items():
        found = next((col for col in df.columns if str(col).strip() in aliases), None)
        if found is not None:
            rename[found] = standard
    df = df.rename(columns=rename)

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError("Missing required column(s): " + ", ".join(missing) +
                         ". Please upload the UAC program CSV with all six required fields.")

    notes = []
    original_rows = len(df)
    df = df.dropna(how="all").copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    invalid_dates = int(df["Date"].isna().sum())
    if invalid_dates:
        notes.append(f"{invalid_dates} row(s) with invalid or missing dates were excluded.")
    df = df.dropna(subset=["Date"]).copy()

    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")
    bad_numeric = {c: int(df[c].isna().sum()) for c in NUMERIC}
    bad_numeric = {k:v for k,v in bad_numeric.items() if v}
    if bad_numeric:
        notes.append("Missing or non-numeric values found: " + "; ".join(f"{k}: {v}" for k,v in bad_numeric.items()) + ". Ratios omit unavailable values.")
    negative = {c:int((df[c] < 0).sum()) for c in NUMERIC if (df[c] < 0).any()}
    if negative:
        notes.append("Negative counts detected: " + ", ".join(negative.keys()) + ". Please verify source values.")
    duplicates = int(df.duplicated(subset=["Date"]).sum())
    if duplicates:
        notes.append(f"{duplicates} duplicate date row(s) found; keeping the last row for each date.")
        df = df.sort_values("Date").drop_duplicates("Date", keep="last")
    if df.empty:
        raise ValueError("No usable dated records remain after validation. Check the Date column.")
    df = df.sort_values("Date").reset_index(drop=True)
    if original_rows:
        notes.insert(0, f"Loaded {len(df):,} usable dated record(s) from '{name}'.")
    return df, notes

st.sidebar.header("Data")
uploaded = st.sidebar.file_uploader("Upload a replacement CSV (optional)", type=["csv"])
source = uploaded if uploaded is not None else next((p for p in DATA_CANDIDATES if p.exists()), DATA_CANDIDATES[0])

try:
    df, validation_notes = read_csv_checked(source)
except ValueError as err:
    st.error(f"Dataset validation failed: {err}")
    st.markdown("**How to fix:** Upload the original UAC CSV with all six required columns, or ensure the repository contains `data/uac_care_data.csv`.")
    st.stop()
except Exception as err:
    st.error(f"Unexpected dataset loading error: {err}")
    st.stop()

with st.expander("Data validation report", expanded=False):
    for note in validation_notes:
        st.warning(note) if ("Negative" in note or "Missing" in note or "invalid" in note) else st.info(note)
    st.success("Required columns and date parsing validated.")

st.sidebar.header("Filters")
min_date, max_date = df.Date.min().date(), df.Date.max().date()
date_range = st.sidebar.date_input("Reporting date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
if isinstance(date_range, (tuple,list)) and len(date_range)==2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    view = df[df.Date.between(start,end)].copy()
else:
    view = df.copy()
if view.empty:
    st.warning("No records exist in the selected date range.")
    st.stop()

ratio_mode = st.sidebar.radio("Ratio display", ["Percentage", "Decimal"], horizontal=True)
rolling_n = st.sidebar.slider("Rolling average (records)", 3, 30, 7)
transfer_threshold = st.sidebar.slider("Transfer indicator alert threshold (%)", 0, 100, 20)
discharge_threshold = st.sidebar.slider("Discharge indicator alert threshold (%)", 0, 20, 5)

C = {k:k for k in NUMERIC}
intake, cbp, transfers, hhs, discharges = [C[k] for k in NUMERIC]
view["transfer_pct"] = 100 * view[transfers] / view[cbp].replace(0,np.nan)
view["discharge_pct"] = 100 * view[discharges] / view[hhs].replace(0,np.nan)
view["pressure"] = view[intake] - view[discharges]
view["transfer_roll"] = view["transfer_pct"].rolling(rolling_n,min_periods=1).mean()
view["discharge_roll"] = view["discharge_pct"].rolling(rolling_n,min_periods=1).mean()

def nfmt(x): return "—" if pd.isna(x) else f"{x:,.0f}"
def pfmt(x):
    if pd.isna(x): return "—"
    return f"{x:.2f}%" if ratio_mode=="Percentage" else f"{x/100:.4f}"
def lastval(s):
    s=s.dropna()
    return float(s.iloc[-1]) if len(s) else np.nan

st.caption(f"Coverage: {view.Date.min():%d %b %Y} – {view.Date.max():%d %b %Y} | {len(view):,} reporting records")
st.subheader("1. Program snapshot")
latest=view.iloc[-1]
k1,k2,k3,k4,k5=st.columns(5)
k1.metric("CBP custody",nfmt(latest[cbp]))
k2.metric("HHS care",nfmt(latest[hhs]))
k3.metric("Daily intake",nfmt(latest[intake]))
k4.metric("Daily transfers",nfmt(latest[transfers]))
k5.metric("Daily discharges",nfmt(latest[discharges]))

st.subheader("2. Pipeline and transition indicators")
m1,m2,m3=st.columns(3)
m1.metric("Transfer flow / CBP stock",pfmt(lastval(view.transfer_pct)))
m2.metric("Discharge flow / HHS stock",pfmt(lastval(view.discharge_pct)))
period_ratio = 100*view[discharges].sum()/view[intake].sum() if view[intake].sum() else np.nan
m3.metric("Selected-period discharges / intake",pfmt(period_ratio))
st.caption("These are descriptive flow-to-stock or cross-stage volume indicators. They are not cohort transition probabilities, average processing times, or direct measures of placement success.")

pipe=pd.DataFrame({"Stage":["CBP custody stock","Transfers out of CBP (daily flow)","HHS care stock","HHS discharges (daily flow)"],
                   "Children":[latest[cbp],latest[transfers],latest[hhs],latest[discharges]]})
fig=px.bar(pipe,x="Stage",y="Children",color="Stage",title="Latest selected-date pipeline measures")
fig.update_layout(showlegend=False)
st.plotly_chart(fig,use_container_width=True)

st.subheader("3. Transfer and discharge trends")
choice=st.radio("Select indicator",["Transfer indicator","Discharge indicator"],horizontal=True)
field,rolling,title=("transfer_pct","transfer_roll","Daily transfers ÷ CBP custody stock") if choice=="Transfer indicator" else ("discharge_pct","discharge_roll","Daily HHS discharges ÷ HHS care stock")
fig=go.Figure()
fig.add_trace(go.Scatter(x=view.Date,y=view[field],mode="lines+markers",name="Daily indicator"))
fig.add_trace(go.Scatter(x=view.Date,y=view[rolling],mode="lines",name=f"{rolling_n}-record rolling average"))
fig.update_layout(title=title,xaxis_title="Date",yaxis_title="Percent",hovermode="x unified")
st.plotly_chart(fig,use_container_width=True)

st.subheader("4. Care-load and flow trends")
fig=go.Figure()
fig.add_trace(go.Scatter(x=view.Date,y=view[cbp],name="CBP custody",mode="lines"))
fig.add_trace(go.Scatter(x=view.Date,y=view[hhs],name="HHS care",mode="lines"))
fig.update_layout(title="Reported active care loads",xaxis_title="Date",yaxis_title="Children")
st.plotly_chart(fig,use_container_width=True)

monthly=view.set_index("Date").resample("MS").agg({intake:"sum",transfers:"sum",discharges:"sum"}).reset_index()
monthly=monthly.rename(columns={intake:"Intake",transfers:"Transfers",discharges:"Discharges"})
fig=px.line(monthly,x="Date",y=["Intake","Transfers","Discharges"],markers=True,title="Monthly intake, transfers and discharges")
st.plotly_chart(fig,use_container_width=True)

st.subheader("5. System pressure and potential bottlenecks")
st.caption("Intake minus HHS discharges is a cross-stage pressure proxy, not a reconciled backlog balance.")
fig=px.bar(view,x="Date",y="pressure",color="pressure",title="Daily intake minus HHS discharges")
fig.add_hline(y=0,line_dash="dash",line_color="black")
st.plotly_chart(fig,use_container_width=True)

st.subheader("6. Weekday pattern")
weekday=view.copy()
weekday["Weekday"]=weekday.Date.dt.day_name()
order=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
ws=weekday.groupby("Weekday").agg(Mean_intake=(intake,"mean"),Mean_transfers=(transfers,"mean"),Mean_discharges=(discharges,"mean"),Records=("Date","count")).reindex(order).dropna(how="all").reset_index()
fig=px.bar(ws,x="Weekday",y=["Mean_transfers","Mean_discharges"],barmode="group",title="Mean daily transfers and discharges by weekday")
st.plotly_chart(fig,use_container_width=True)
st.dataframe(ws,use_container_width=True)

st.subheader("7. Visual threshold alerts")
alerts=[]
if lastval(view.transfer_pct)<transfer_threshold: alerts.append(f"Latest transfer indicator is below {transfer_threshold}%.")
if lastval(view.discharge_pct)<discharge_threshold: alerts.append(f"Latest discharge indicator is below {discharge_threshold}%.")
if view.pressure.tail(7).mean()>0: alerts.append("Mean intake exceeded HHS discharges over the last seven selected records.")
if alerts:
    for alert in alerts: st.warning(alert)
else:
    st.success("No configured threshold alerts for the latest selected period.")

st.subheader("8. Data quality and export")
quality=pd.DataFrame({"Field":NUMERIC,"Missing values":[int(view[c].isna().sum()) for c in NUMERIC],
                      "Negative values":[int((view[c]<0).sum()) for c in NUMERIC]})
st.dataframe(quality,use_container_width=True)
st.download_button("Download filtered analysis CSV",view.to_csv(index=False).encode("utf-8"),"care_transition_filtered_analysis.csv","text/csv")
with st.expander("Preview source data"):
    st.dataframe(view.tail(20),use_container_width=True)

st.caption("For actual transfer delays, HHS length of stay and cohort-based placement outcomes, the dataset must include linked case-level stage timestamps. Aggregate daily counts cannot establish individual outcomes or causal effects.")
