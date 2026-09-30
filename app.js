const ENGINE = "model1";
const ENGINE_LABEL = "Sentinel-X Expert Engine";

const TERMINAL_LINES = [
  "> [SENTINEL-X] Initializing forensic reasoning engine...",
  "> [YOLO] Detecting humans & tracking activities...",
  "> [CLASSIFIER] Scoring synthetic / AI artifact likelihood...",
  "> [FFT] Running spectral artifact analysis on frames...",
  "> [SENTINEL-X] Writing natural-language forensic report...",
];

const state = {
  webcamStream: null,
  selectedFile: null,
  selectedFileUrl: "",
  selectedSource: null, // "camera" | "file" | "url"
  scanInProgress: false,
  lastAnalyzedUrl: "",
  lastCameraFile: null,
  lastResultData: null,
  scenes: [],
  activeSceneIndex: 0,
  modalViewMode: "heatmap", // "heatmap" | "original" | "split"
};

const $ = (id) => document.getElementById(id);

const el = {
  appShell: $("appShell"),
  nav: $("mainNav"),
  pages: Array.from(document.querySelectorAll(".page")),
  statusBadge: $("statusBadge"),
  modeBadge: $("modeBadge"),
  // sources
  enableCameraButton: $("enableCameraButton"),
  cameraStatus: $("cameraStatus"),
  dropZone: $("dropZone"),
  fileInput: $("fileInput"),
  fileMeta: $("fileMeta"),
  clearFileButton: $("clearFileButton"),
  urlInput: $("urlInput"),
  analyzeUrlButton: $("analyzeUrlButton"),
  urlStatus: $("urlStatus"),
  // stage
  activeSourceTitle: $("activeSourceTitle"),
  viewportState: $("viewportState"),
  webcamVideo: $("webcamVideo"),
  fileVideo: $("fileVideo"),
  stagePlaceholder: $("stagePlaceholder"),
  mediaStage: $("mediaStage"),
  terminalOverlay: $("terminalOverlay"),
  analyzeButton: $("analyzeButton"),
  activityStatus: $("activityStatus"),
  // verdict / results
  verdictStatus: $("verdictStatus"),
  verdictHeadline: $("verdictHeadline"),
  verdictCopy: $("verdictCopy"),
  scoreRing: $("scoreRing"),
  humanCountBadge: $("humanCountBadge"),
  humanList: $("humanList"),
  activitiesList: $("activitiesList"),
  laplacianValue: $("laplacianValue"),
  fftValue: $("fftValue"),
  metricSource: $("metricSource"),
  metricSrcType: $("metricSrcType"),
  metricFrames: $("metricFrames"),
  metricEngine: $("metricEngine"),
  metricConfidence: $("metricConfidence"),
  gotoReport: $("gotoReport"),
  gotoAnalyze: $("gotoAnalyze"),
  // scene gallery
  sceneAnalysisCard: $("sceneAnalysisCard"),
  sceneCountBadge: $("sceneCountBadge"),
  sceneGallery: $("sceneGallery"),
  // report evidence
  reportEvidenceSection: $("reportEvidenceSection"),
  reportEvidenceGrid: $("reportEvidenceGrid"),
  // gradcam modal
  viewGradcamBtn: $("viewGradcamBtn"),
  gradcamModal: $("gradcamModal"),
  closeGradcamBtn: $("closeGradcamBtn"),
  gradcamImage: $("gradcamImage"),
  gradcamLoading: $("gradcamLoading"),
  modalSceneTitle: $("modalSceneTitle"),
  modalSceneSubtitle: $("modalSceneSubtitle"),
  modalViewModeToggle: $("modalViewModeToggle"),
  btnModeHeatmap: $("btnModeHeatmap"),
  btnModeOriginal: $("btnModeOriginal"),
  btnModeSplit: $("btnModeSplit"),
  modalSceneNav: $("modalSceneNav"),
  modalScenePills: $("modalScenePills"),
  gradcamSingleView: $("gradcamSingleView"),
  gradcamSplitView: $("gradcamSplitView"),
  gradcamSplitOriginal: $("gradcamSplitOriginal"),
  gradcamSplitHeatmap: $("gradcamSplitHeatmap"),
  modalSceneFooter: $("modalSceneFooter"),
  modalSceneVerdict: $("modalSceneVerdict"),
  modalSceneTime: $("modalSceneTime"),
  modalSceneCaption: $("modalSceneCaption"),
  // fullscreen camera overlay
  cameraFullscreenOverlay: $("cameraFullscreenOverlay"),
  closeCameraButton: $("closeCameraButton"),
  fullscreenWebcamVideo: $("fullscreenWebcamVideo"),
  fullscreenTerminalOverlay: $("fullscreenTerminalOverlay"),
  fullscreenAnalyzeButton: $("fullscreenAnalyzeButton"),
  fullscreenViewResultsButton: $("fullscreenViewResultsButton"),
  fullscreenCameraStatus: $("fullscreenCameraStatus"),
  resultsNoticeBanner: $("resultsNoticeBanner"),
  resultsNoticeText: $("resultsNoticeText"),
  bannerGradcamBtn: $("bannerGradcamBtn"),
  // report
  reportMeta: $("reportMeta"),
  explanationContent: $("explanationContent"),
};

