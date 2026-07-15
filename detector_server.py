#!/usr/bin/env python3
"""Serve the local app and provide a Meso4-based deepfake analysis endpoint."""

from __future__ import annotations

import cgi
import io
import json
import os
import pathlib
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent
VENDOR_DIR = ROOT / ".vendor"
MODEL_PATH = ROOT / ".models" / "meso4_best.pth"
REMOTE_MODEL_URL = "https://api.thehive.ai/api/v2/task/sync"

if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

import imageio.v2 as imageio
import numpy as np
import torch
import torch.nn as nn
from PIL import Image


class Meso4(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(3, 8, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(8)
        self.relu = nn.ReLU(inplace=True)
        self.leakyrelu = nn.LeakyReLU(0.1)
        self.conv2 = nn.Conv2d(8, 8, 5, padding=2, bias=False)
        self.bn2 = nn.BatchNorm2d(16)
        self.conv3 = nn.Conv2d(8, 16, 5, padding=2, bias=False)
        self.conv4 = nn.Conv2d(16, 16, 5, padding=2, bias=False)
        self.maxpooling1 = nn.MaxPool2d((2, 2))
        self.maxpooling2 = nn.MaxPool2d((4, 4))
        self.dropout = nn.Dropout(0.5)
        self.fc1 = nn.Linear(16 * 8 * 8, 16)
        self.fc2 = nn.Linear(16, 2)

    def features(self, tensor: torch.Tensor) -> torch.Tensor:
        tensor = self.maxpooling1(self.bn1(self.relu(self.conv1(tensor))))
        tensor = self.maxpooling1(self.bn1(self.relu(self.conv2(tensor))))
        tensor = self.maxpooling1(self.bn2(self.relu(self.conv3(tensor))))
        tensor = self.maxpooling2(self.bn2(self.relu(self.conv4(tensor))))
        return tensor.view(tensor.size(0), -1)

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        feature = self.features(tensor)
        output = self.dropout(feature)
        output = self.leakyrelu(self.fc1(output))
        output = self.dropout(output)
        return self.fc2(output)


class LocalDetector:
    def __init__(self) -> None:
        self.model = Meso4().eval()
        state_dict = torch.load(MODEL_PATH, map_location="cpu")
        state_dict = {
            key.replace("backbone.", ""): value
            for key, value in state_dict.items()
            if key.startswith("backbone.")
        }
        self.model.load_state_dict(state_dict, strict=True)

    def analyze_image_bytes(self, image_bytes: bytes) -> dict:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return self.analyze_pil_image(image)

    def _prepare_frame(self, frame: np.ndarray) -> torch.Tensor:
        height, width = frame.shape[:2]
        side = min(height, width)
        x0 = (width - side) // 2
        y0 = (height - side) // 2
        crop = frame[y0 : y0 + side, x0 : x0 + side]
        image = Image.fromarray(crop).resize((256, 256), Image.BILINEAR)
        array = np.asarray(image).astype("float32") / 255.0
        array = (array - 0.5) / 0.5
        tensor = torch.from_numpy(array.transpose(2, 0, 1)).unsqueeze(0)
        return tensor

    def _score_tensor(self, tensor: torch.Tensor) -> float:
        with torch.no_grad():
            logits = self.model(tensor)
            probability = torch.softmax(logits, dim=1)[0, 1].item()
        return float(probability)

    def analyze_pil_image(self, image: Image.Image) -> dict:
        frame = np.asarray(image.convert("RGB"))
        probability = self._score_tensor(self._prepare_frame(frame))
        return self._build_response(probability, "image", 1, [probability])

    def analyze_image_batch(self, image_payloads: list[bytes]) -> dict:
        probabilities = []
        quality_scores = []
        temporal_differences = []
        previous_luminance = None
        for payload in image_payloads:
            image = Image.open(io.BytesIO(payload)).convert("RGB")
            frame = np.asarray(image)
            probabilities.append(self._score_tensor(self._prepare_frame(frame)))
            quality_scores.append(self._measure_quality(frame))
            luminance = np.mean(frame.astype("float32"), axis=2)
            if previous_luminance is not None:
                temporal_differences.append(float(np.mean(np.abs(luminance - previous_luminance))))
            previous_luminance = luminance

        if not probabilities:
            raise ValueError("No readable live frames were received.")

        # Median aggregation resists one-off glare, motion blur, and JPEG artifacts.
        probability = float(np.median(probabilities))
        response = self._build_response(probability, "live", len(probabilities), probabilities)
        quality_score = float(np.median(quality_scores))
        temporal_change = float(np.median(temporal_differences)) if temporal_differences else 0.0
        motion_score = min(temporal_change / 3.5, 1.0)
        presence_score = min(0.72 * quality_score + 0.28 * motion_score, 1.0)
        response["type"]["live_presence"] = presence_score
        response["meta"]["quality_score"] = quality_score
        response["meta"]["temporal_change"] = temporal_change
        response["meta"]["minimum_quality"] = 0.42
        return response

    def _measure_quality(self, frame: np.ndarray) -> float:
        rgb = frame.astype("float32")
        luminance = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
        brightness = float(np.mean(luminance))
        contrast = float(np.std(luminance))
        horizontal_detail = float(np.mean(np.abs(np.diff(luminance, axis=1))))
        vertical_detail = float(np.mean(np.abs(np.diff(luminance, axis=0))))
        detail = (horizontal_detail + vertical_detail) / 2

        exposure_score = max(0.0, 1.0 - abs(brightness - 128.0) / 105.0)
        contrast_score = min(contrast / 45.0, 1.0)
        detail_score = min(detail / 14.0, 1.0)
        return float(0.45 * exposure_score + 0.30 * contrast_score + 0.25 * detail_score)

    def analyze_video_path(self, video_path: pathlib.Path) -> dict:
        reader = imageio.get_reader(str(video_path), format="ffmpeg")
        try:
            metadata = reader.get_meta_data()
            frame_count = metadata.get("nframes")
            if not frame_count or frame_count == float("inf"):
              duration = metadata.get("duration") or 0
              fps = metadata.get("fps") or 24
              frame_count = max(int(duration * fps), 1)

            indices = np.linspace(
                0,
                max(int(frame_count) - 1, 0),
                num=min(12, max(int(frame_count), 1)),
                dtype=int,
            )

            probabilities = []
            for index in indices:
                try:
                    frame = reader.get_data(int(index))
                except Exception:
                    continue
                probabilities.append(self._score_tensor(self._prepare_frame(frame)))
        finally:
            reader.close()

        if not probabilities:
            raise ValueError("No readable frames were extracted from the uploaded video.")

        probability = float(np.mean(probabilities))
        return self._build_response(probability, "video", len(probabilities), probabilities)

    def _build_response(
        self, probability: float, source_type: str, frame_count: int, frame_scores: list[float]
    ) -> dict:
        return {
            "status": "success",
            "type": {
                "ai_generated": probability,
                "deepfake": probability,
            },
            "meta": {
                "detector": "Meso4 Local",
                "source_type": source_type,
                "frame_count": frame_count,
                "max_frame_score": max(frame_scores),
                "mean_frame_score": float(np.mean(frame_scores)),
            },
        }


DETECTOR = LocalDetector()


def analyze_with_model_two(file_bytes: bytes, filename: str) -> dict:
    api_key = os.environ.get("HIVE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Detection Model 2 is not configured on this server.")

    boundary = f"----NSUNeuralForensics{uuid.uuid4().hex}"
    content_type = "video/webm" if filename.lower().endswith(".webm") else "video/mp4"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            file_bytes,
            f"\r\n--{boundary}--\r\n".encode(),
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
        raise RuntimeError(f"Detection Model 2 rejected the request ({error.code}): {detail[:180]}")
    except urllib.error.URLError as error:
        raise RuntimeError(f"Detection Model 2 is currently unreachable: {error.reason}")

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

    def do_POST(self) -> None:
        if self.path != "/api/analyze":
            self.send_error(HTTPStatus.NOT_FOUND, "Unsupported endpoint.")
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_json(
                {"status": "failure", "error": {"message": "Expected multipart form upload."}},
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

        media_fields = form["media"] if "media" in form else None
        media_items = media_fields if isinstance(media_fields, list) else [media_fields]
        media_items = [item for item in media_items if item is not None and getattr(item, "file", None)]
        if not media_items:
            self._send_json(
                {"status": "failure", "error": {"message": "No media file was provided."}},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            source_type = form.getfirst("source_type", "")
            engine = form.getfirst("engine", "model1")
            if source_type == "live":
                payload = DETECTOR.analyze_image_batch([item.file.read() for item in media_items])
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
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                    temp_file.write(file_bytes)
                    temp_path = pathlib.Path(temp_file.name)
                try:
                    payload = DETECTOR.analyze_video_path(temp_path)
                    if source_type == "live_video":
                        payload["meta"]["source_type"] = "live_video"
                finally:
                    temp_path.unlink(missing_ok=True)
            else:
                payload = DETECTOR.analyze_image_bytes(file_bytes)
        except Exception as error:
            self._send_json(
                {"status": "failure", "error": {"message": str(error)}},
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
    server = ThreadingHTTPServer(("0.0.0.0", 8080), AppHandler)
    print("Serving NeuralForensics NSU // Cyber Lab on http://localhost:8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
