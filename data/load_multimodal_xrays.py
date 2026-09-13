from datasets import load_dataset
import os

os.makedirs("data/xrays", exist_ok=True)
limit_per_class = 100

def save_imagefolder_dataset(repo_id, out_prefix, split="train"):
    """Generic loader for imagefolder-format HF datasets."""
    print(f"\nLoading {repo_id} ...")
    dataset = load_dataset(repo_id, split=split, download_mode="force_redownload")
    print("Features:", dataset.features)
    ...

    counts = {}
    for item in dataset:
        label_id = item["label"]
        label_name = dataset.features["label"].names[label_id].lower().replace(" ", "_")
        if counts.get(label_name, 0) >= limit_per_class:
            continue
        folder = f"data/xrays/{out_prefix}_{label_name}"
        os.makedirs(folder, exist_ok=True)
        idx = counts.get(label_name, 0)
        item["image"].convert("L").save(f"{folder}/{label_name}_{idx}.jpg")
        counts[label_name] = idx + 1
    print(f"Saved: {counts}")
    return counts

# Chest X-ray
save_imagefolder_dataset("Mahadih534/Chest_X-Ray_Images-Dataset", "chest")

# Skeletal
save_imagefolder_dataset("JishnuSatwik/BoneFractureDataset", "skeletal")

# Mammogram
save_imagefolder_dataset("realzdlegend/breast_cancer_xray", "mammogram")

print("\nAll imagefolder-based modalities done. Abdominal (OrganAMNIST) loaded separately below.")

# Abdominal
import medmnist
from medmnist import OrganAMNIST

organ_data = OrganAMNIST(split="train", download=True)
organ_names = organ_data.info["label"]  # dict: {"0": "bladder", "1": "femur-left", ...}
print("Organ classes:", organ_names)

counts = {}
for img, label in organ_data:
    label_name = organ_names[str(label[0])].lower().replace(" ", "_").replace("-", "_")
    if counts.get(label_name, 0) >= limit_per_class:
        continue
    folder = f"data/xrays/abdominal_{label_name}"
    os.makedirs(folder, exist_ok=True)
    idx = counts.get(label_name, 0)
    img.convert("L").save(f"{folder}/{label_name}_{idx}.jpg")
    counts[label_name] = idx + 1

print(f"Saved abdominal: {counts}")