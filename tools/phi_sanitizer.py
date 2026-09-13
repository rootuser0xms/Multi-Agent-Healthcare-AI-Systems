def sanitize_patient_record(record, purpose="general"):

    if record is None:
        return None

    if purpose == "booking":
       
        return {
            "patient_id": record["patient_id"],
            "conditions": record["conditions"],
            "insurance_provider": record["insurance_provider"],
        }
    elif purpose == "insurance_verification":
   
        return {
            "patient_id": record["patient_id"],
            "insurance_provider": record["insurance_provider"],
            "insurance_id": record["insurance_id"],
        }
    elif purpose == "full_clinical":
     
        return record
    else:
        # Default: minimal, no identity, no insurance details
        return {
            "patient_id": record["patient_id"],
            "conditions": record["conditions"],
        }