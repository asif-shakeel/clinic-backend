# analysis_registry.py

ANALYSES = {
    "basic_clinic": {
        "label": "Basic Clinic Analysis",
        "files": {
            "patients": {
                "required_columns": [
                    "Patient ID",
                    "Insurance",
                    "DOB",
                    "City",
                    "State",
                ]
            },
            "visits": {
                "required_columns": [
                    "Patient ID",
                    "Visit Date",
                    "Service Charge",
                ]
            },
            "metrics": {
                "required_columns": [
                    "Patient ID",
                    "Metric Date",
                    "Pain Score",
                    "Mobility Score",
                ]
            },
        }
    }
}
