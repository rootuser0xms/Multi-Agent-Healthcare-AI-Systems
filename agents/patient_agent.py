from tools.patient_db_tool import get_patient_by_id, get_patients_by_condition
from tools.phi_sanitizer import sanitize_patient_record
from tools.audit_log import log_action

class PatientAgent:

    def __init__(self, name="PatientAgent"):
        self.name = name

    def get_record_for(self, patient_id, purpose="general"):
        log_action(self.name, "lookup_patient", {"patient_id": patient_id, "purpose": purpose})

        raw_record = get_patient_by_id(patient_id)
        if raw_record is None:
            log_action(self.name, "lookup_patient_not_found", {"patient_id": patient_id})
            return None

        sanitized = sanitize_patient_record(raw_record, purpose=purpose)

        log_action(
            self.name, "lookup_patient_complete",
            {"patient_id": patient_id, "purpose": purpose},
            result_summary=f"returned fields: {list(sanitized.keys())}"
        )
        return sanitized


if __name__ == "__main__":
    agent = PatientAgent()

    print("Full clinical purpose:")
    print(agent.get_record_for("P0001", purpose="full_clinical"))

    print("\nBooking purpose (should NOT include name/dob):")
    print(agent.get_record_for("P0001", purpose="booking"))

    print("\nInsurance verification purpose:")
    print(agent.get_record_for("P0001", purpose="insurance_verification"))