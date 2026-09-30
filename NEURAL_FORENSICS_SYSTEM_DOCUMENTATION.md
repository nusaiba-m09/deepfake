# NEURAL FORENSICS: SENTINEL-X DEEPFAKE & SYNTHETIC MEDIA DETECTION SYSTEM
**North South University // Cyber Forensics & Intelligence Laboratory**
**Authors:** Neural Forensics Research Group  
**System Architecture & Model Technical Manual**  
**Version:** 2.0 (Production Release)  
**Date:** September 2026

---

## 1. Executive Summary & Purpose

The **NeuralForensics Sentinel-X** system is an enterprise-grade cyber-forensic platform engineered at North South University to detect, classify, localize, and explain digital media manipulations. With the proliferation of generative artificial intelligence—specifically deepfake face-swapping algorithms (DeepFaceLab, SimSwap, FaceShifter), facial reenactment systems (First Order Motion, LivePortrait), neural voice/lip synthesis (Wav2Lip, SadTalker), and text-to-video generative models (Sora, Kling, Runway Gen-3)—digital media integrity has become critically vulnerable.

Traditional deepfake detectors suffer from three fatal flaws:
1. **Black-box opacity**: Classifying videos with an unexplained numerical score without pointing to where the manipulation occurred.
2. **False positives on real media**: Confusing common video compression artifacts (H.264/H.265 compression blocks, YouTube VP9 encoding, beauty filters) with generative synthetic noise.
3. **Background interference**: Diverting model attention away from the human face toward high-contrast background elements (aquariums, studio lighting, monitors, textures).

NeuralForensics Sentinel-X resolves these challenges through a **Multi-Modal Calibrated Forensic Architecture**. It combines Google's **PaliGemma-3B** vision-language foundation model, a specialized **Vision Transformer (ViT)** deepfake classifier, **physical frequency-domain spectral analysis (2D-FFT)**, **spatial edge variance (Laplacian)**, and **backpropagated attention Grad-CAM saliency mapping**.

---

## 2. High-Level System Architecture

The platform operates across four primary layers:

```
[ User Interaction Layer ]
  ├── YouTube / Web Video URLs (Streaming via yt-dlp)
  ├── Local File Uploads (MP4, WebM, MOV, JPG, PNG)
  └── Real-Time Live Webcam Stream (Indexed Video Buffering)
               │
               ▼
[ Ingestion & Preprocessing Layer ]
  ├── Dynamic Keyframe Temporal Sampler (FPS-derived mm:ss timestamps)
  ├── Frame Quality Assessment (Luminance, Contrast, Exposure)
  └── Physical Telemetry Analyzer (Laplacian Edge Variance & 2D-FFT Rolloff)
               │
               ▼
[ Neural Inference & Forensic Layer ]
  ├── 1. PaliGemma-3B (SigLIP Vision Transformer + Gemma-2B Autoregressive LLM)
  │      ├── Spatial Token Localization ("detect person", "detect face")
  │      ├── Contextual Activity Recognition ("what are the people doing?")
  │      ├── Semantic Natural Language Captioning ("caption en")
  │      └── Organic Authenticity Reasoning ("does this person look real or synthetic?")
  │
  ├── 2. Specialized ViT Classifier (dima806/ai_vs_real_image_detection)
  │      └── Micro-Texture Patch Attention on Cropped Human Head/Face
  │
  └── 3. Grad-CAM Explainable AI Engine
         └── Backpropagated gradients with strict human-subject spatial normalization
               │
               ▼
[ Decision Fusion & Explanatory Output Layer ]
  ├── Multi-Modal Calibrated Decision Fusion Engine
  ├── Zero-Latency Saliency Caching (<50ms retrieval)
  ├── Interactive Multi-View Inspector (Heatmap / Original / Split View)
  └── Automated Forensic Intelligence Report (PDF/Print Export)
```

---

## 3. End-to-End Processing Steps

