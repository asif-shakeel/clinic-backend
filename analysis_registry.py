ANALYSES = {
    "basic_clinic": {
        "label": "Basic Clinic Analysis",
        "outputs": [
            "Patient counts by insurance",
            "Average service charge"
        ],
        "files": {
            "patients": {
                "required_columns": [
                    "patient_id", "insurance", "dob", "city", "state"
                ]
            },
            "visits": {
                "required_columns": [
                    "patient_id", "visit_date", "service_charge"
                ]
            },
        },
    },

    "clinic_outcomes": {
        "label": "Clinic Outcomes Analysis",
        "outputs": [
            "Outcome trends over time",
            "Pain vs mobility correlation",
            "Service charge by outcome"
        ],
        "files": {
            "patients": {
                "required_columns": [
                    "patient_id", "insurance", "dob"
                ]
            },
            "visits": {
                "required_columns": [
                    "patient_id", "visit_date", "service_charge"
                ]
            },
            "metrics": {
                "required_columns": [
                    "patient_id",
                    "metric_date",
                    "pain_score",
                    "mobility_score"
                ]
            },
        },
    },
}
