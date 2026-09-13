from tools.patient_db_tool import get_patient_by_id
from tools.audit_log import log_action

class NaivePatientAgent:

    def __init__(self, name="NaivePatientAgent"):
        self.name = name

    def get_record_for(self, patient_id, purpose="general"):
        log_action(self.name, "lookup_patient_NAIVE", {"patient_id": patient_id, "purpose": purpose})
        raw_record = get_patient_by_id(patient_id)
        if raw_record is None:
            return None
        # No sanitization applied - full record returned regardless of purpose
        log_action(
            self.name, "lookup_patient_complete_NAIVE",
            {"patient_id": patient_id, "purpose": purpose},
            result_summary=f"returned fields: {list(raw_record.keys())}"
        )
        return raw_record