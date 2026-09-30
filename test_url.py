import sys
import json
import detector_server

import os

hf_token = os.environ.get("HF_TOKEN", "")
if hf_token:
    try:
        from huggingface_hub import login
        print("[*] Logging into Hugging Face...")
        login(token=hf_token)
    except ImportError:
        pass



url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

print(f"[*] Testing deepfake URL processing on: {url}")
try:
    path = detector_server.download_url_media(url)
    print(f"[+] Successfully downloaded to: {path}")
    
    print("[*] Passing video file to analyze_video_path()...")
    result = detector_server.DETECTOR.analyze_video_path(path)
    print("\n[+] Success! Analysis result:")
    print(json.dumps(result, indent=2))
except Exception as e:
    import traceback
    traceback.print_exc()
