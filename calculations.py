import os
import os, json, html
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List

import numpy as np
import pandas as pd
from scipy import sparse



BASE_DIR = "/Users/asif/Documents/Data_and_Analytics"
DATA_DIR = OUT_DIR  = os.path.join(BASE_DIR, "sample_data")
OUT_DIR  = os.path.join(BASE_DIR, "outputs")



patients = pd.read_csv(os.path.join(DATA_DIR, "patients.csv"))
visits = pd.read_csv(os.path.join(DATA_DIR,"visits.csv"))
metrics = pd.read_csv(os.path.join(DATA_DIR,"metrics.csv"))


visits["VisitDate"] = pd.to_datetime(visits["VisitDate"])
metrics["MetricDate"] = pd.to_datetime(metrics["MetricDate"])
patients["DOB"] = pd.to_datetime(patients["DOB"])


visits_full = visits.merge(patients, on="PatientID", how="left")

full_data = visits_full.merge(
    metrics,
    left_on=["PatientID", "VisitDate"],
    right_on=["PatientID", "MetricDate"],
    how="left"
)

avg_charge_by_insurance = (
    full_data
    .groupby("Insurance")["ServiceCharge"]
    .mean()
    .reset_index()
)

revenue_by_city = (
    full_data
    .groupby("City")["ServiceCharge"]
    .sum()
    .reset_index()
)

avg_pain_by_insurance = (
    full_data
    .groupby("Insurance")["PainScore"]
    .mean()
    .reset_index()
)

visit_counts = (
    full_data
    .groupby("PatientID")
    .size()
    .reset_index(name="VisitCount")
)

correlation = full_data[["PainScore", "MobilityScore"]].corr()

from scipy.stats import ttest_ind

bluecross = full_data.loc[
    full_data["Insurance"] == "BlueCross", "ServiceCharge"
]

aetna = full_data.loc[
    full_data["Insurance"] == "Aetna", "ServiceCharge"
]

t_stat, p_value = ttest_ind(bluecross, aetna, equal_var=False)

avg_charge_by_insurance.to_csv(os.path.join(OUT_DIR,
    "avg_charge_by_insurance.csv"), index=False
)

revenue_by_city.to_csv(os.path.join(OUT_DIR,
    "revenue_by_city.csv"), index=False
)
