import torch
from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import os

MODEL_ID = "google/medgemma-1.5-4b-it"

_model = None
_processor = None

def _get_device_and_dtype():

    forced = os.environ.get("MEDGEMMA_DEVICE")
    if forced:
        dtype = torch.bfloat16 if forced == "cuda" else torch.float32
        return forced, dtype
    return "cpu", torch.float32

def _load_model():
    global _model, _processor
    if _model is None:
        device, dtype = _get_device_and_dtype()
        print(f"Loading MedGemma 1.5 on device={device}, dtype={dtype} (first call only, this takes a while)...")
        _processor = AutoProcessor.from_pretrained(MODEL_ID)
        _model = AutoModelForImageTextToText.from_pretrained(
            MODEL_ID,
            dtype=dtype,              
            device_map=device,
            low_cpu_mem_usage=True,   
        )
    return _model, _processor

def analyze_image(image_path, modality, question=None):
    model, processor = _load_model()
    image = Image.open(image_path).convert("RGB")

    if question is None:
        question = f"This is a {modality} image. Describe any notable findings and give a likely classification."

    messages = [
        {
            "role": "system",
            "content": [{"type": "text", "text": "You are an expert radiologist assistant. Be concise and specific."}]
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image", "image": image}
            ]
        }
    ]

    inputs = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True,
        return_dict=True, return_tensors="pt"
    ).to(model.device, dtype=model.dtype)

    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=300, do_sample=False)

    response = processor.decode(output[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
    return response.strip()