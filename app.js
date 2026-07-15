const AUTO_ANALYZE_ON_FILE_LOAD = false;

const TERMINAL_LINES = [
  "> [SYS] Extracting structural face meshes...",
  "> [SYS] Analyzing frame-by-frame temporal consistency...",
  "> [SYS] Querying NSU Neural Matrix Verification Engine...",
];

const state = {
  webcamStream: null,
  selectedModel: "model1",
  selectedFile: null,
  selectedFileUrl: "",
  scanInProgress: false,
  terminalIntervalId: null,
  terminalTimeoutId: null,
};

const elements = {
  appShell: document.getElementById("appShell"),
  webcamVideo: document.getElementById("webcamVideo"),
  fileVideo: document.getElementById("fileVideo"),
  stagePlaceholder: document.getElementById("stagePlaceholder"),
  terminalOverlay: document.getElementById("terminalOverlay"),
  enableCameraButton: document.getElementById("enableCameraButton"),
  clearFileButton: document.getElementById("clearFileButton"),
  cameraStatus: document.getElementById("cameraStatus"),
  dropZone: document.getElementById("dropZone"),
  fileInput: document.getElementById("fileInput"),
  fileMeta: document.getElementById("fileMeta"),
  analyzeButton: document.getElementById("analyzeButton"),
  statusBadge: document.getElementById("statusBadge"),
  modeBadge: document.getElementById("modeBadge"),
  verdictHeadline: document.getElementById("verdictHeadline"),
  verdictCopy: document.getElementById("verdictCopy"),
  metricSource: document.getElementById("metricSource"),
  metricConfidence: document.getElementById("metricConfidence"),
  metricScoreLabel: document.getElementById("metricScoreLabel"),
  metricEngine: document.getElementById("metricEngine"),
  activityStatus: document.getElementById("activityStatus"),
  liveSourceCard: document.getElementById("liveSourceCard"),
  fileSourceCard: document.getElementById("fileSourceCard"),
  activeSourceTitle: document.getElementById("activeSourceTitle"),
  viewportState: document.getElementById("viewportState"),
  modelButtons: [...document.querySelectorAll(".model-button")],
  sampleButtons: [...document.querySelectorAll(".sample-button")],
};

initialize();

function initialize() {
  elements.modeBadge.textContent = "LOCAL FORENSIC DETECTION";
  elements.statusBadge.textContent = "READY";
  elements.metricEngine.textContent = "Detection Model 1";

  bindEvents();
  refreshStagePlaceholder();
  refreshAnalyzeButton();
}

function bindEvents() {
  elements.enableCameraButton.addEventListener("click", enableWebcamFeed);
  elements.clearFileButton.addEventListener("click", clearSelectedFile);
  elements.fileInput.addEventListener("change", (event) => {
    const [file] = event.target.files || [];
    if (file) {
      handleVideoFile(file);
    }
  });
  elements.analyzeButton.addEventListener("click", handleAnalysis);
  elements.modelButtons.forEach((button) => {
    button.addEventListener("click", () => selectDetectionModel(button.dataset.model));
  });
  elements.sampleButtons.forEach((button) => {
    button.addEventListener("click", () => loadVerificationSample(button));
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    elements.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropZone.classList.add("is-dragover");
    });
  });

  ["dragleave", "dragend", "drop"].forEach((eventName) => {
    elements.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropZone.classList.remove("is-dragover");
    });
  });

  elements.dropZone.addEventListener("drop", (event) => {
    const [file] = event.dataTransfer?.files || [];
    if (file) {
      handleVideoFile(file);
    }
  });

  window.addEventListener("beforeunload", cleanupMedia);
}

function selectDetectionModel(model) {
  state.selectedModel = model === "model2" ? "model2" : "model1";
  elements.modelButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.model === state.selectedModel);
  });
  resetVerdict();
  appendLog(`${getSelectedModelLabel()} selected.`);
}

