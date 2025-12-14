import os
import pandas as pd
from scipy.stats import ttest_ind


# ---------- LOAD ----------
def load_data(data_dir):
    patients = pd.read_csv(os.path.join(data_dir, "patients.csv"))
    visits = pd.read_csv(os.path.join(data_dir, "visits.csv"))
    metrics = pd.read_csv(os.path.join(data_dir, "metrics.csv"))

    # Dates (normalized names)
    visits["visitdate"] = pd.to_datetime(visits["visitdate"])
    metrics["metricdate"] = pd.to_datetime(metrics["metricdate"])
    patients["dob"] = pd.to_datetime(patients["dob"])

    return patients, visits, metrics


# ---------- MERGE ----------
def merge_data(patients, visits, metrics):
    visits_full = visits.merge(patients, on="patientid", how="left")

    full_data = visits_full.merge(
        metrics,
        left_on=["patientid", "visitdate"],
        right_on=["patientid", "metricdate"],
        how="left"
    )
    return full_data


# ---------- FILTER ----------
def filter_by_date(df, start_date=None, end_date=None):
    if start_date:
        df = df[df["visitdate"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["visitdate"] <= pd.to_datetime(end_date)]
    return df


# ---------- AGGREGATES ----------
def compute_aggregates(df):
    return {
        "avg_charge_by_insurance":
            df.groupby("insurance")["servicecharge"].mean().reset_index(),

        "revenue_by_city":
            df.groupby("city")["servicecharge"].sum().reset_index(),

        "avg_pain_by_insurance":
            df.groupby("insurance")["painscore"].mean().reset_index(),

        "visit_counts":
            df.groupby("patientid").size().reset_index(name="visitcount"),
    }


# ---------- STATS ----------
def run_stats(df):
    stats = {}

    stats["pain_mobility_corr"] = (
        df[["painscore", "mobilityscore"]].corr()
    )

    bluecross = df.loc[df["insurance"] == "bluecross", "servicecharge"]
    aetna = df.loc[df["insurance"] == "aetna", "servicecharge"]

    if len(bluecross) >= 2 and len(aetna) >= 2:
        t_stat, p_value = ttest_ind(bluecross, aetna, equal_var=False)
        stats["charge_ttest"] = {
            "t_stat": float(t_stat),
            "p_value": float(p_value),
        }
    else:
        stats["charge_ttest"] = {
            "error": "Not enough data for t-test"
        }

    return stats

def run_basic_clinic(data_dir, out_dir, start_date=None, end_date=None):
    patients, visits, metrics = load_data(data_dir)
    full = merge_data(patients, visits, metrics)
    full = filter_by_date(full, start_date, end_date)

    results = {
        "avg_charge_by_insurance":
            full.groupby("insurance")["servicecharge"].mean().reset_index(),

        "revenue_by_city":
            full.groupby("city")["servicecharge"].sum().reset_index(),

        "visit_counts":
            full.groupby("patientid").size().reset_index(name="visit_count"),
    }

    save_results(results, out_dir)

def run_clinic_outcomes(data_dir, out_dir, start_date=None, end_date=None):
    patients, visits, metrics = load_data(data_dir)
    full = merge_data(patients, visits, metrics)
    full = filter_by_date(full, start_date, end_date)

    results = {
        "avg_pain_by_insurance":
            full.groupby("insurance")["painscore"].mean().reset_index(),

        "pain_mobility_corr":
            full[["painscore", "mobilityscore"]].corr().reset_index(),
    }

    save_results(results, out_dir)

# ---------- SAVE ----------
def save_results(results, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, df in results.items():
        df.to_csv(os.path.join(out_dir, f"{name}.csv"), index=False)


# ---------- MAIN ----------
def run_analysis(analysis_key, data_dir, out_dir, start_date=None, end_date=None):
    if analysis_key == "basic_clinic":
        return run_basic_clinic(data_dir, out_dir, start_date, end_date)

    if analysis_key == "clinic_outcomes":
        return run_clinic_outcomes(data_dir, out_dir, start_date, end_date)

    raise ValueError(f"Unknown analysis: {analysis_key}")