/* ------------------------------------------------------------------ */
/* Page navigation                                                     */
/* ------------------------------------------------------------------ */

function showPage(name) {
  el.pages.forEach((page) => {
    const active = page.dataset.page === name;
    page.classList.toggle("is-active", active);
  });
  Array.from(el.nav.querySelectorAll(".nav-item")).forEach((item) => {
    item.classList.toggle("is-active", item.dataset.page === name);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

el.nav.addEventListener("click", (e) => {
  const item = e.target.closest(".nav-item");
  if (item) showPage(item.dataset.page);
});
el.gotoReport.addEventListener("click", () => showPage("report"));
el.gotoAnalyze.addEventListener("click", () => showPage("analyze"));

/* ------------------------------------------------------------------ */
/* Source helpers                                                       */
/* ------------------------------------------------------------------ */

function setStatus(classes) {
  el.statusBadge.className = "status-badge " + classes;
}

function setViewport(classes) {
  el.viewportState.className = "viewport-state " + classes;
}

function selectSource(source) {
  state.selectedSource = source;
  const labels = {
    camera: "Live camera feed",
    file: "Uploaded media",
    url: "URL media",
  };
  el.activeSourceTitle.textContent = labels[source] || "No source selected";
  el.analyzeButton.disabled = false;
  el.activityStatus.textContent = "Source ready — press Run Analysis to scan.";
}

function clearSelection() {
  state.selectedSource = null;
  state.selectedFile = null;
  state.selectedFileUrl = "";
  el.activeSourceTitle.textContent = "No source selected";
  el.analyzeButton.disabled = true;
  el.fileVideo.hidden = true;
  el.fileVideo.removeAttribute("src");
  el.stagePlaceholder.hidden = false;
  el.activityStatus.textContent = "System ready — choose a source to begin.";
}

/* ------------------------------------------------------------------ */
/* Camera                                                              */
/* ------------------------------------------------------------------ */

async function enableCamera() {
  if (state.webcamStream) {
    state.webcamStream.getTracks().forEach((t) => t.stop());
    state.webcamStream = null;
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    el.cameraStatus.textContent = "Camera not supported in this browser.";
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 1280, height: 720 },
      audio: false,
    });
    state.webcamStream = stream;
    el.cameraStatus.textContent = "Camera active.";
    el.enableCameraButton.textContent = "Stop Camera";
    selectSource("camera");

    // Show fullscreen camera overlay
    showFullscreenCamera(stream);
  } catch (err) {
    el.cameraStatus.textContent = "Camera permission denied or unavailable.";
  }
}

function showFullscreenCamera(stream) {
  const overlay = el.cameraFullscreenOverlay;
  const fsVideo = el.fullscreenWebcamVideo;
  fsVideo.srcObject = stream;
  overlay.hidden = false;
  document.body.classList.add("camera-active");
  if (el.fullscreenCameraStatus) {
    el.fullscreenCameraStatus.textContent = "Camera active \u2014 frame ready for deepfake scan";
  }
}

