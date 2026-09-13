import re
from tools.audit_log import log_action
from datetime import datetime, timedelta

# Red-flag terms that apply regardless of modality
GENERAL_RED_FLAGS = [
    "malignant", "malignancy", "metastasis", "metastatic", "hemorrhage",
    "critical", "urgent", "emergent", "rupture", "acute", "severe",
    "life-threatening", "perforation", "obstruction"
]

# Modality-specific clinical terms
MODALITY_RED_FLAGS = {
    "chest x-ray": [
        "cardiomegaly", "enlarged heart", "arrhythmia", "effusion",
        "pneumothorax", "consolidation", "edema", "aortic aneurysm"
    ],
    "skeletal": [
        "fracture", "dislocation", "osteomyelitis", "malalignment", "comminuted"
    ],
    "mammogram": [
        "mass", "spiculated", "calcification", "bi-rads 4", "bi-rads 5"
    ],
    "abdominal": [
        "ischemia", "free air", "aneurysm", "bowel obstruction", "appendicitis"
    ],
}

# Content-based department routing: checked in order, first match wins
CONTENT_DEPARTMENT_KEYWORDS = [
    (["cardiomegaly", "enlarged heart", "cardiac", "arrhythmia", "heart"], "Cardiology"),
    (["fracture", "dislocation", "osteomyelitis", "bone", "joint"], "Orthopedics"),
    (["mass", "spiculated", "calcification", "bi-rads", "tumor"], "Breast Imaging / Oncology"),
    (["pneumothorax", "consolidation", "pneumonia", "lung", "pulmonary"], "Pulmonology"),
    (["liver", "kidney", "spleen", "pancreas", "bowel", "appendicitis"], "Gastroenterology"),
]

# Fallback if nothing in the finding text matches a specific department
MODALITY_DEFAULT_DEPARTMENT = {
    "chest x-ray": "Pulmonology",
    "skeletal": "Orthopedics",
    "mammogram": "Breast Imaging / Oncology",
    "abdominal": "Gastroenterology",
}

# Simplified NegEx-style negation cues (Chapman et al., 2001)
NEGATION_CUES = [
    "no", "not", "without", "denies", "denied", "negative for",
    "no evidence of", "no signs of", "no focal", "ruled out", "rule out",
    "absence of", "free of"
]

# Words that end a negation's scope early within the same sentence
SCOPE_RESET_WORDS = ["but", "however", "although", "except", "aside from"]


def _split_sentences(text_lower):
    """Split on sentence-ending punctuation - negation scope rarely crosses these."""
    return re.split(r'[.;\n]', text_lower)


def _is_negated(text_lower, term):
    """
    Check whether `term` falls within the scope of a negation cue earlier
    in the same sentence/clause - handles list constructions like
    'no A, B, or C' where a fixed word window would miss later items.
    Scope ends early if a reset word (but, however, etc.) appears
    between the cue and the term.
    """
    sentences = _split_sentences(text_lower)
    for sentence in sentences:
        if term not in sentence:
            continue

        term_pos = sentence.find(term)
        text_before_term = sentence[:term_pos]

        cue_positions = []
        for cue in NEGATION_CUES:
            idx = text_before_term.rfind(cue)
            if idx != -1:
                cue_positions.append((idx, cue))

        if not cue_positions:
            continue

        cue_pos, cue_text = max(cue_positions, key=lambda x: x[0])
        text_between = text_before_term[cue_pos + len(cue_text):]

        if any(reset_word in text_between for reset_word in SCOPE_RESET_WORDS):
            continue

        return True

    return False


def contains_red_flag(finding_text, modality):
    text_lower = finding_text.lower()
    all_terms = list(GENERAL_RED_FLAGS) + MODALITY_RED_FLAGS.get(modality.lower(), [])

    active_flags = []
    for term in all_terms:
        if term in text_lower and not _is_negated(text_lower, term):
            active_flags.append(term)
    return active_flags


def route_department(modality, finding_text):
    text_lower = finding_text.lower()
    for keywords, department in CONTENT_DEPARTMENT_KEYWORDS:
        matched = [kw for kw in keywords if kw in text_lower and not _is_negated(text_lower, kw)]
        if matched:
            return department
    return MODALITY_DEFAULT_DEPARTMENT.get(modality.lower(), "General Medicine")


def book_consultation(patient_id, modality, finding_text, urgency_rating="unknown"):
    """
    Decides whether to auto-book or flag for human review, and logs
    the decision either way. Fail-safe default: if anything is
    ambiguous, flag for review rather than auto-book.
    """
    flags = contains_red_flag(finding_text, modality)
    department = route_department(modality, finding_text)

    requires_review = bool(flags) or urgency_rating.lower() not in ("low", "routine")

    if requires_review:
        decision = {
            "status": "FLAGGED_FOR_HUMAN_REVIEW",
            "patient_id": patient_id,
            "department": department,
            "reason": f"red_flag_terms={flags}, urgency_rating={urgency_rating}",
            "red_flags": flags,   # structured, not just embedded in the string
        }
    else:
        appointment_time = datetime.now() + timedelta(days=7)
        decision = {
            "status": "AUTO_BOOKED",
            "patient_id": patient_id,
            "department": department,
            "appointment_time": appointment_time.isoformat(),
            "red_flags": flags,   # empty list in this branch, but consistent shape
        }

    log_action(
        "BookingTool", "booking_decision",
        {"patient_id": patient_id, "modality": modality, "urgency_rating": urgency_rating, "red_flags": flags},
        result_summary=decision["status"]
    )

    return decision