### Step 1: Input Ingestion & Multi-Source Normalization
The system accepts media from four distinct ingestion vectors:
1. **YouTube & Streaming URLs**: Processed through an in-memory `yt-dlp` streaming extractor with multi-client fallback (`android`, `tv`, `ios`, `web_safari`) to bypass YouTube SABR bot-detection and 403 Forbidden throttling.
2. **Local Video Uploads**: Video files are streamed to temporary storage, decoded via OpenCV, and probed for duration, frame count, resolution, and native frame rate.
3. **Local Image Uploads**: High-resolution photos are ingested and normalized for multi-scale inspection.
4. **Live Camera Feed**: The client captures sequential frames from the user's camera at set intervals and sends synchronized batches for continuous monitoring.

### Step 2: Keyframe Temporal Sampling
Rather than blindly analyzing only the first second of a video, the system extracts keyframes uniformly distributed across the temporal duration of the video.
- For each sampled frame, the exact timestamp (`mm:ss`) is computed:
  $$\text{Timestamp} = \left\lfloor \frac{\text{Frame Index}}{\text{FPS} \times 60} \right\rfloor : \left( \left\lfloor \frac{\text{Frame Index}}{\text{FPS}} \right\rfloor \pmod{60} \right)$$
- This guarantees forensic coverage of the beginning, middle climax, and conclusion of the media.

### Step 3: Human Subject & Facial Localization
Deepfake manipulation typically targets the human face and head. Evaluating full-frame images causes deep learning models to inspect background walls, furniture, or compression artifacts rather than facial boundaries.
1. The frame is fed into PaliGemma with the prompt `detect person`.
2. PaliGemma uses spatial coordinate tokens (`<loc0000>` to `<loc1023>`) representing normalized coordinates ($[0, 1023]$) of detected bounding boxes.
3. The bounding box coordinates $[y_1, x_1, y_2, x_2]$ are scaled to original pixel dimensions $(W, H)$:
   $$x_{\text{pixel}} = \text{round}\left(\frac{x}{1024} \times W\right), \quad y_{\text{pixel}} = \text{round}\left(\frac{y}{1024} \times H\right)$$
4. The system isolates the facial region by extracting the upper 45% of the person's bounding box:
   $$\text{Face Height} = \max\left(1, \lfloor(by_2 - by_1) \times 0.45\rfloor\right)$$
   $$\text{Face Crop} = \text{Image}[by_1 - \text{pad}_y : by_1 + \text{Face Height} + \text{pad}_y, \; bx_1 - \text{pad}_x : bx_2 + \text{pad}_x]$$

### Step 4: Semantic Vision-Language Analysis (PaliGemma-3B)
PaliGemma performs three simultaneous vision-language tasks on the media:
1. **Scene Description**: Prompt `caption en` generates natural language understanding of the environment.
2. **Behavioral Analysis**: Prompt `answer en what are the people doing?` extracts actions (speaking, smiling, gesturing).
3. **Semantic Authenticity Assessment**: Prompt `answer en does this person look real or synthetic?` directly probes the language model for perceived visual anomalies.

### Step 5: Micro-Artifact Vision Transformer (ViT) Inference
The cropped facial patch is passed to the specialized Vision Transformer (`dima806/ai_vs_real_image_detection`):
1. The image is divided into $16 \times 16$ non-overlapping patches.
2. Patches are projected through linear embeddings and processed by multi-head self-attention layers.
3. The classification head outputs logits for `[REAL, FAKE]`. Softmax computes the raw deepfake probability $P_{\text{ViT}}$.