function hideFullscreenCamera() {
  const overlay = el.cameraFullscreenOverlay;
  const fsVideo = el.fullscreenWebcamVideo;
  if (fsVideo) { fsVideo.srcObject = null; }
  overlay.hidden = true;
  document.body.classList.remove("camera-active");
}

function stopCameraCompletely() {
  if (state.webcamStream) {
    state.webcamStream.getTracks().forEach((t) => t.stop());
    state.webcamStream = null;
  }
  state.selectedSource = null;
  el.webcamVideo.srcObject = null;
  el.webcamVideo.hidden = true;
  el.stagePlaceholder.hidden = false;
  el.cameraStatus.textContent = "Camera is off.";
  el.enableCameraButton.textContent = "Enable Camera";
  el.analyzeButton.disabled = true;
  el.activeSourceTitle.textContent = "No source selected";
  hideFullscreenCamera();
}

el.enableCameraButton.addEventListener("click", () => {
  if (state.webcamStream) {
    stopCameraCompletely();
    return;
  }
  enableCamera();
});

el.closeCameraButton.addEventListener("click", () => {
  stopCameraCompletely();
});



/* ------------------------------------------------------------------ */
/* Fullscreen camera analysis                                          */
/* ------------------------------------------------------------------ */

el.fullscreenAnalyzeButton.addEventListener("click", async () => {
  if (state.scanInProgress) return;

  const form = new FormData();
  form.append("engine", ENGINE);
  form.append("source_type", "camera");
  try {
    const file = await captureCameraFrame(el.fullscreenWebcamVideo);
    form.append("media", file, "camera_capture.jpg");
    state.lastCameraFile = file;
  } catch (err) {
    if (el.fullscreenCameraStatus) el.fullscreenCameraStatus.textContent = "Could not capture frame.";
    return;
  }

  state.scanInProgress = true;
  el.fullscreenAnalyzeButton.disabled = true;
  if (el.fullscreenViewResultsButton) el.fullscreenViewResultsButton.hidden = true;
  if (el.fullscreenCameraStatus) el.fullscreenCameraStatus.textContent = "Scanning frame with Sentinel-X & PaliGemma VLM...";
  setStatus("is-running");

  // Show terminal in fullscreen overlay
  const fsTerminal = el.fullscreenTerminalOverlay;
  if (fsTerminal) {
    fsTerminal.classList.add("is-active");
    fsTerminal.textContent = TERMINAL_LINES.join("\n");
  }

  try {
    const res = await fetch("/api/analyze", { method: "POST", body: form });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data || data.status !== "success") {
      throw new Error(
        (data && data.error && (data.error.message || data.error)) ||
          "Analysis failed with status " + res.status
      );
    }
    renderResults(data);
    if (el.fullscreenCameraStatus) {
      el.fullscreenCameraStatus.textContent = "✅ Analysis Complete! Transitioning to Results & Heatmap...";
    }
    if (el.fullscreenViewResultsButton) {
      el.fullscreenViewResultsButton.hidden = false;
    }
    setTimeout(() => {
      hideFullscreenCamera();
      showPage("results");
      window.scrollTo({ top: 0, behavior: "smooth" });
    }, 900);
  } catch (err) {
    renderError(err.message || String(err));
  } finally {
    state.scanInProgress = false;
    el.fullscreenAnalyzeButton.disabled = false;
    if (fsTerminal) {
      fsTerminal.classList.remove("is-active");
      fsTerminal.textContent = "";
    }
  }
});

