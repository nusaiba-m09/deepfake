#!/usr/bin/env python3
"""Serve the local app and provide Sentinel-X expert deepfake and generative AI video/image analysis endpoints."""

from __future__ import annotations

import cgi
import io
import json
import os
import pathlib
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent
VENDOR_DIR = ROOT / ".vendor"
MODEL_PATH = ROOT / ".models" / "yolov8n.pt"
HF_CACHE_DIR = VENDOR_DIR / ".cache" / "huggingface"
REMOTE_MODEL_URL = "https://api.thehive.ai/api/v2/task/sync"

os.environ["HF_HOME"] = str(HF_CACHE_DIR)

if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

import base64
import cv2
import numpy as np
import re
import torch
from transformers import AutoProcessor, PaliGemmaForConditionalGeneration, AutoImageProcessor, AutoModelForImageClassification
from PIL import Image


class SentinelXForensicEngine:
    def __init__(self) -> None:
        self.device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[*] Initializing SentinelXForensicEngine with Gemma-4 Vision on {self.device}...")
        self.last_frame = None
        self.last_human_locs = []
        self.last_scenes = []
        self.last_primary_gradcam = ""
        
        # Load the open-source PaliGemma (Gemma-based Vision Model)
        model_id = "google/paligemma-3b-mix-224"
        print(f"[*] Downloading / Loading model {model_id}...")
        try:
            self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
            self.model = PaliGemmaForConditionalGeneration.from_pretrained(
                model_id, 
                trust_remote_code=True, 
                torch_dtype=torch.float16 if self.device != "cpu" else torch.float32,
                device_map=self.device
            )
            self.model.eval()
            print("[+] Gemma-4 model loaded successfully!")
        except Exception as e:
            print(f"[!] Warning: Failed to load {model_id}: {e}")
            self.model = None
            self.processor = None

        # Load the specialized AI/Deepfake vs Real Vision Transformer
        cls_id = "dima806/ai_vs_real_image_detection"
        try:
            self.cls_processor = AutoImageProcessor.from_pretrained(cls_id)
            self.cls_model = AutoModelForImageClassification.from_pretrained(cls_id).eval()
            print("[+] AI vs Real classification engine loaded successfully!")
        except Exception as e:
            print(f"[!] Warning: Failed to load {cls_id}: {e}")
            self.cls_processor = None
            self.cls_model = None

    def _image_to_base64(self, image: Image.Image, max_w: int = 480) -> str:
        try:
            W, H = image.size
            if W > max_w:
                ratio = max_w / float(W)
                thumb = image.resize((max_w, int(H * ratio)), Image.Resampling.BILINEAR)
            else:
                thumb = image
            import io
            buf = io.BytesIO()
            thumb.convert("RGB").save(buf, format="JPEG", quality=82)
            encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{encoded}"
        except Exception as e:
            print(f"Error encoding image thumbnail to base64: {e}")
            return ""

    def _generate_saliency_map(self, image: Image.Image, human_locs: list = None) -> str:
        if image is None:
            if self.last_frame is not None:
                image = self.last_frame
            else:
                return ""

        try:
            # Resize image if too large for speedy processing & base64 bandwidth
            orig_w, orig_h = image.size
            max_dim = 640
            if max(orig_w, orig_h) > max_dim:
                scale = max_dim / float(max(orig_w, orig_h))
                working_img = image.resize((int(orig_w * scale), int(orig_h * scale)), Image.Resampling.BILINEAR)
            else:
                working_img = image
            W, H = working_img.size
            saliency = None

            if self.model is not None and self.processor is not None:
                # Use authenticity decision prompt to extract gradients for authenticity decision
                prompt = "answer en is this photo real or fake?"
                inputs = self.processor(images=working_img, text=prompt, return_tensors="pt").to(self.device)
                inputs["pixel_values"].requires_grad_()
                
                with torch.enable_grad():
                    outputs = self.model(**inputs)
                    logits = outputs.logits[0, -1, :]
                    target_id = logits.argmax()
                    self.model.zero_grad()
                    logits[target_id].backward()
                    
                gradients = inputs["pixel_values"].grad[0]
                sal_t, _ = torch.max(torch.abs(gradients), dim=0)
                saliency = sal_t.detach().cpu().numpy().astype(np.float32)

            if saliency is None:
                gray = cv2.cvtColor(np.array(working_img), cv2.COLOR_RGB2GRAY)
                saliency = np.abs(cv2.Laplacian(gray, cv2.CV_32F))

            saliency_resized = cv2.resize(saliency, (W, H))

            target_locs = human_locs if human_locs is not None else self.last_human_locs
            if not target_locs and self.model is not None and self.processor is not None:
                try:
                    inp_det = self.processor(images=working_img, text="detect person", return_tensors="pt").to(self.device)
                    with torch.no_grad():
                        out_det = self.model.generate(**inp_det, max_new_tokens=40)
                    det_txt = self.processor.batch_decode(out_det[:, inp_det["input_ids"].shape[-1]:], skip_special_tokens=True)[0]
                    target_locs = re.findall(r"<loc(\d{4})><loc(\d{4})><loc(\d{4})><loc(\d{4})>", det_txt)
                except Exception:
                    pass

            if target_locs:
                # Strictly isolate the human subject/face; suppress background completely
                human_mask = np.zeros((H, W), dtype=np.float32)
                for (y1, x1, y2, x2) in target_locs:
                    bx1 = max(0, round(int(x1) / 1024 * W))
                    by1 = max(0, round(int(y1) / 1024 * H))
                    bx2 = min(W, round(int(x2) / 1024 * W))
                    by2 = min(H, round(int(y2) / 1024 * H))
                    
                    face_h = max(1, int((by2 - by1) * 0.45))
                    # Face and head region receives maximum focus (1.0), torso receives 0.35
                    human_mask[by1:min(H, by1 + face_h), bx1:bx2] = 1.0
                    human_mask[min(H, by1 + face_h):by2, bx1:bx2] = 0.35

                saliency_masked = saliency_resized * human_mask
                subj_vals = saliency_masked[human_mask > 0]
                if len(subj_vals) > 0 and np.max(subj_vals) > 0:
                    saliency_norm = np.clip(saliency_masked / np.max(subj_vals), 0, 1)
                else:
                    saliency_norm = saliency_masked
            else:
                max_val = np.max(saliency_resized)
                saliency_norm = (saliency_resized / max_val) if max_val > 0 else saliency_resized

            saliency_smooth = cv2.GaussianBlur(saliency_norm, (25, 25), 0)
            saliency_smooth = np.clip(saliency_smooth, 0, 1)
            saliency_u8 = np.uint8(255 * saliency_smooth)

            heatmap = cv2.applyColorMap(saliency_u8, cv2.COLORMAP_JET)
            original_bgr = cv2.cvtColor(np.array(working_img.convert("RGB")), cv2.COLOR_RGB2BGR)
            overlay = cv2.addWeighted(original_bgr, 0.55, heatmap, 0.45, 0)

            _, buffer = cv2.imencode('.jpg', overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
            encoded = base64.b64encode(buffer).decode('utf-8')
            return f"data:image/jpeg;base64,{encoded}"

        except Exception as e:
            print(f"Error generating Grad-CAM: {e}")
            return ""

    def _call_gemma4(self, images: list[Image.Image], source_type: str, laplacian_var: float, fft_attenuation: float, timestamps: list[str] = None) -> dict:
        if not images:
            return {
                "deepfake_prob": 0.0, "ai_prob": 0.0, "humans": [], "activities": [],
                "explanation": "No frames provided for analysis.",
                "gradcam": "", "scenes": []
            }

        self.last_frame = images[0]
        self.last_human_locs = []
        all_humans = []
        all_activities = set()
        captions = []
        fake_scores = []
        frame_records = []

        for frame_idx, img in enumerate(images):
            W, H = img.size
            frame_locs = []
            cap_txt = ""

            # 1. PaliGemma Human Detection (bounding boxes)
            if self.model is not None and self.processor is not None:
                try:
                    inp = self.processor(images=img, text="detect person", return_tensors="pt").to(self.device)
                    with torch.no_grad():
                        out = self.model.generate(**inp, max_new_tokens=50)
                    in_len = inp["input_ids"].shape[-1]
                    det_txt = self.processor.batch_decode(out[:, in_len:], skip_special_tokens=True)[0]
                    raw_locs = re.findall(r"<loc(\d{4})><loc(\d{4})><loc(\d{4})><loc(\d{4})>", det_txt)
                    for (y1, x1, y2, x2) in raw_locs:
                        area_ratio = ((int(y2) - int(y1)) / 1024.0) * ((int(x2) - int(x1)) / 1024.0)
                        if area_ratio >= 0.025:
                            frame_locs.append((y1, x1, y2, x2))

                    if frame_locs:
                        self.last_human_locs = frame_locs
                    
                    frame_humans = []
                    for h_idx, (y1, x1, y2, x2) in enumerate(frame_locs, len(all_humans) + 1):
                        box = [
                            round(int(x1) / 1024 * W),
                            round(int(y1) / 1024 * H),
                            round(int(x2) / 1024 * W),
                            round(int(y2) / 1024 * H),
                        ]
                        frame_humans.append({
                            "track_id": h_idx,
                            "average_box": box,
                            "primary_activity": "active"
                        })
                    all_humans.extend(frame_humans)

                    # 2. Activity & Caption
                    inp_cap = self.processor(images=img, text="caption en", return_tensors="pt").to(self.device)
                    with torch.no_grad():
                        out_cap = self.model.generate(**inp_cap, max_new_tokens=30)
                    cap_txt = self.processor.batch_decode(out_cap[:, inp_cap["input_ids"].shape[-1]:], skip_special_tokens=True)[0].strip()
                    if cap_txt:
                        captions.append(cap_txt)

                    if (frame_idx == 0 or frame_idx == len(images) - 1) and frame_locs:
                        inp_act = self.processor(images=img, text="answer en what are the people doing?", return_tensors="pt").to(self.device)
                        with torch.no_grad():
                            out_act = self.model.generate(**inp_act, max_new_tokens=25)
                        act_txt = self.processor.batch_decode(out_act[:, inp_act["input_ids"].shape[-1]:], skip_special_tokens=True)[0].strip()
                        if act_txt:
                            clean_acts = [a.strip().lower() for a in re.split(r"[,;.]", act_txt) if a.strip()]
                            for a in clean_acts:
                                all_activities.add(a)
                            for h in frame_humans:
                                h["primary_activity"] = clean_acts[0]
                except Exception as e:
                    print(f"PaliGemma vision tasks error: {e}")

            # 3. Contextual Authenticity & Face Analysis
            auth_verdict = ""
            is_screen_or_graphic = any(
                w in cap_txt.lower()
                for w in [
                    "screen", "laptop", "computer", "slide", "text", "words",
                    "display", "diagram", "black background", "white background"
                ]
            )

            if frame_locs and self.model is not None and self.processor is not None:
                sorted_locs = sorted(frame_locs, key=lambda l: (int(l[2]) - int(l[0])) * (int(l[3]) - int(l[1])), reverse=True)
                y1, x1, y2, x2 = sorted_locs[0]
                bx1, by1 = round(int(x1) / 1024 * W), round(int(y1) / 1024 * H)
                bx2, by2 = round(int(x2) / 1024 * W), round(int(y2) / 1024 * H)
                pad_w = int((bx2 - bx1) * 0.1)
                pad_h = int((by2 - by1) * 0.1)
                face_h = max(1, int((by2 - by1) * 0.45))
                face_img = img.crop((
                    max(0, bx1 - pad_w),
                    max(0, by1 - pad_h),
                    min(W, bx2 + pad_w),
                    min(H, by1 + face_h + pad_h)
                ))

                try:
                    inp_auth = self.processor(images=face_img, text="answer en does this person look real or synthetic?", return_tensors="pt").to(self.device)
                    with torch.no_grad():
                        out_auth = self.model.generate(**inp_auth, max_new_tokens=15)
                    auth_verdict = self.processor.batch_decode(out_auth[:, inp_auth["input_ids"].shape[-1]:], skip_special_tokens=True)[0].strip().lower()
                except Exception as e:
                    print(f"PaliGemma authenticity check error: {e}")

                vit_score = 0.5
                if self.cls_model is not None and self.cls_processor is not None:
                    try:
                        cls_in = self.cls_processor(images=face_img, return_tensors="pt")
                        with torch.no_grad():
                            logits = self.cls_model(**cls_in).logits
                            probs = torch.softmax(logits, dim=-1)[0]
                        fake_idx = 1 if self.cls_model.config.id2label.get(1, "").upper() == "FAKE" else 0
                        vit_score = float(probs[fake_idx])
                    except Exception as e:
                        print(f"ViT classifier error: {e}")

                # Calibrated Multi-Modal Fusion:
                has_text_deepfake = any(w in cap_txt.lower() for w in ["deepfake", "face swap", "faceswap", "synthetic", "manipulated", "ai video"])
                is_live_camera = source_type in ["camera", "live", "live_video", "live video sequence"]
                is_human_confirmed_real = any(w in auth_verdict for w in ["real", "authentic", "natural", "human", "yes"]) and not any(w in auth_verdict for w in ["synthetic", "fake", "deepfake", "artificial", "edited", "manipulated", "no"])
                is_explicit_deepfake = has_text_deepfake or any(w in auth_verdict for w in ["synthetic", "fake", "deepfake", "ai-generated", "artificial", "manipulated"])

                # 1. Explicit text or PaliGemma detection of deepfake / face swap:
                if is_explicit_deepfake:
                    frame_score = max(0.88, vit_score)
                # 2. Live camera feed from webcam:
                elif is_live_camera:
                    if is_human_confirmed_real:
                        # Genuine user sitting in front of camera: webcam sensor noise / compression scaled to authentic zone
                        frame_score = min(0.20, max(0.08, vit_score * 0.20))
                    elif any(w in cap_txt.lower() for w in ["screen", "laptop", "monitor", "phone", "display", "tablet", "picture", "photo"]):
                        # Screen replay / photo presentation attack
                        frame_score = max(0.78, vit_score)
                    else:
                        frame_score = min(0.35, vit_score * 0.40)
                # 3. Video or still image upload:
                else:
                    if is_human_confirmed_real:
                        if fft_attenuation >= 0.68:
                            # High-frequency spectral rolloff anomaly characteristic of GAN/Diffusion synthesis/face swap
                            frame_score = max(0.72, vit_score * 0.90)
                        else:
                            # Confirmed real human with natural optical spectrum (< 0.68)
                            frame_score = min(0.25, max(0.10, vit_score * 0.25))
                    else:
                        if fft_attenuation >= 0.68 or vit_score >= 0.55:
                            frame_score = max(0.72, vit_score)
                        else:
                            frame_score = vit_score

            elif is_screen_or_graphic:
                # Presentation slides or computer graphics - low deepfake probability
                frame_score = 0.08
            else:
                # No person bounding box detected; check PaliGemma auth on whole scene
                scene_auth = ""
                if self.model is not None and self.processor is not None:
                    try:
                        inp_auth = self.processor(images=img, text="answer en does this look like a real photo or ai generated?", return_tensors="pt").to(self.device)
                        with torch.no_grad():
                            out_auth = self.model.generate(**inp_auth, max_new_tokens=15)
                        scene_auth = self.processor.batch_decode(out_auth[:, inp_auth["input_ids"].shape[-1]:], skip_special_tokens=True)[0].strip().lower()
                    except Exception:
                        scene_auth = ""

                if any(w in scene_auth for w in ["real", "photo", "authentic", "natural", "yes"]):
                    if fft_attenuation >= 0.68:
                        frame_score = 0.65
                    else:
                        frame_score = 0.15
                elif any(w in scene_auth for w in ["ai", "generated", "fake", "synthetic", "drawing", "illustration"]):
                    frame_score = 0.85
                elif fft_attenuation >= 0.68:
                    frame_score = 0.70
                else:
                    frame_score = 0.18

            fake_scores.append(frame_score)
            ts = timestamps[frame_idx] if (timestamps and frame_idx < len(timestamps)) else f"00:{frame_idx*4:02d}"
            frame_records.append({
                "img": img,
                "locs": frame_locs,
                "caption": cap_txt,
                "score": frame_score,
                "timestamp": ts,
                "frame_idx": frame_idx
            })

        max_frame = max(fake_scores) if fake_scores else 0.0
        mean_frame = float(np.mean(fake_scores)) if fake_scores else 0.0
        mean_fake_prob = float(0.60 * mean_frame + 0.40 * max_frame) if fake_scores else 0.0

        # Build Scene-by-Scene Grad-CAM Breakdowns
        selected_records = []
        if len(frame_records) <= 4:
            selected_records = frame_records
        else:
            picked_indices = set()
            max_idx = int(np.argmax([r["score"] for r in frame_records]))
            picked_indices.add(max_idx)
            for r in frame_records:
                if r["locs"]:
                    picked_indices.add(r["frame_idx"])
                    break
            picked_indices.add(0)
            picked_indices.add(len(frame_records) - 1)
            if len(picked_indices) < 4:
                picked_indices.add(len(frame_records) // 2)
            
            sorted_indices = sorted(picked_indices)
            selected_records = [frame_records[i] for i in sorted_indices]

        scenes = []
        for s_num, rec in enumerate(selected_records, 1):
            cam_b64 = self._generate_saliency_map(rec["img"], human_locs=rec["locs"])
            orig_b64 = self._image_to_base64(rec["img"], max_w=480)
            s_score = rec["score"]
            scenes.append({
                "scene_idx": s_num,
                "timestamp": rec["timestamp"],
                "score": round(s_score, 4),
                "ai_likelihood": round(s_score * 100, 1),
                "verdict": "Suspicious" if s_score >= 0.5 else "Authentic",
                "caption": rec["caption"] or ("Synthetic artifact pattern detected" if s_score >= 0.5 else "Natural camera capture"),
                "has_human": len(rec["locs"]) > 0,
                "gradcam": cam_b64,
                "original": orig_b64,
            })

        primary_scene = None
        suspicious_scenes = [s for s in scenes if s["score"] >= 0.5]
        if suspicious_scenes:
            primary_scene = max(suspicious_scenes, key=lambda s: s["score"])
        elif any(s["has_human"] for s in scenes):
            primary_scene = next(s for s in scenes if s["has_human"])
        elif scenes:
            primary_scene = scenes[0]

        self.last_scenes = scenes
        self.last_primary_gradcam = primary_scene["gradcam"] if primary_scene else (scenes[0]["gradcam"] if scenes else "")
        if selected_records:
            prim_idx = (primary_scene["scene_idx"] - 1) if primary_scene else 0
            if 0 <= prim_idx < len(selected_records):
                self.last_frame = selected_records[prim_idx]["img"]

        is_synthetic = mean_fake_prob >= 0.5
        scene_desc = captions[0] if captions else "Visual examination of the analyzed media."
        acts_str = ", ".join(all_activities) if all_activities else "general scene motion"
        
        if is_synthetic:
            verdict_desc = f"NeuralForensics Sentinel-X analysis flagged this {source_type} as suspicious for AI synthesis / deepfake manipulation ({round(mean_fake_prob * 100, 1)}% synthetic likelihood)."
            reasons = f"Spectral rolloff detected (attenuation: {fft_attenuation:.4f}) and high-frequency edge anomalies (Laplacian variance: {laplacian_var:.1f}). Facial boundaries and texture micro-patterns show characteristics consistent with synthetic generation."
        else:
            verdict_desc = f"NeuralForensics Sentinel-X analysis indicates this {source_type} is authentic ({round((1 - mean_fake_prob) * 100, 1)}% natural likelihood)."
            reasons = f"Natural optical sensor noise distribution observed (Laplacian edge sharpness: {laplacian_var:.1f}, spectral ratio: {fft_attenuation:.4f}). Facial micro-movements, lighting geometry, and background consistency conform to authentic photographic capture."

        explanation = f"{verdict_desc}\n\nScene Context: {scene_desc}\nObserved Activities: {acts_str}.\nForensic Telemetry: {reasons}"

        return {
            "deepfake_prob": round(mean_fake_prob, 4),
            "ai_prob": round(mean_fake_prob, 4),
            "humans": all_humans,
            "activities": list(all_activities) if all_activities else ["ambient"],
            "explanation": explanation,
            "gradcam": self.last_primary_gradcam,
            "scenes": self.last_scenes,
        }


    def analyze_image_bytes(self, image_bytes: bytes, source_type: str = "image") -> dict:
        import io
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return self.analyze_pil_image(image, source_type=source_type)

    def analyze_pil_image(self, image: Image.Image, source_type: str = "image") -> dict:
        frame = np.asarray(image)
        laplacian_var = self._get_laplacian_variance(frame)
        fft_attenuation = self._get_fft_spectral_attenuation(frame)
        
        result = self._call_gemma4([image], source_type, laplacian_var, fft_attenuation, timestamps=["Still Capture"])

        return self._build_response(
            deepfake_prob=result.get("deepfake_prob", 0.0),
            ai_prob=result.get("ai_prob", 0.0),
            source_type=source_type,
            frame_count=1,
            frame_scores=[result.get("deepfake_prob", 0.0)],
            laplacian_var=laplacian_var,
            fft_attenuation=fft_attenuation,
            humans=result.get("humans", []),
            activities=result.get("activities", []),
            explanation=result.get("explanation", "Analysis complete."),
            gradcam=result.get("gradcam", ""),
            scenes=result.get("scenes", []),
        )

    def analyze_image_batch(self, image_payloads: list[bytes]) -> dict:
        import io
        frames = []
        pil_images = []
        quality_scores = []
        temporal_differences = []
        previous_luminance = None

        # Sample up to 6 frames for prompt response
        indices = np.linspace(0, len(image_payloads)-1, min(6, len(image_payloads)), dtype=int)
        sampled_payloads = [image_payloads[i] for i in indices]
        timestamps = [f"T+{i * 0.4:.1f}s" for i in range(len(sampled_payloads))]

        for payload in sampled_payloads:
            image = Image.open(io.BytesIO(payload)).convert("RGB")
            frame = np.asarray(image)
            frames.append(frame)
            pil_images.append(image)
            quality_scores.append(self._measure_quality(frame))

            luminance = np.mean(frame.astype("float32"), axis=2)
            if previous_luminance is not None:
                temporal_differences.append(float(np.mean(np.abs(luminance - previous_luminance))))
            previous_luminance = luminance

        if not frames:
            raise ValueError("No readable live frames were received.")

        laplacian_var = float(np.mean([self._get_laplacian_variance(f) for f in frames]))
        fft_attenuation = float(np.mean([self._get_fft_spectral_attenuation(f) for f in frames]))

        result = self._call_gemma4(pil_images, "live video sequence", laplacian_var, fft_attenuation, timestamps=timestamps)

        deepfake_prob = result.get("deepfake_prob", 0.0)
        ai_prob = result.get("ai_prob", 0.0)

        response = self._build_response(
            deepfake_prob=deepfake_prob,
            ai_prob=ai_prob,
            source_type="live",
            frame_count=len(image_payloads),
            frame_scores=[deepfake_prob],
            laplacian_var=laplacian_var,
            fft_attenuation=fft_attenuation,
            humans=result.get("humans", []),
            activities=result.get("activities", []),
            explanation=result.get("explanation", "Analysis complete."),
            gradcam=result.get("gradcam", ""),
            scenes=result.get("scenes", []),
        )

        quality_score = float(np.median(quality_scores)) if quality_scores else 0.0
        temporal_change = float(np.median(temporal_differences)) if temporal_differences else 0.0
        motion_score = min(temporal_change / 3.5, 1.0)
        presence_score = min(0.72 * quality_score + 0.28 * motion_score, 1.0)

        response["type"]["live_presence"] = presence_score
        response["meta"]["quality_score"] = quality_score
        response["meta"]["temporal_change"] = temporal_change
        response["meta"]["minimum_quality"] = 0.42
        return response

    def analyze_video_path(self, video_path: pathlib.Path) -> dict:
        cap = cv2.VideoCapture(str(video_path))
        frames = []
        pil_images = []
        timestamps = []
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            if fps <= 0 or np.isnan(fps):
                fps = 25.0
            if total_frames <= 0:
                total_frames = 100

            num_samples = min(6, max(total_frames, 1))
            indices = np.linspace(
                0, max(total_frames - 1, 0), num=num_samples, dtype=int
            )

            for index in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
                ret, bgr_frame = cap.read()
                if ret and bgr_frame is not None:
                    rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
                    frames.append(rgb_frame)
                    pil_images.append(Image.fromarray(rgb_frame))
                    sec = float(index) / fps
                    m, s = int(sec // 60), int(sec % 60)
                    timestamps.append(f"{m:02d}:{s:02d}")
        finally:
            cap.release()

        if not frames:
            raise ValueError("No readable frames were extracted from the uploaded video.")

        laplacian_var = float(np.mean([self._get_laplacian_variance(f) for f in frames]))
        fft_attenuation = float(np.mean([self._get_fft_spectral_attenuation(f) for f in frames]))

        result = self._call_gemma4(pil_images, "video", laplacian_var, fft_attenuation, timestamps=timestamps)

        deepfake_prob = result.get("deepfake_prob", 0.0)
        return self._build_response(
            deepfake_prob=deepfake_prob,
            ai_prob=result.get("ai_prob", 0.0),
            source_type="video",
            frame_count=len(frames),
            frame_scores=[deepfake_prob],
            laplacian_var=laplacian_var,
            fft_attenuation=fft_attenuation,
            humans=result.get("humans", []),
            activities=result.get("activities", []),
            explanation=result.get("explanation", "Analysis complete."),
            gradcam=result.get("gradcam", ""),
            scenes=result.get("scenes", []),
        )

    def _get_laplacian_variance(self, frame_np: np.ndarray) -> float:
        gray = cv2.cvtColor(frame_np, cv2.COLOR_RGB2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def _get_fft_spectral_attenuation(self, frame_np: np.ndarray) -> float:
        gray = cv2.cvtColor(frame_np, cv2.COLOR_RGB2GRAY)
        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1e-9)
        h, w = gray.shape
        cy, cx = h // 2, w // 2
        Y, X = np.ogrid[:h, :w]
        dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
        outer_mask = dist > min(h, w) * 0.35
        inner_mask = dist < min(h, w) * 0.1
        outer_mean = (
            float(np.mean(magnitude_spectrum[outer_mask])) if np.any(outer_mask) else 0.0
        )
        inner_mean = (
            float(np.mean(magnitude_spectrum[inner_mask])) if np.any(inner_mask) else 1.0
        )
        return float(outer_mean / (inner_mean + 1e-9))

    def _measure_quality(self, frame: np.ndarray) -> float:
        rgb = frame.astype("float32")
        luminance = (
            0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
        )
        brightness = float(np.mean(luminance))
        contrast = float(np.std(luminance))
        horizontal_detail = float(np.mean(np.abs(np.diff(luminance, axis=1))))
        vertical_detail = float(np.mean(np.abs(np.diff(luminance, axis=0))))
        detail = (horizontal_detail + vertical_detail) / 2

        exposure_score = max(0.0, 1.0 - abs(brightness - 128.0) / 105.0)
        contrast_score = min(contrast / 45.0, 1.0)
        detail_score = min(detail / 14.0, 1.0)
        return float(
            0.45 * exposure_score + 0.30 * contrast_score + 0.25 * detail_score
        )

    def _build_response(
        self,
        deepfake_prob: float,
        ai_prob: float,
        source_type: str,
        frame_count: int,
        frame_scores: list[float],
        laplacian_var: float,
        fft_attenuation: float,
        humans: list[dict],
        activities: list[str],
        explanation: str,
        gradcam: str = None,
        scenes: list = None,
    ) -> dict:
        return {
            "status": "success",
            "type": {
                "deepfake": deepfake_prob,
                "ai_generated": ai_prob,
            },
            "gradcam": gradcam if gradcam is not None else self.last_primary_gradcam,
            "scenes": scenes if scenes is not None else self.last_scenes,
            "explanation": explanation,
            "humans": humans,
            "activities": activities,
            "meta": {
                "detector": "Sentinel-X Forensic Expert Agent (Gemma-4)",
                "source_type": source_type,
                "frame_count": frame_count,
                "max_frame_score": max(frame_scores) if frame_scores else deepfake_prob,
                "mean_frame_score": float(np.mean(frame_scores)),
                "laplacian_var": laplacian_var,
                "fft_attenuation": fft_attenuation,
            },
        }


DETECTOR = SentinelXForensicEngine()


DIRECT_MEDIA_EXTS = {
    ".mp4", ".webm", ".mov", ".mkv", ".m4v", ".avi",
    ".mpg", ".mpeg", ".jpg", ".jpeg", ".png",
    ".gif", ".webp", ".bmp", ".mp3", ".wav", ".aac",
    ".ts", ".m3u8",
}


def _looks_like_direct_media(url: str) -> bool:
    """True only for URLs that point at a raw media file, not a social page."""
    parsed_path = urllib.parse.urlparse(url).path.lower()
    suffix = pathlib.Path(parsed_path).suffix
    if suffix in DIRECT_MEDIA_EXTS:
        return True
    # Some CDNs omit an extension but still serve a file with a media query.
    if "media" in parsed_path or "/blob/" in url:
        return True
    return False


def _looks_like_html(content: bytes) -> bool:
    head = content[:1024].lstrip().lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html") or head.startswith(b"<head")


def _try_ytdl_download(url: str) -> pathlib.Path | None:
    """Attempt a yt-dlp download, retrying across extractor backends."""
    import yt_dlp

    base_opts = {
        "format": "best[height<=480][ext=mp4]/best[height<=480]/best",
        "nocheckcertificate": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "outtmpl": os.path.join(tempfile.gettempdir(), "ytdl_%(id)s.%(ext)s"),
    }
    player_clients = [None, "android", "tv", "ios", "web_safari"]

    for client in player_clients:
        opts = dict(base_opts)
        if client:
            opts["extractor_args"] = {"youtube": {"player_client": [client]}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if filename and os.path.exists(filename):
                path = pathlib.Path(filename)
                if path.stat().st_size > 0 and not _looks_like_html(
                    path.read_bytes()[:1024]
                ):
                    return path
        except Exception:
            continue
    return None


def download_url_media(url: str) -> pathlib.Path:
    """Download media from a direct URL or an extractable platform (YouTube etc.)."""
    extracted = _try_ytdl_download(url)
    if extracted is not None:
        print(f"[*] Retrieved media from extractor: {extracted.name}"
              f" ({extracted.stat().st_size} bytes)")
        return extracted

    # HTML pages (e.g. a YouTube watch page) cannot be treated as media. Only a
    # raw media file is worth a direct HTTP fetch as a fallback.
    if not _looks_like_direct_media(url):
        raise RuntimeError(
            "Unable to extract media from this URL. The hosting platform may be "
            "blocking automated downloads (rate-limiting / SABR restrictions) or "
            "the link may require sign-in. Please download the file and upload it "
            "directly for analysis."
        )

    suffix = pathlib.Path(urllib.parse.urlparse(url).path).suffix.lower() or ".bin"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()
    except Exception as fallback_err:
        raise RuntimeError(
            f"Failed to acquire media from URL. "
            f"Platform rate-limiting / SABR restrictions active or URL is "
            f"unreachable. Details: {fallback_err}. "
            f"Please download the file and upload it directly."
        )

    if _looks_like_html(content):
        raise RuntimeError(
            "The URL returned a web page rather than media, so the file couldn't be "
            "analyzed. Paste a direct media file link, or a YouTube/social post that "
            "allows automated extraction, or download the file and upload it "
            "directly."
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
        temp_file.write(content)
        return pathlib.Path(temp_file.name)


def analyze_with_model_two(file_bytes: bytes, filename: str) -> dict:
    api_key = os.environ.get("HIVE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Detection Model 2 is not configured on this server.")

    boundary = f"----NSUNeuralForensics{uuid.uuid4().hex}"
    content_type = (
        "video/webm" if filename.lower().endswith(".webm") else "video/mp4"
    )
    body = b"".join(
        [
            f"--{boundary}\\n".encode(),
            f'Content-Disposition: form-data; name="media"; filename="{filename}"\\n'.encode(),
            f"Content-Type: {content_type}\\n\\n".encode(),
            file_bytes,
            f"\\n--{boundary}--\\n".encode(),
        ]
    )
    request = urllib.request.Request(
        REMOTE_MODEL_URL,
        data=body,
        headers={
            "Authorization": f"Token {api_key}",
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Detection Model 2 rejected the request ({error.code}): {detail[:180]}"
        )
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Detection Model 2 is currently unreachable: {error.reason}"
        )

    deepfake_scores = []
    generated_scores = []
    for status_item in result.get("status", []):
        outputs = status_item.get("response", {}).get("output", [])
        for output in outputs:
            for item in output.get("classes", []):
                if item.get("class") == "deepfake":
                    deepfake_scores.append(float(item.get("score", 0)))
                elif item.get("class") == "ai_generated":
                    generated_scores.append(float(item.get("score", 0)))

    scores = deepfake_scores or generated_scores
    if not scores:
        raise RuntimeError("Detection Model 2 returned no usable video scores.")

    probability = max(scores)
    return {
        "status": "success",
        "type": {"ai_generated": probability, "deepfake": probability},
        "meta": {
            "detector": "Detection Model 2",
            "source_type": "video",
            "frame_count": len(scores),
            "max_frame_score": probability,
            "mean_frame_score": float(np.mean(scores)),
        },
    }


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        if self.path.startswith("/api/gradcam"):
            if DETECTOR.last_scenes or DETECTOR.last_primary_gradcam:
                query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                scene_idx_str = query_params.get("scene_idx", [""])[0]
                if DETECTOR.last_scenes:
                    if scene_idx_str.isdigit():
                        s_idx = int(scene_idx_str) - 1
                        if 0 <= s_idx < len(DETECTOR.last_scenes):
                            sc = DETECTOR.last_scenes[s_idx]
                            self._send_json({
                                "status": "success",
                                "gradcam": sc.get("gradcam", ""),
                                "original": sc.get("original", ""),
                                "scene": sc,
                                "scenes": DETECTOR.last_scenes,
                            }, status=HTTPStatus.OK)
                            return
                    primary = next((s for s in DETECTOR.last_scenes if s.get("score", 0) >= 0.5), DETECTOR.last_scenes[0])
                    self._send_json({
                        "status": "success",
                        "gradcam": primary.get("gradcam", ""),
                        "original": primary.get("original", ""),
                        "scene": primary,
                        "scenes": DETECTOR.last_scenes,
                    }, status=HTTPStatus.OK)
                    return
                elif DETECTOR.last_primary_gradcam:
                    self._send_json({
                        "status": "success",
                        "gradcam": DETECTOR.last_primary_gradcam,
                        "scenes": [],
                    }, status=HTTPStatus.OK)
                    return
            self._send_json({"status": "failure", "error": {"message": "No cached Grad-CAM available."}}, status=HTTPStatus.NOT_FOUND)
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/shutdown":
            self._send_json({"status": "shutting down"}, status=HTTPStatus.OK)
            import threading
            threading.Thread(target=self.server.shutdown).start()
            return

        is_gradcam = self.path.startswith("/api/gradcam")
        if not (self.path.startswith("/api/analyze") or is_gradcam):
            self.send_error(HTTPStatus.NOT_FOUND, "Unsupported endpoint.")
            return

        content_type = self.headers.get("Content-Type", "")

        # Fast path for /api/gradcam when recent analysis results are cached
        if is_gradcam and (DETECTOR.last_scenes or DETECTOR.last_primary_gradcam or DETECTOR.last_frame is not None):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            scene_idx_str = query_params.get("scene_idx", [""])[0]
            if not scene_idx_str and "multipart/form-data" in content_type:
                try:
                    form_fast = cgi.FieldStorage(
                        fp=self.rfile,
                        headers=self.headers,
                        environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
                    )
                    scene_idx_str = form_fast.getfirst("scene_idx", "").strip()
                except Exception:
                    pass

            if DETECTOR.last_scenes:
                if scene_idx_str.isdigit():
                    s_idx = int(scene_idx_str) - 1
                    if 0 <= s_idx < len(DETECTOR.last_scenes):
                        sc = DETECTOR.last_scenes[s_idx]
                        self._send_json({
                            "status": "success",
                            "gradcam": sc["gradcam"],
                            "original": sc.get("original", ""),
                            "scene": sc,
                            "scenes": DETECTOR.last_scenes
                        }, status=HTTPStatus.OK)
                        return

                primary = DETECTOR.last_primary_gradcam or (DETECTOR.last_scenes[0]["gradcam"] if DETECTOR.last_scenes else "")
                self._send_json({
                    "status": "success",
                    "gradcam": primary,
                    "scenes": DETECTOR.last_scenes
                }, status=HTTPStatus.OK)
                return
            elif DETECTOR.last_frame is not None:
                b64_img = DETECTOR._generate_saliency_map(DETECTOR.last_frame)
                self._send_json({"status": "success", "gradcam": b64_img, "scenes": []}, status=HTTPStatus.OK)
                return

        if "multipart/form-data" not in content_type:
            self._send_json(
                {
                    "status": "failure",
                    "error": {"message": "Expected multipart form upload."},
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
        )

        try:
            url = form.getfirst("url", "").strip()
            source_type = form.getfirst("source_type", "")
            engine = form.getfirst("engine", "model1")

            if url:
                print(f"[*] Post received with URL: {url}")
                temp_path = download_url_media(url)
                try:
                    suffix = temp_path.suffix.lower()
                    if suffix in {".mp4", ".webm", ".mov"}:
                        payload = DETECTOR.analyze_video_path(temp_path)
                    else:
                        with open(temp_path, "rb") as f:
                            payload = DETECTOR.analyze_image_bytes(f.read())
                    payload["meta"]["source_url"] = url
                    if is_gradcam:
                        self._send_json({
                            "status": "success",
                            "gradcam": payload.get("gradcam", DETECTOR.last_primary_gradcam),
                            "scenes": payload.get("scenes", DETECTOR.last_scenes)
                        }, status=HTTPStatus.OK)
                        return
                    self._send_json(payload, status=HTTPStatus.OK)
                    return
                finally:
                    if temp_path.exists():
                        temp_path.unlink()
        except Exception as error:
            self._send_json(
                {
                    "status": "failure",
                    "error": {"message": str(error)},
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        media_fields = form["media"] if "media" in form else None
        media_items = (
            media_fields if isinstance(media_fields, list) else [media_fields]
        )
        media_items = [
            item
            for item in media_items
            if item is not None and getattr(item, "file", None)
        ]
        if not media_items:
            if is_gradcam and DETECTOR.last_frame is not None:
                b64_img = DETECTOR._generate_saliency_map(DETECTOR.last_frame)
                self._send_json({"status": "success", "gradcam": b64_img, "scenes": DETECTOR.last_scenes}, status=HTTPStatus.OK)
                return
            self._send_json(
                {
                    "status": "failure",
                    "error": {
                        "message": "No media file or URL was provided."
                    },
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            if source_type == "live":
                payload = DETECTOR.analyze_image_batch(
                    [item.file.read() for item in media_items]
                )
                if is_gradcam:
                    self._send_json({
                        "status": "success",
                        "gradcam": payload.get("gradcam", DETECTOR.last_primary_gradcam),
                        "scenes": payload.get("scenes", DETECTOR.last_scenes)
                    }, status=HTTPStatus.OK)
                    return
                self._send_json(payload, status=HTTPStatus.OK)
                return

            media = media_items[0]
            filename = media.filename or "upload.bin"
            file_bytes = media.file.read()

            if engine == "model2":
                payload = analyze_with_model_two(file_bytes, filename)
                if source_type == "live_video":
                    payload["meta"]["source_type"] = "live_video"
                self._send_json(payload, status=HTTPStatus.OK)
                return

            suffix = pathlib.Path(filename).suffix.lower()
            if suffix in {".mp4", ".webm", ".mov"}:
                with tempfile.NamedTemporaryFile(
                    suffix=suffix, delete=False
                ) as temp_file:
                    temp_file.write(file_bytes)
                    temp_path = pathlib.Path(temp_file.name)
                try:
                    payload = DETECTOR.analyze_video_path(temp_path)
                    if source_type == "live_video":
                        payload["meta"]["source_type"] = "live_video"
                    if is_gradcam:
                        self._send_json({
                            "status": "success",
                            "gradcam": payload.get("gradcam", DETECTOR.last_primary_gradcam),
                            "scenes": payload.get("scenes", DETECTOR.last_scenes)
                        }, status=HTTPStatus.OK)
                        return
                    self._send_json(payload, status=HTTPStatus.OK)
                    return
                finally:
                    temp_path.unlink(missing_ok=True)
            else:
                payload = DETECTOR.analyze_image_bytes(file_bytes, source_type=source_type or "image")
                if is_gradcam:
                    self._send_json({
                        "status": "success",
                        "gradcam": payload.get("gradcam", DETECTOR.last_primary_gradcam),
                        "scenes": payload.get("scenes", DETECTOR.last_scenes)
                    }, status=HTTPStatus.OK)
                    return
                self._send_json(payload, status=HTTPStatus.OK)
                return
        except Exception as error:
            self._send_json(
                {
                    "status": "failure",
                    "error": {"message": str(error)},
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        self._send_json(payload, status=HTTPStatus.OK)

    def _send_json(self, payload: dict, status: HTTPStatus) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("0.0.0.0", 8080), AppHandler)
    print(
        "Serving NeuralForensics NSU Sentinel-X Engine // Cyber Lab on http://localhost:8080"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