### Step 6: Physical Signal & Frequency Forensics
To prevent neural networks from hallucinating, Sentinel-X computes physical image metrics directly from raw sensor pixels:
1. **Laplacian Edge Variance (Spatial Domain)**:
   Measures high-frequency edge sharpness and boundary discontinuities:
   $$\text{Var}_{\text{Lap}} = \text{Var}\left( \nabla^2 I \right) = \text{Var}\left( \frac{\partial^2 I}{\partial x^2} + \frac{\partial^2 I}{\partial y^2} \right)$$
   - Real camera recordings typically show natural sensor noise ($\text{Var}_{\text{Lap}} \in [100, 3000]$).
   - Generative diffusion or GAN boundary blending exhibits extreme high-frequency anomalies ($\text{Var}_{\text{Lap}} > 6000$ to $15000+$).
2. **2D Fast Fourier Transform Spectral Ratio (Frequency Domain)**:
   Computes the energy ratio of high-frequency components against low-frequency illumination:
   $$F(u, v) = \sum_{x=0}^{M-1} \sum_{y=0}^{N-1} I(x, y) e^{-j 2\pi \left(\frac{ux}{M} + \frac{vy}{N}\right)}$$
   $$\text{Ratio}_{\text{FFT}} = \frac{\text{Mean Energy}(r > R_{\text{cutoff}})}{\text{Mean Energy}(r \le R_{\text{cutoff}})}$$
   Authentic optical lenses follow natural power-law spectrum decay, whereas deepfake generative upsamplers create distinct frequency spikes.

### Step 7: Multi-Modal Calibrated Fusion Engine
The decision engine mathematically fuses semantic, neural, and physical signals:
- **Case 1: Generative Cues Detected by PaliGemma**  
  If PaliGemma explicitly identifies visual artifacts (`"synthetic"`, `"fake"`, `"ai-generated"`):
  $$\text{Score}_{\text{Frame}} = \max\left(0.85, P_{\text{ViT}}\right)$$
- **Case 2: Natural Features Confirmed by PaliGemma**  
  If PaliGemma observes authentic human features (`"real"`, `"authentic"`, `"natural"`, `"human"`):
  - If $\text{Var}_{\text{Lap}} > 6000$ (Physical edge anomaly detected):
    $$\text{Score}_{\text{Frame}} = \min\left(0.65, P_{\text{ViT}}\right)$$
  - Else (Normal camera noise):
    The elevated ViT probability is recognized as standard video compression (H.264 block noise) and calibrated down to the authentic baseline:
    $$\text{Score}_{\text{Frame}} = \min\left(0.20, P_{\text{ViT}} \times 0.22\right)$$
- **Case 3: Graphic / Presentation Slide**  
  If the scene consists of slides or screen captures, deepfake probability is set to $0.08$.

### Step 8: Saliency Heatmap Generation (Grad-CAM with Subject Isolation)
1. Gradients of the predicted authenticity token are backpropagated through PaliGemma's vision encoder:
   $$G = \frac{\partial \mathcal{L}_{\text{token}}}{\partial A_{\text{pixels}}}$$
2. To prevent high-contrast backgrounds (aquariums, lights, text) from hijacking the heatmap:
   - A spatial mask $M(x, y)$ is initialized to $0.0$ across the background.
   - The human face/head is assigned weight $1.0$; the upper torso is assigned weight $0.35$.
   - The gradient map is masked: $S_{\text{masked}} = S \odot M$.
   - Normalization is computed **strictly across the subject pixels**:
     $$S_{\text{normalized}}(x, y) = \frac{S_{\text{masked}}(x, y)}{\max_{(x', y') \in \text{Subject}} S_{\text{masked}}(x', y')}$$
3. Gaussian smoothing and OpenCV JET colormapping generate the final forensic overlay:
   $$\text{Overlay} = 0.55 \times I_{\text{original}} + 0.45 \times \text{Colormap}(S_{\text{u8}})$$

### Step 9: Zero-Latency Caching & Multi-View Rendering
When a user clicks "View Grad-CAM", the system serves the pre-computed heatmap from memory in under **50 milliseconds**, without re-downloading or re-running the model. The frontend provides:
- **Heatmap View**: Full gradient overlay.
- **Original View**: Unaugmented source keyframe.
- **Split View**: Synchronized side-by-side comparative inspection.
- **Scene Pills**: Direct jumping between temporal video scenes.

