import json

PATIENTS_PATH = "data/patients.json"

def load_patients():
    with open(PATIENTS_PATH) as f:
        return json.load(f)

def get_patient_by_id(patient_id):
    """Look up a single patient's full record by ID."""
    patients = load_patients()
    for p in patients:
        if p["patient_id"] == patient_id:
            return p
    return None

def get_patients_by_condition(condition):
    """Find all patients with a given condition"""
    patients = load_patients()
    return [p for p in patients if condition in p["conditions"]]