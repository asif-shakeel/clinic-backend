# analysis_registry.py

ANALYSES = {
    "basic_clinic": {
        "label": "Basic Clinic Analysis",
        "files": {
            "patients": {
                "required_columns": [
                    "patient_id",
                    "insurance",
                    "dob",
                    "city",
                    "state",
                ]
            },
            "visits": {
                "required_columns": [
                    "patient_id",
                    "visit_date",
                    "service_charge",
                ]
            },
            "metrics": {
                "required_columns": [
                    "patient_id",
                    "metric_date",
                    "pain_score",
                    "mobility_score",
                ]
            },
        }
    }
}
