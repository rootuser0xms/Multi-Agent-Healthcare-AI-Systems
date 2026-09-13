from agents.patient_agent_naive import NaivePatientAgent
from agents.imaging_agent import ImagingAgent
from agents.research_agent import ResearchAgent
from tools.audit_log import log_action


class NaiveHealthcareOrchestrator:

    def __init__(self):
        self.patient_agent = NaivePatientAgent()
        self.imaging_agent = ImagingAgent()
        self.research_agent = ResearchAgent()

    def handle_patient_visit(self, patient_id, image_path, modality):
        log_action("NaiveOrchestrator", "visit_started", {"patient_id": patient_id, "modality": modality})

        patient_context = self.patient_agent.get_record_for(patient_id, purpose="booking")
        log_action(
            "NaiveOrchestrator", "handoff_to_imaging_agent",
            {"patient_id": patient_id, "fields_passed": list(patient_context.keys()) if patient_context else None,
             "full_context": patient_context}  # deliberately logging the full unsanitized context
        )

        if patient_context is None:
            return {"status": "ERROR", "reason": f"No patient found with ID {patient_id}"}

        imaging_result = self.imaging_agent.analyze_and_route(image_path, modality=modality, patient_id=patient_id)

        report = {
            "patient_id": patient_id,
            "patient_name": patient_context.get("name"),   # naive: includes name in final report too
            "modality": modality,
            "finding": imaging_result["finding"],
            "urgency_rating": imaging_result["urgency_rating"],
            "booking": imaging_result["booking"],
        }

        log_action("NaiveOrchestrator", "visit_complete", {"patient_id": patient_id}, result_summary=report["booking"]["status"])
        return report


if __name__ == "__main__":
    import glob, json
    orchestrator = NaiveHealthcareOrchestrator()
    sample_images = glob.glob("data/xrays/chest_pneumonia/*.jpg")
    report = orchestrator.handle_patient_visit("P0001", sample_images[0], "chest X-ray")
    print(json.dumps(report, indent=2))