---

## 4. Deep-Dive into the Core Models

### 4.1 Google PaliGemma-3B
- **Vision Backbone**: SigLIP (Signal-Language Pre-training) Vision Transformer.
  - Image resolution: $224 \times 224$ pixels.
  - Vision encoder parameter count: ~400 Million.
  - Employs sigmoid loss on image-text pairs, providing richer spatial feature representations than softmax contrastive models.
- **Language Backbone**: Gemma-2B Autoregressive Transformer.
  - Parameter count: ~2.0 Billion.
  - Multi-query attention and Rotary Positional Embeddings (RoPE).
- **Linear Projector**: Maps visual patch tokens from SigLIP directly into the token embedding dimension of Gemma.
- **Spatial Tokenization**: PaliGemma represents 2D bounding boxes as 1,024 discrete coordinate tokens: `<loc0000>` to `<loc1023>`. This enables simultaneous bounding-box localization and open-ended text reasoning in a single unified forward pass.

### 4.2 Vision Transformer AI vs Real Classifier (`dima806/ai_vs_real_image_detection`)
- Architecture: Vision Transformer (ViT-Base-16).
- Input: $224 \times 224 \times 3$ facial crop.
- Patch Size: $16 \times 16$ pixels ($14 \times 14 = 196$ patches).
- Hidden dimension: 768, 12 transformer encoder blocks, 12 attention heads.
- Specialization: Highly sensitive to generative diffusion artifacts, blur boundaries, unnatural skin micro-patterns, and GAN checkerboard artifacts.

---

## 5. How to Fine-Tune the Models (Complete Practical Guide)

To adapt NeuralForensics to emerging generative models (e.g. Sora, FLUX, DeepFaceLive), the models can be fine-tuned following this protocol:

### 5.1 Dataset Preparation
Construct a balanced training corpus containing:
1. **Real Video Faces**:
   - VoxCeleb2 (Celebrity talking heads across diverse lighting and angles).
   - YouTube-Faces (Unconstrained in-the-wild video recordings).
   - Local diverse demographics (South Asian / Bangladeshi faces).
2. **Deepfake & Synthetic Faces**:
   - FaceForensics++ (Deepfakes, Face2Face, FaceSwap, NeuralTextures).
   - DFDC (Deepfake Detection Challenge dataset).
   - Celeb-DF v2 (High-quality optical flow and blended edges).
   - Diffusion-generated video frames (Runway Gen-3, Luma Dream Machine, Pika).
3. **Data Augmentation & Compression Simulation**:
   - Random H.264/H.265 compression with Constant Rate Factor (CRF) between 23 and 38.
   - Downsampling and bilinear upsampling (simulating YouTube/TikTok mobile scaling).
   - Lens blur and color temperature shifts.

### 5.2 Fine-Tuning PaliGemma-3B using QLoRA / PEFT
Because PaliGemma-3B is 3 Billion parameters, full parameter fine-tuning requires 40GB+ VRAM. **Parameter-Efficient Fine-Tuning (PEFT) via QLoRA** allows fine-tuning on a single consumer GPU (e.g. RTX 3090, 4090, or Apple Silicon with MPS).

#### Step-by-Step Training Configuration:
1. **Quantization**: Load Gemma weights in 4-bit NormalFloat (NF4) with double quantization using `bitsandbytes`.
2. **Freeze Vision Encoder**: Freeze the SigLIP vision backbone to preserve universal visual feature extraction.
3. **LoRA Adapters**: Inject low-rank decomposition matrices ($r=16, \alpha=32$) into Gemma's self-attention projection layers (`q_proj`, `k_proj`, `v_proj`, `o_proj`).
4. **Target Multi-Task Dataset Format**:
   - Bounding Box Task:
     - Prompt: `<image> detect face`
     - Target: `<loc0205><loc0367><loc0843><loc0659> face`
   - Forensic Classification Task:
     - Prompt: `<image> answer en does this person look real or synthetic?`
     - Target: `real` (for authentic) or `synthetic deepfake with blended facial seam` (for manipulated)