if (el.fullscreenViewResultsButton) {
  el.fullscreenViewResultsButton.addEventListener("click", () => {
    hideFullscreenCamera();
    showPage("results");
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

if (el.bannerGradcamBtn) {
  el.bannerGradcamBtn.addEventListener("click", () => {
    el.viewGradcamBtn.click();
  });
}

/* ------------------------------------------------------------------ */
/* File upload                                                         */
/* ------------------------------------------------------------------ */

async function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function bytesLabel(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(2) + " MB";
}

async function handleFile(file) {
  if (!file) return;
  const isVideo = file.type.startsWith("video/");
  const isImage = file.type.startsWith("image/");
  if (!isVideo && !isImage) {
    el.fileMeta.textContent = "Unsupported file type. Use MP4, JPG, PNG or WebP.";
    return;
  }
  state.selectedFile = file;
  state.selectedSource = "file";
  el.fileMeta.textContent =
    file.name + " // " + bytesLabel(file.size);
  el.clearFileButton.hidden = false;

  if (isVideo) {
    const dataUrl = await readFileAsDataUrl(file);
    state.selectedFileUrl = dataUrl;
    el.fileVideo.src = dataUrl;
    el.fileVideo.hidden = false;
    el.webcamVideo.hidden = true;
    el.stagePlaceholder.hidden = true;
  } else {
    const objectUrl = URL.createObjectURL(file);
    state.selectedFileUrl = objectUrl;
    el.fileVideo.src = objectUrl;
    el.fileVideo.hidden = false;
    el.webcamVideo.hidden = true;
    el.stagePlaceholder.hidden = true;
  }
  selectSource("file");
}

el.dropZone.addEventListener("click", () => el.fileInput.click());
el.dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  el.dropZone.classList.add("drag");
});
el.dropZone.addEventListener("dragleave", () => el.dropZone.classList.remove("drag"));
el.dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  el.dropZone.classList.remove("drag");
  const file = e.dataTransfer.files && e.dataTransfer.files[0];
  if (file) handleFile(file);
});
el.fileInput.addEventListener("change", (e) => {
  const file = e.target.files && e.target.files[0];
  if (file) handleFile(file);
});
el.clearFileButton.addEventListener("click", () => {
  el.fileInput.value = "";
  clearSelection();
  el.fileMeta.textContent = "MP4 · WebM · JPG · PNG · WebP";
  el.clearFileButton.hidden = true;
});

/* ------------------------------------------------------------------ */
/* URL analysis                                                        */
/* ------------------------------------------------------------------ */

async function analyzeUrl() {
  const url = (el.urlInput.value || "").trim();
  if (!url) {
    el.urlStatus.textContent = "Paste a valid link first.";
    return;
  }
  if (state.webcamStream) {
    state.webcamStream.getTracks().forEach((t) => t.stop());
    state.webcamStream = null;
    el.webcamVideo.hidden = true;
    el.enableCameraButton.textContent = "Enable Camera";
  }
  state.selectedFile = null;
  state.selectedSource = "url";
  selectSource("url");
  el.fileVideo.hidden = true;
  el.stagePlaceholder.hidden = true;
  el.urlStatus.textContent = "Fetching media and analyzing...";
  await runAnalysis(url);
}

el.analyzeUrlButton.addEventListener("click", analyzeUrl);
el.urlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") analyzeUrl();
});

/* ------------------------------------------------------------------ */
/* Analysis                                                            */
/* ------------------------------------------------------------------ */

function playTerminal() {
  if (el.terminalOverlay) {
    el.terminalOverlay.classList.add("is-active");
    el.terminalOverlay.textContent = TERMINAL_LINES.join("\n");
  }
}

function stopTerminal() {
  if (el.terminalOverlay) {
    el.terminalOverlay.classList.remove("is-active");
    el.terminalOverlay.textContent = "";
  }
}

async function runAnalysis(pendingUrl) {
  if (state.scanInProgress) return;

  const form = new FormData();
  form.append("engine", ENGINE);

  if (state.selectedSource === "url" || pendingUrl) {
    const targetUrl = pendingUrl || el.urlInput.value.trim();
    form.append("url", targetUrl);
    state.lastAnalyzedUrl = targetUrl;
  } else if (state.selectedSource === "file" && state.selectedFile) {
    form.append("media", state.selectedFile);
  } else if (state.selectedSource === "camera" && state.webcamStream) {
    try {
      const file = await captureCameraFrame(el.fullscreenWebcamVideo || el.webcamVideo);
      form.append("media", file, "camera_capture.jpg");
      form.append("source_type", "camera");
      state.lastCameraFile = file;
    } catch (err) {
      el.verdictCopy.textContent = "Could not capture a frame from the camera.";
      return;
    }
  } else {
    return;
  }

  state.scanInProgress = true;
  el.analyzeButton.disabled = true;
  el.activityStatus.textContent = "Analyzing...";
  setStatus("is-running");
  setViewport("is-running");
  playTerminal();

  try {
    const res = await fetch("/api/analyze", { method: "POST", body: form });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data || data.status !== "success") {
      throw new Error(
        (data && data.error && (data.error.message || data.error)) ||
          "Analysis failed with status " + res.status
      );
    }
    renderResults(data);
  } catch (err) {
    renderError(err.message || String(err));
  } finally {
    state.scanInProgress = false;
    el.analyzeButton.disabled = false;
    stopTerminal();
  }
}