async function loadVerificationSample(button) {
  const sampleUrl = button.dataset.sample;
  if (!sampleUrl) return;

  elements.sampleButtons.forEach((item) => item.classList.remove("is-loading"));
  button.classList.add("is-loading");
  appendLog("Loading verification sample...");
  try {
    const response = await fetch(sampleUrl);
    if (!response.ok) throw new Error(`Sample unavailable (${response.status}).`);
    const blob = await response.blob();
    const filename = decodeURIComponent(sampleUrl.split("/").pop());
    handleVideoFile(new File([blob], filename, { type: "video/mp4" }));
    elements.sampleButtons.forEach((item) => item.classList.remove("is-selected"));
    button.classList.add("is-selected");
    appendLog(`${button.querySelector("span").textContent} loaded. Run analysis to verify.`);
  } catch (error) {
    appendLog(`Unable to load sample: ${error.message}`);
  } finally {
    button.classList.remove("is-loading");
  }
}

async function enableWebcamFeed() {
  if (!navigator.mediaDevices?.getUserMedia) {
    elements.cameraStatus.textContent =
      "This browser does not expose secure camera capture through getUserMedia.";
    appendLog("Webcam initialization failed: getUserMedia unavailable.");
    return;
  }

  if (state.webcamStream) {
    stopWebcamFeed();
    return;
  }

  if (state.selectedFile) {
    clearSelectedFile();
  }

  elements.cameraStatus.textContent = "Requesting camera authorization...";

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "user",
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    });

    state.webcamStream = stream;
    resetVerdict();
    elements.webcamVideo.srcObject = stream;
    elements.webcamVideo.hidden = false;
    elements.enableCameraButton.textContent = "Disable Camera";
    elements.cameraStatus.textContent = "Scanner ready. Center your face inside the targeting frame.";
    appendLog("Camera feed connected successfully.");
    refreshStagePlaceholder();
    refreshAnalyzeButton();
  } catch (error) {
    console.error(error);
    elements.cameraStatus.textContent =
      "Camera access was denied or unavailable. Use local MP4 upload to continue.";
    appendLog(`Camera access error: ${error.message}`);
  }
}

function stopWebcamFeed() {
  state.webcamStream?.getTracks().forEach((track) => track.stop());
  state.webcamStream = null;
  resetVerdict();
  elements.webcamVideo.srcObject = null;
  elements.enableCameraButton.textContent = "Enable Camera";
  elements.cameraStatus.textContent = "Camera is off. No live frames are being captured.";
  appendLog("Camera feed stopped.");
  refreshStagePlaceholder();
  refreshAnalyzeButton();
}

function handleVideoFile(file) {
  if (!isAcceptedVideoFile(file)) {
    elements.fileMeta.textContent = "Rejected. Only MP4 evidence files are accepted.";
    appendLog(`Rejected upload: ${file.name} is not an MP4 file.`);
    return;
  }


  if (state.webcamStream) {
    stopWebcamFeed();
  }

  if (state.selectedFileUrl) {
    URL.revokeObjectURL(state.selectedFileUrl);
  }

  state.selectedFile = file;
  resetVerdict();
  state.selectedFileUrl = URL.createObjectURL(file);
  elements.fileVideo.src = state.selectedFileUrl;
  elements.fileVideo.hidden = false;
  elements.fileVideo.load();
  elements.fileMeta.textContent = `${file.name} // ${(file.size / (1024 * 1024)).toFixed(2)} MB`;
  elements.metricSource.textContent = file.name;
  appendLog(`Local evidence loaded: ${file.name}`);
  refreshStagePlaceholder();
  elements.clearFileButton.hidden = false;
  refreshAnalyzeButton();

  if (AUTO_ANALYZE_ON_FILE_LOAD) {
    window.setTimeout(() => {
      handleAnalysis();
    }, 120);
  }
}

function clearSelectedFile() {
  if (state.selectedFileUrl) {
    URL.revokeObjectURL(state.selectedFileUrl);
  }
  state.selectedFile = null;
  resetVerdict();
  state.selectedFileUrl = "";
  elements.fileVideo.removeAttribute("src");
  elements.fileVideo.load();
  elements.fileMeta.textContent = "No evidence file selected";
  elements.clearFileButton.hidden = true;
  elements.metricSource.textContent = state.webcamStream ? "Live Camera" : "Awaiting input";
  appendLog("Uploaded video cleared.");
  refreshStagePlaceholder();
  refreshAnalyzeButton();
}

