from faker import Faker
import random, json

fake = Faker()
Faker.seed(42)
random.seed(42)

conditions = [
    "Hypertension", "Type 2 Diabetes", "Asthma", "Coronary Artery Disease",
    "Chronic Kidney Disease", "Osteoarthritis", "Osteoporosis",           # skeletal
    "Bone Fracture (healed)",                                            # skeletal
    "Breast Cyst (benign)", "Fibroadenoma",                              # mammogram
    "Gallstones", "Abdominal Hernia", "Irritable Bowel Syndrome",        # abdominal
    "Brain Aneurysm (monitored)", "Herniated Disc",                      # CT/MRI relevant
    "COPD", "None"
]

insurers = ["BlueCross", "Aetna", "UnitedHealth", "Medicare", "Medicaid", "Cigna", "Other"]

def generate_patient(patient_id):
    insurance_provider = random.choice(insurers)
    return {
        "patient_id": patient_id,
        "name": fake.name(),
        "dob": fake.date_of_birth(minimum_age=18, maximum_age=90).isoformat(),
        "conditions": random.sample(conditions, k=random.randint(0, 3)),
        "medications": random.sample(
            ["Lisinopril", "Metformin", "Albuterol", "Atorvastatin", "Ibuprofen", "None"],
            k=random.randint(0, 2)
        ),
        "insurance_provider": insurance_provider,
        "insurance_id": fake.bothify(text="INS-####-????") if insurance_provider != "Other" else "SELF-PAY"
    }

patients = [generate_patient(f"P{i:04d}") for i in range(1, 1001)]

with open("data/patients.json", "w") as f:
    json.dump(patients, f, indent=2)

print(f"Generated {len(patients)} synthetic patients -> data/patients.json")