el.analyzeButton.addEventListener("click", () => {
  if (state.selectedSource === "url") {
    analyzeUrl();
  } else {
    runAnalysis();
  }
});

function captureCameraFrame(videoEl) {
  return new Promise((resolve, reject) => {
    const video = videoEl || el.fullscreenWebcamVideo || el.webcamVideo;
    if (!video || !video.videoWidth) return reject(new Error("no-frame"));
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("capture-failed"))),
      "image/jpeg",
      0.9
    );
  });
}

/* ------------------------------------------------------------------ */
/* Rendering                                                           */
/* ------------------------------------------------------------------ */

function pct(value, digits) {
  return Math.round((Number(value) || 0) * 100);
}

function renderResults(data) {
  state.lastResultData = data;
  state.scenes = data.scenes || [];
  state.activeSceneIndex = 0;

  const type = data.type || {};
  const prob = Number(type.ai_generated) || 0;
  const confidence = pct(prob);
  const isDeepfake = prob > 0.5;
  const meta = data.meta || {};

  // Verdict
  el.verdictStatus.dataset.state = isDeepfake ? "alert" : "secure";
  el.verdictHeadline.textContent = isDeepfake
    ? "Deepfake / AI suspected"
    : "Likely authentic media";
  el.verdictCopy.textContent = isDeepfake
    ? "This media shows a strong likelihood of AI generation or manipulation. Review the telemetry, keyframes, and AI report for detail."
    : "This media shows no strong signs of AI generation or manipulation. Review the telemetry, keyframes, and AI report for detail.";
  el.scoreRing.textContent = confidence + "%";
  el.scoreRing.dataset.state = isDeepfake ? "alert" : "secure";
  
  if (data.status === "success") {
    el.viewGradcamBtn.hidden = false;
    if (el.resultsNoticeBanner) {
      el.resultsNoticeBanner.hidden = false;
      if (el.resultsNoticeText) {
        el.resultsNoticeText.innerHTML = "<b>Analysis Complete:</b> " + (isDeepfake ? "⚠️ Deepfake Suspicion Detected" : "✅ Verified Authentic Natural Capture") + " (" + confidence + "%). Click <b>\"Inspect Heatmap\"</b> to see the visual explanation.";
      }
    }
  } else {
    el.viewGradcamBtn.hidden = true;
    if (el.resultsNoticeBanner) el.resultsNoticeBanner.hidden = true;
  }

  el.metricEngine.textContent = ENGINE_LABEL;
  el.metricSource.textContent = getSourceLabel(data);
  el.metricSrcType.textContent = (meta.source_type || "media").replace("_", " ");
  el.metricFrames.textContent = meta.frame_count != null ? meta.frame_count : "--";
  el.metricConfidence.textContent = confidence + "%";

  // Humans & activities
  const humans = data.humans || [];
  el.humanCountBadge.textContent = humans.length;
  if (humans.length === 0) {
    el.humanList.innerHTML = "<li class='empty'>No humans detected.</li>";
  } else {
    el.humanList.innerHTML = humans
      .map(
        (h) =>
          "<li>" +
          "<span class='person'>Track #" +
          (h.track_id != null ? h.track_id : "?") +
          "</span>" +
          "<span class='act'>" +
          (h.primary_activity || "—") +
          "</span>" +
          (h.average_box
            ? "<span class='box'>[" + h.average_box.join(", ") + "]</span>"
            : "") +
          "</li>"
      )
      .join("");
  }
  const activities = data.activities || [];
  el.activitiesList.innerHTML =
    activities.length === 0
      ? "<span class='empty'>No activities identified</span>"
      : activities
          .map((a) => "<span class='tag taghot'>" + a + "</span>")
          .join("");

  el.laplacianValue.textContent =
    meta.laplacian_var != null ? Number(meta.laplacian_var).toFixed(2) : "--";
  el.fftValue.textContent =
    meta.fft_attenuation != null ? Number(meta.fft_attenuation).toFixed(4) : "--";

  // Render Scene-by-Scene Forensic Breakdown Gallery
  if (state.scenes && state.scenes.length > 0) {
    el.sceneAnalysisCard.hidden = false;
    el.sceneCountBadge.textContent = state.scenes.length + (state.scenes.length === 1 ? " Keyframe" : " Keyframes");
    el.sceneGallery.innerHTML = state.scenes
      .map((s, idx) => {
        const isSusp = s.verdict === "Suspicious" || s.score >= 0.5;
        const badgeClass = isSusp ? "alert" : "secure";
        const badgeText = isSusp ? `Suspicious (${s.ai_likelihood}%)` : `Authentic (${(100 - s.ai_likelihood).toFixed(1)}%)`;
        const initialImg = s.gradcam || s.original;
        return `
          <div class="scene-card" data-idx="${idx}">
            <div class="scene-card-header">
              <span class="scene-card-title">
                <span>⏱️</span> Scene #${s.scene_idx} (${s.timestamp})
              </span>
              <span class="scene-badge ${badgeClass}">${badgeText}</span>
            </div>
            <div class="scene-img-box" data-idx="${idx}">
              <img class="scene-img" id="sceneImg_${idx}" src="${initialImg}" alt="Scene ${s.scene_idx}" data-mode="heatmap" />
              <button class="scene-toggle-pill" data-idx="${idx}" title="Toggle between Grad-CAM heatmap and original frame">Heatmap</button>
            </div>
            <div class="scene-card-body">
              <p class="scene-caption">${s.caption || 'Forensic visual capture'}</p>
              <button class="scene-inspect-btn" data-idx="${idx}">
                <span>🔬</span> Inspect Saliency Gradients
              </button>
            </div>
          </div>
        `;
      })
      .join("");

    // Wire up toggle pill and inspect buttons in scene cards
    el.sceneGallery.querySelectorAll(".scene-toggle-pill").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.idx, 10);
        const img = document.getElementById(`sceneImg_${idx}`);
        const sc = state.scenes[idx];
        if (!img || !sc) return;
        if (img.dataset.mode === "heatmap") {
          img.dataset.mode = "original";
          img.src = sc.original || sc.gradcam;
          btn.textContent = "Original";
        } else {
          img.dataset.mode = "heatmap";
          img.src = sc.gradcam || sc.original;
          btn.textContent = "Heatmap";
        }
      });
    });

    el.sceneGallery.querySelectorAll(".scene-inspect-btn, .scene-img-box").forEach((box) => {
      box.addEventListener("click", () => {
        const idx = parseInt(box.dataset.idx, 10);
        openGradcamModal(idx);
      });
    });

    // Populate Report Evidence Gallery
    el.reportEvidenceSection.hidden = false;
    el.reportEvidenceGrid.innerHTML = state.scenes
      .map((s) => {
        const isSusp = s.verdict === "Suspicious" || s.score >= 0.5;
        const badgeClass = isSusp ? "alert" : "secure";
        const badgeText = isSusp ? `Suspicious ${s.ai_likelihood}%` : `Authentic ${(100 - s.ai_likelihood).toFixed(1)}%`;
        return `
          <div class="report-evidence-card">
            <img class="report-evidence-img" src="${s.gradcam || s.original}" alt="Evidence Scene ${s.scene_idx}" />
            <div class="report-evidence-meta">
              <div class="evidence-tag-row">
                <span>Scene #${s.scene_idx} &bull; ${s.timestamp}</span>
                <span class="badge ${badgeClass}">${badgeText}</span>
              </div>
              <span style="color: var(--muted); font-size: 0.76rem; line-height: 1.35;">${s.caption}</span>
            </div>
          </div>
        `;
      })
      .join("");
  } else {
    el.sceneAnalysisCard.hidden = true;
    el.reportEvidenceSection.hidden = true;
  }

  // Report
  const now = new Date().toLocaleString();
  el.reportMeta.innerHTML =
    "<span>Source: <b>" + getSourceLabel(data) + "</b></span>" +
    "<span>Engine: <b>" + ENGINE_LABEL + "</b></span>" +
    "<span>Confidence: <b>" + confidence + "%</b></span>" +
    "<span>Analyzed at: <b>" + now + "</b></span>";
  el.explanationContent.innerHTML =
    data.explanation
      ? data.explanation.split("\n").filter(Boolean).map((p) => "<p>" + p + "</p>").join("")
      : "<p class='placeholder'>No explanation was generated.</p>";

  el.activityStatus.textContent =
    "Analysis complete — " + (isDeepfake ? "deepfake suspected" : "likely authentic") +
    " (" + confidence + "%).";
  setStatus(isDeepfake ? "is-alert" : "is-secure");
  setViewport("is-done");
  showPage("results");
}