function refreshAnalyzeButton() {
  const hasFile = Boolean(state.selectedFile);
  const hasLive = Boolean(state.webcamStream);
  elements.analyzeButton.disabled = state.scanInProgress || (!hasFile && !hasLive);
  elements.analyzeButton.textContent = hasFile
    ? "Run MP4 Deepfake Analysis"
    : hasLive
      ? "Record & Analyze Live Clip"
      : "Select Camera or MP4 First";
}

function isAcceptedVideoFile(file) {
  const fileName = file?.name?.toLowerCase() || "";
  const mimeType = file?.type?.toLowerCase() || "";
  return mimeType === "video/mp4" || fileName.endsWith(".mp4");
}

function syncMediaVisibility() {
  const showFile = Boolean(state.selectedFileUrl);
  const showLive = !showFile && Boolean(state.webcamStream);

  elements.webcamVideo.hidden = !showLive;
  elements.fileVideo.hidden = !showFile;
}

function refreshStagePlaceholder() {
  const hasLiveMedia = Boolean(state.webcamStream) && !Boolean(state.selectedFileUrl);
  const hasFileMedia = Boolean(state.selectedFileUrl);
  elements.stagePlaceholder.hidden = hasLiveMedia || hasFileMedia;
  elements.appShell.classList.toggle("has-media", hasLiveMedia || hasFileMedia);
  elements.liveSourceCard.classList.toggle("is-active", hasLiveMedia);
  elements.fileSourceCard.classList.toggle("is-active", hasFileMedia);
  elements.activeSourceTitle.textContent = hasFileMedia
    ? "Uploaded Video Analysis"
    : hasLiveMedia
      ? "Live Camera Analysis"
      : "Select an Input Source";
  elements.viewportState.textContent = hasFileMedia
    ? "VIDEO READY"
    : hasLiveMedia
      ? "CAMERA ONLINE"
      : "STANDBY";
  syncMediaVisibility();
}

async function handleAnalysis() {
  if (state.scanInProgress) {
    return;
  }

  const hasFile = Boolean(state.selectedFile);
  const hasLive = Boolean(state.webcamStream);

  if (!hasFile && !hasLive) {
    elements.statusBadge.textContent = "INPUT REQUIRED";
    elements.verdictHeadline.textContent = "Input Required";
    elements.verdictCopy.textContent =
      "Authorize the camera feed or drop an MP4 file before starting forensic analysis.";
    appendLog("Analysis blocked: no live camera or file input available.");
    return;
  }

  state.scanInProgress = true;
  elements.analyzeButton.disabled = true;
  elements.analyzeButton.textContent = "Analysis in Progress...";
  elements.statusBadge.textContent = "ANALYZING";
  elements.viewportState.textContent = "SCANNING";
  elements.verdictHeadline.textContent = "Running Analysis";
  elements.verdictCopy.textContent = hasFile
    ? "Sampling the video timeline and evaluating synthetic facial artifacts."
    : "Recording a three-second clip, then analyzing facial artifacts across time.";
  elements.metricSource.textContent = hasFile ? state.selectedFile.name : "Live Webcam";

  setUiState("neutral");
  startScanEffects();

  try {
    const responseData = hasFile
      ? await analyzeVideoFile(state.selectedFile)
      : await analyzeLiveFrame();

    renderVerdict(responseData, hasFile ? state.selectedFile.name : "Live Webcam");
  } catch (error) {
    console.error(error);
    const isQualityIssue = error.message.includes("quality");
    setUiState(isQualityIssue ? "neutral" : "alert");
    elements.statusBadge.textContent = isQualityIssue ? "REPOSITION" : "SCAN FAILED";
    elements.viewportState.textContent = "SCAN ERROR";
    elements.verdictHeadline.textContent = isQualityIssue
      ? "Face Signal Quality Too Low"
      : "Analysis Failed";
    elements.verdictCopy.textContent = formatAnalysisError(error);
    elements.metricConfidence.textContent = "--";
    appendLog(`Analysis error: ${error.message}`);
  } finally {
    stopScanEffects();
    state.scanInProgress = false;
    refreshAnalyzeButton();
  }
}

async function analyzeLiveFrame() {
  const clip = await recordLiveClip();
  const formData = new FormData();
  formData.append("media", clip, "live-camera-scan.webm");
  formData.append("source_type", "live_video");
  formData.append("engine", state.selectedModel);
  return requestLocalAnalysis(formData);
}