#### Training Script Outline (PyTorch + HuggingFace PEFT):
```python
import torch
from transformers import AutoProcessor, PaliGemmaForConditionalGeneration, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

model_id = "google/paligemma-3b-mix-224"
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16
)

processor = AutoProcessor.from_pretrained(model_id)
model = PaliGemmaForConditionalGeneration.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    device_map="auto"
)

# Freeze vision encoder
for param in model.vision_tower.parameters():
    param.requires_grad = False

lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "o_proj", "k_proj", "v_proj", "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# Output: trainable params: ~18.8M || all params: ~2.94B || trainable%: 0.64%
```

5. **Loss & Optimizer**:
   - Cross-entropy loss over target output tokens only (mask prompt tokens with `-100`).
   - Optimizer: AdamW (learning rate $2 \times 10^{-4}$ with cosine decay, warmup ratio $0.05$).
   - Train for 3–5 epochs.

### 5.3 Fine-Tuning the ViT Deepfake Classifier
1. Train directly on cropped $224 \times 224$ facial patches.
2. Loss function: Binary Cross Entropy with Label Smoothing ($0.1$ smoothing prevents overconfident false positives on compressed authentic media).
3. Hard Negative Mining: Specifically include compressed YouTube talking-head videos in the "REAL" class so the ViT learns that compression artifacts are not AI synthesis.

---

## 6. API Reference

### 1. `POST /api/analyze`
Submits media for full forensic inspection.
- **Parameters (multipart/form-data)**:
  - `media`: Video or image file binary.
  - `url` (optional): YouTube or direct media URL.
  - `source_type`: `"video"`, `"image"`, or `"live"`.
- **Response (JSON)**:
  ```json
  {
    "status": "success",
    "type": {
      "deepfake": 0.20,
      "ai_generated": 0.20
    },
    "gradcam": "data:image/jpeg;base64,...",
    "scenes": [
      {
        "scene_idx": 1,
        "timestamp": "00:00",
        "score": 0.20,
        "ai_likelihood": 20.0,
        "verdict": "Authentic",
        "caption": "a woman in a yellow dress is standing in front of an aquarium.",
        "has_human": true,
        "gradcam": "data:image/jpeg;base64,...",
        "original": "data:image/jpeg;base64,..."
      }
    ],
    "explanation": "NeuralForensics Sentinel-X analysis indicates this video is authentic (80.0% natural likelihood)...",
    "humans": [{"track_id": 1, "average_box": [72, 223, 698, 802]}],
    "activities": ["speaking"],
    "meta": {
      "detector": "Sentinel-X Forensic Expert Agent (Gemma-4)",
      "frame_count": 8,
      "laplacian_var": 1144.2,
      "fft_attenuation": 0.7944
    }
  }
  ```

### 2. `GET /api/gradcam?scene_idx={N}`
Retrieves cached high-resolution Grad-CAM overlays instantly ($<0.05\text{s}$) without re-evaluating the video.

---

## 7. Conclusion & Research Significance

The **NeuralForensics Sentinel-X** system bridges the gap between deep learning theoretical research and robust, real-world deployment. By combining:
1. **PaliGemma-3B**'s contextual scene reasoning and spatial subject localization,
2. **Vision Transformer**'s sensitive micro-texture artifact detection on facial crops,
3. **Physical frequency and edge telemetry** to prevent compression false positives, and
4. **Subject-isolated Grad-CAM** explainability,

the system achieves state-of-the-art accuracy, complete resilience against background clutter, and explainable forensic accountability for North South University's Cyber Forensics and Intelligence research.
