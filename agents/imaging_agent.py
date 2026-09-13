from tools.medgemma_tool import analyze_image
from tools.booking_tool import book_consultation
from tools.audit_log import log_action

class ImagingAgent:
    def __init__(self, name="ImagingAgent"):
        self.name = name

    def _get_urgency_rating(self, image_path, modality, finding_text):
        """Ask MedGemma directly for a simple urgency label - used only
        as a secondary signal alongside the red-flag keyword check."""
        urgency_question = (
            f"Based on this {modality} finding: '{finding_text}', "
            "rate the urgency as exactly one word: low, medium, or high. "
            "Answer with only that one word."
        )
        rating = analyze_image(image_path, modality, question=urgency_question)
        rating_clean = rating.strip().lower().split()[0] if rating.strip() else "unknown"
        return rating_clean

    def analyze_and_route(self, image_path, modality, patient_id=None):
        log_action(self.name, "analyze_image", {"image_path": image_path, "modality": modality, "patient_id": patient_id})

        finding = analyze_image(image_path, modality)
        urgency = self._get_urgency_rating(image_path, modality, finding)

        booking_result = book_consultation(
            patient_id=patient_id or "UNKNOWN",
            modality=modality,
            finding_text=finding,
            urgency_rating=urgency,
        )

        log_action(
            self.name, "analyze_and_route_complete",
            {"image_path": image_path, "modality": modality},
            result_summary=f"{booking_result['status']} -> {booking_result['department']}"
        )

        return {
            "modality": modality,
            "finding": finding,
            "urgency_rating": urgency,
            "booking": booking_result,
        }


if __name__ == "__main__":
    import glob
    agent = ImagingAgent()

    sample_images = glob.glob("data/xrays/chest_pneumonia/*.jpg")
    if not sample_images:
        print("No sample images found")
    else:
        result = agent.analyze_and_route(sample_images[0], modality="chest X-ray", patient_id="P0001")
        print(f"Finding: {result['finding']}\n")
        print(f"Urgency rating (self-reported by model): {result['urgency_rating']}")
        print(f"Booking decision: {result['booking']}")