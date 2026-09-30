import os
import sys

hf_token = os.environ.get("HF_TOKEN", "")

if hf_token:
    try:
        from huggingface_hub import login
        print("[*] Logging into Hugging Face...")
        login(token=hf_token)
    except ImportError:
        pass

print("[*] Importing the Sentinel-X Detector...")
import detector_server
import json

test_image = "concept.jpg"

if not os.path.exists(test_image):
    print(f"[!] Test image {test_image} not found.")
    sys.exit(1)

print(f"[*] Testing the PaliGemma model on '{test_image}'...")
with open(test_image, "rb") as f:
    image_bytes = f.read()

try:
    result = detector_server.DETECTOR.analyze_image_bytes(image_bytes)
    print("\n[+] Success! Detector generated the following analysis:")
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"\n[!] Error during analysis: {e}")
