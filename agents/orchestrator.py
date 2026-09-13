import time
from agents.patient_agent import PatientAgent
from agents.imaging_agent import ImagingAgent
from agents.research_agent import ResearchAgent
from tools.audit_log import log_action


class HealthcareOrchestrator:
    """
    Routes a single patient visit through Patient -> Imaging -> (conditionally) Research.
    Every inter-agent handoff is logged explicitly via audit_log

    """

    def __init__(self):
        self.patient_agent = PatientAgent()
        self.imaging_agent = ImagingAgent()
        self.research_agent = ResearchAgent()

    def handle_patient_visit(self, patient_id, image_path, modality):
        log_action("Orchestrator", "visit_started", {"patient_id": patient_id, "modality": modality})

        # Step 1: get patient context, scoped to what booking actually needs.
        patient_context = self.patient_agent.get_record_for(patient_id, purpose="booking")
        log_action(
            "Orchestrator", "handoff_to_imaging_agent",
            {"patient_id": patient_id, "fields_passed": list(patient_context.keys()) if patient_context else None}
        )

        if patient_context is None:
            log_action("Orchestrator", "visit_aborted", {"patient_id": patient_id, "reason": "patient not found"})
            return {"status": "ERROR", "reason": f"No patient found with ID {patient_id}"}

        # Step 2: imaging analysis + booking decision
        imaging_result = self.imaging_agent.analyze_and_route(
            image_path, modality=modality, patient_id=patient_id
        )

        report = {
            "patient_id": patient_id,
            "modality": modality,
            "finding": imaging_result["finding"],
            "urgency_rating": imaging_result["urgency_rating"],
            "booking": imaging_result["booking"],
            "related_research": None,
        }

        # Step 3: only escalate to lookup if the case was actually flagged
        if imaging_result["booking"]["status"] == "FLAGGED_FOR_HUMAN_REVIEW":
            clinical_terms = " ".join(imaging_result["booking"]["red_flags"])
            log_action("Orchestrator", "handoff_to_research_agent", {"patient_id": patient_id, "trigger": clinical_terms})

            try:
                time.sleep(0.4)  # stay under NCBI's ~3 req/sec limit without an API key
                research_query = f"{modality} {clinical_terms}"
                research_result = self.research_agent.handle(research_query, max_results=3)
                report["related_research"] = research_result["articles"]
            except Exception as e:
                log_action("Orchestrator", "research_agent_failed", {"patient_id": patient_id, "error": str(e)})
                report["related_research"] = []
                report["research_error"] = str(e)

        log_action(
            "Orchestrator", "visit_complete",
            {"patient_id": patient_id},
            result_summary=report["booking"]["status"]
        )

        return report


if __name__ == "__main__":
    import glob
    import json

    orchestrator = HealthcareOrchestrator()

    sample_images = glob.glob("data/xrays/chest_pneumonia/*.jpg")
    if not sample_images:
        print("No sample images found")
    else:
        report = orchestrator.handle_patient_visit(
            patient_id="P0001",
            image_path=sample_images[0],
            modality="chest X-ray"
        )
        print(json.dumps(report, indent=2))