function renderError(message) {
  el.verdictStatus.dataset.state = "error";
  el.verdictHeadline.textContent = "Analysis could not be completed";
  el.verdictCopy.textContent = message || "An unexpected error occurred.";
  el.scoreRing.textContent = "—";
  el.activityStatus.textContent = "Analysis failed — see Results for the reason.";
  if (el.resultsNoticeBanner) el.resultsNoticeBanner.hidden = true;
  setStatus("is-idle");
  setViewport("is-done");
  el.explanationContent.innerHTML =
    "<p class='placeholder'>" + message + "</p>";
  el.reportMeta.innerHTML = "";
  showPage("results");
}

function getSourceLabel(data) {
  const meta = data.meta || {};
  if (meta.source_type) {
    if (String(meta.source_type).indexOf("video") !== -1) {
      return state.selectedSource === "url" && el.urlInput.value
        ? el.urlInput.value.replace(/^https?:\/\//, "").slice(0, 48) + "…"
        : (state.selectedFile && state.selectedFile.name) || "Video file";
    }
    if (meta.source_type === "camera") {
      return "Live Camera Optical Stream";
    }
    return (state.selectedFile && state.selectedFile.name) || "Image file";
  }
  return "Unknown media source";
}

/* ------------------------------------------------------------------ */
/* Grad-CAM Heatmap & Scene Inspection Modal                          */
/* ------------------------------------------------------------------ */

function updateModalSceneView() {
  const sc = state.scenes[state.activeSceneIndex];
  if (!sc) return;

  const isSusp = sc.verdict === "Suspicious" || sc.score >= 0.5;
  el.modalSceneTitle.textContent = `Scene #${sc.scene_idx} Saliency Map (${sc.timestamp})`;
  el.modalSceneSubtitle.textContent = `PaliGemma-3B Attention & ViT Density (${sc.ai_likelihood}% synthetic likelihood)`;
  
  el.modalSceneVerdict.textContent = isSusp ? `Suspicious (${sc.ai_likelihood}%)` : `Authentic (${(100 - sc.ai_likelihood).toFixed(1)}%)`;
  el.modalSceneVerdict.className = `badge ${isSusp ? "alert" : "secure"}`;
  el.modalSceneTime.textContent = `Keyframe: ${sc.timestamp}`;
  el.modalSceneCaption.textContent = sc.caption;

  // Update nav pills
  el.modalScenePills.querySelectorAll(".modal-scene-pill").forEach((pill, idx) => {
    pill.classList.toggle("active", idx === state.activeSceneIndex);
  });

  // Display based on view mode
  if (state.modalViewMode === "split") {
    el.gradcamSingleView.hidden = true;
    el.gradcamSplitView.hidden = false;
    el.gradcamSplitOriginal.src = sc.original || sc.gradcam;
    el.gradcamSplitHeatmap.src = sc.gradcam || sc.original;
    el.gradcamLoading.hidden = true;
  } else {
    el.gradcamSplitView.hidden = true;
    el.gradcamSingleView.hidden = false;
    el.gradcamImage.hidden = false;
    el.gradcamLoading.hidden = true;
    el.gradcamImage.src = state.modalViewMode === "original" ? (sc.original || sc.gradcam) : (sc.gradcam || sc.original);
  }
}

async function openGradcamModal(sceneIndex = 0) {
  el.gradcamModal.hidden = false;
  state.activeSceneIndex = sceneIndex;

  if (state.scenes && state.scenes.length > 0) {
    el.modalSceneNav.hidden = state.scenes.length <= 1;
    el.modalScenePills.innerHTML = state.scenes
      .map((s, idx) => {
        const isSusp = s.verdict === "Suspicious" || s.score >= 0.5;
        const icon = isSusp ? "⚠️" : "✅";
        return `
          <button class="modal-scene-pill ${idx === state.activeSceneIndex ? 'active' : ''}" data-idx="${idx}">
            <span>${icon}</span> Scene ${s.scene_idx} (${s.timestamp})
          </button>
        `;
      })
      .join("");

    el.modalScenePills.querySelectorAll(".modal-scene-pill").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.activeSceneIndex = parseInt(btn.dataset.idx, 10);
        updateModalSceneView();
      });
    });

    updateModalSceneView();
    return;
  }

  // Fallback: If no scenes are cached, fetch /api/gradcam
  el.gradcamLoading.hidden = false;
  el.gradcamSingleView.hidden = false;
  el.gradcamSplitView.hidden = true;
  el.gradcamImage.hidden = true;
  el.modalSceneNav.hidden = true;

  let form = new FormData();
  form.append("engine", "model1");

  if (state.lastAnalyzedUrl) {
    form.append("url", state.lastAnalyzedUrl);
  } else if (state.selectedSource === "url" && el.urlInput.value) {
    form.append("url", el.urlInput.value.trim());
  } else if (state.selectedSource === "file" && state.selectedFile) {
    form.append("media", state.selectedFile);
  } else if (state.selectedSource === "camera" && state.lastCameraFile) {
    form.append("media", state.lastCameraFile, "camera_capture.jpg");
    form.append("source_type", "camera");
  }

  try {
    const res = await fetch("/api/gradcam", { method: "POST", body: form });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data || !data.gradcam) {
      throw new Error(
        (data && data.error && (data.error.message || data.error)) ||
          "Failed to retrieve Grad-CAM decision heatmap."
      );
    }
    if (data.scenes && data.scenes.length > 0) {
      state.scenes = data.scenes;
      openGradcamModal(0);
      return;
    }
    el.gradcamImage.onload = () => {
      el.gradcamLoading.hidden = true;
      el.gradcamImage.hidden = false;
    };
    el.gradcamImage.src = data.gradcam;
  } catch (err) {
    alert("Error loading Grad-CAM: " + err.message);
    el.gradcamModal.hidden = true;
    el.gradcamLoading.hidden = true;
  }
}