async function analyzeVideoFile(file) {
  return sendMediaToLocalDetector(file, file.name);
}

async function sendMediaToLocalDetector(mediaBlob, filename) {
  const formData = new FormData();
  formData.append("media", mediaBlob, filename);
  formData.append("engine", state.selectedModel);
  return requestLocalAnalysis(formData);
}

function recordLiveClip() {
  return new Promise((resolve, reject) => {
    if (!window.MediaRecorder || !state.webcamStream) {
      reject(new Error("This browser cannot record a live analysis clip."));
      return;
    }

    const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp8")
      ? "video/webm;codecs=vp8"
      : "video/webm";
    const chunks = [];
    const recorder = new MediaRecorder(state.webcamStream, { mimeType });
    recorder.addEventListener("dataavailable", (event) => {
      if (event.data.size) chunks.push(event.data);
    });
    recorder.addEventListener("error", () => reject(new Error("Live clip recording failed.")));
    recorder.addEventListener("stop", () => {
      if (!chunks.length) {
        reject(new Error("Live clip recording produced no video data."));
        return;
      }
      resolve(new Blob(chunks, { type: mimeType }));
    });
    recorder.start(250);
    window.setTimeout(() => recorder.stop(), 3000);
  });
}

async function requestLocalAnalysis(formData) {
  const response = await fetch("/api/analyze", { method: "POST", body: formData });
  const responseText = await response.text();
  let payload = null;
  try {
    payload = JSON.parse(responseText);
  } catch (_error) {
    payload = null;
  }
  if (!response.ok || payload?.status !== "success") {
    throw new Error(payload?.error?.message || `Local detector failed (${response.status}).`);
  }
  return payload;
}

function captureWebcamFrameBlob() {
  return new Promise((resolve, reject) => {
    const video = elements.webcamVideo;

    if (!video.videoWidth || !video.videoHeight) {
      reject(new Error("Webcam feed is active but no video frame is ready yet."));
      return;
    }

    // Meso4 expects an aligned face crop, not a full room/background frame.
    const sourceSide = Math.round(Math.min(video.videoWidth, video.videoHeight) * 0.68);
    const sourceX = Math.round((video.videoWidth - sourceSide) / 2);
    const sourceY = Math.round((video.videoHeight - sourceSide) / 2);
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 512;
    const context = canvas.getContext("2d");

    if (!context) {
      reject(new Error("Unable to initialize capture canvas."));
      return;
    }

    context.drawImage(
      video,
      sourceX,
      sourceY,
      sourceSide,
      sourceSide,
      0,
      0,
      canvas.width,
      canvas.height
    );
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error("Webcam frame capture produced an empty blob."));
          return;
        }
        resolve(blob);
      },
      "image/jpeg",
      0.92
    );
  });
}

function startScanEffects() {
  elements.appShell.classList.add("is-scanning");
  elements.terminalOverlay.classList.add("is-visible");
  elements.terminalOverlay.textContent = "";
  cycleTerminalLines();
}

function stopScanEffects() {
  elements.appShell.classList.remove("is-scanning");
  elements.terminalOverlay.classList.remove("is-visible");
  window.clearTimeout(state.terminalTimeoutId);
  window.clearInterval(state.terminalIntervalId);
}

function cycleTerminalLines() {
  let lineIndex = 0;
  let charIndex = 0;
  let renderedLines = [];

  window.clearTimeout(state.terminalTimeoutId);
  window.clearInterval(state.terminalIntervalId);

  const typeNextCharacter = () => {
    if (!state.scanInProgress) {
      return;
    }

    const currentLine = TERMINAL_LINES[lineIndex];
    renderedLines[lineIndex] = currentLine.slice(0, charIndex + 1);
    elements.terminalOverlay.innerHTML = renderedLines.join("<br>");
    charIndex += 1;

    if (charIndex < currentLine.length) {
      state.terminalTimeoutId = window.setTimeout(typeNextCharacter, 28);
      return;
    }

    lineIndex += 1;
    charIndex = 0;

    if (lineIndex >= TERMINAL_LINES.length) {
      lineIndex = 0;
      renderedLines = [];
      state.terminalTimeoutId = window.setTimeout(typeNextCharacter, 900);
      return;
    }

    state.terminalTimeoutId = window.setTimeout(typeNextCharacter, 240);
  };

  typeNextCharacter();
  state.terminalIntervalId = window.setInterval(() => {
    if (!state.scanInProgress) {
      window.clearInterval(state.terminalIntervalId);
    }
  }, 1000);
}

function renderVerdict(responseData, sourceLabel) {
  const isLiveVideo = responseData?.meta?.source_type === "live_video";
  const rawProbability = extractAiProbability(responseData);
  const probability = isLiveVideo && state.selectedModel === "model1"
    ? calibrateCameraDomainScore(rawProbability)
    : rawProbability;
  const scorePercent = Math.round(probability * 100);
  const threatThreshold = 0.5;
  const threatDetected = probability >= threatThreshold;

  if (threatDetected) {
    setUiState("alert");
    elements.viewportState.textContent = "DEEPFAKE ALERT";
    elements.statusBadge.textContent = "HIGH RISK";
    elements.verdictHeadline.textContent = `DEEPFAKE SUSPECTED // ${scorePercent}%`;
    elements.verdictCopy.textContent =
      "Local detector flagged deepfake-consistent artifacts across the analyzed media sample.";
    appendLog(`Alert verdict issued for ${sourceLabel} at ${scorePercent}% synthetic likelihood.`);
  } else {
    setUiState("secure");
    elements.viewportState.textContent = "AUTHENTIC";
    elements.statusBadge.textContent = "AUTHENTIC";
    elements.verdictHeadline.textContent = `AUTHENTIC SIGNAL // ${100 - scorePercent}%`;
    elements.verdictCopy.textContent =
      "The analyzed media remained below the detector threshold for synthetic manipulation.";
    appendLog(`Authentic verdict issued for ${sourceLabel} at ${scorePercent}% synthetic likelihood.`);
  }

  elements.metricSource.textContent = sourceLabel;
  elements.metricScoreLabel.textContent = "Synthetic Score";
  elements.metricConfidence.textContent = `${scorePercent}%`;
  elements.metricEngine.textContent = getSelectedModelLabel();
}

function calibrateCameraDomainScore(rawProbability) {
  const epsilon = 0.0001;
  const clipped = Math.min(Math.max(rawProbability, epsilon), 1 - epsilon);
  const correctedLogit = Math.log(clipped / (1 - clipped)) - 1.2;
  return 1 / (1 + Math.exp(-correctedLogit));
}

function extractAiProbability(responseData) {
  const candidates = [
    responseData?.type?.ai_generated,
    responseData?.type?.deepfake,
    responseData?.summary?.ai_generated,
    responseData?.summary?.deepfake,
    responseData?.result?.type?.ai_generated,
    responseData?.result?.summary?.ai_generated,
  ];

  for (const value of candidates) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return Math.min(Math.max(value, 0), 1);
    }
  }

  throw new Error("Unable to extract AI-generated probability from detector response.");
}

function setUiState(mode) {
  elements.appShell.classList.remove("app-state-neutral", "app-state-alert", "app-state-secure");
  elements.appShell.classList.add(`app-state-${mode}`);
}

function resetVerdict() {
  setUiState("neutral");
  elements.statusBadge.textContent = "READY";
  elements.verdictHeadline.textContent = "Awaiting Scan";
  elements.verdictCopy.textContent = "Execute the analysis to generate a forensic verdict.";
  elements.metricConfidence.textContent = "--";
  elements.metricEngine.textContent = getSelectedModelLabel();
}

function getSelectedModelLabel() {
  return state.selectedModel === "model2" ? "Detection Model 2" : "Detection Model 1";
}

function appendLog(message) {
  elements.activityStatus.textContent = message;
}

function cleanupMedia() {
  state.webcamStream?.getTracks().forEach((track) => track.stop());
  if (state.selectedFileUrl) {
    URL.revokeObjectURL(state.selectedFileUrl);
  }
}

function formatAnalysisError(error) {
  const message = error?.message || "Unknown detector error.";
  if (message.includes("decode")) {
    return "The uploaded video could not be decoded for local analysis.";
  }
  if (message.includes("quality") || message.includes("Calibrate")) {
    return message;
  }
  if (message.includes("Local detector")) {
    return message;
  }
  return "The local detector could not complete the analysis request.";
}