// Wire modal view mode switcher
if (el.btnModeHeatmap) {
  el.btnModeHeatmap.addEventListener("click", () => {
    state.modalViewMode = "heatmap";
    el.btnModeHeatmap.classList.add("active");
    el.btnModeOriginal.classList.remove("active");
    el.btnModeSplit.classList.remove("active");
    updateModalSceneView();
  });
}
if (el.btnModeOriginal) {
  el.btnModeOriginal.addEventListener("click", () => {
    state.modalViewMode = "original";
    el.btnModeHeatmap.classList.remove("active");
    el.btnModeOriginal.classList.add("active");
    el.btnModeSplit.classList.remove("active");
    updateModalSceneView();
  });
}
if (el.btnModeSplit) {
  el.btnModeSplit.addEventListener("click", () => {
    state.modalViewMode = "split";
    el.btnModeHeatmap.classList.remove("active");
    el.btnModeOriginal.classList.remove("active");
    el.btnModeSplit.classList.add("active");
    updateModalSceneView();
  });
}

el.viewGradcamBtn.addEventListener("click", () => {
  const maxIdx = state.scenes.findIndex((s) => s.score >= 0.5);
  openGradcamModal(maxIdx >= 0 ? maxIdx : 0);
});

if (el.bannerGradcamBtn) {
  el.bannerGradcamBtn.addEventListener("click", () => {
    const maxIdx = state.scenes.findIndex((s) => s.score >= 0.5);
    openGradcamModal(maxIdx >= 0 ? maxIdx : 0);
  });
}

el.closeGradcamBtn.addEventListener("click", () => {
  el.gradcamModal.hidden = true;
});

/* ------------------------------------------------------------------ */
/* Init                                                                */
/* ------------------------------------------------------------------ */

setStatus("is-idle");
setViewport("is-idle");
showPage("analyze");
