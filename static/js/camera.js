/*
==================================================
SMART MESS MANAGEMENT SYSTEM - CAMERA & FACE SCAN
==================================================
Description: HTML5 Webcam video streaming, snapshot capture,
base64 encoding, live facial attendance scanning, and real-time alerts.
==================================================
*/

// ==========================================
// WEBCAM STREAM MANAGER - START
// ==========================================
class MessCamera {
  constructor(videoElementId, canvasElementId) {
    this.video = document.getElementById(videoElementId);
    this.canvas = document.getElementById(canvasElementId);
    this.stream = null;
    this.isStreaming = false;
  }

  async start(facingMode = "user") {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Webcam access is not supported by your browser or secure context.");
      }

      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: facingMode,
          width: { ideal: 640 },
          height: { ideal: 480 }
        },
        audio: false
      });

      if (this.video) {
        this.video.srcObject = this.stream;
        await this.video.play();
        this.isStreaming = true;
      }
      return true;
    } catch (err) {
      console.error("[MessCamera] Camera start error:", err);
      showToast(`Camera Error: ${err.message || "Failed to access webcam"}`, "danger");
      return false;
    }
  }

  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    if (this.video) {
      this.video.srcObject = null;
    }
    this.isStreaming = false;
  }

  captureBase64() {
    if (!this.isStreaming || !this.video || !this.canvas) {
      return null;
    }

    const context = this.canvas.getContext("2d");
    this.canvas.width = this.video.videoWidth || 640;
    this.canvas.height = this.video.videoHeight || 480;

    // Draw current video frame to canvas
    context.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

    // Export as JPEG base64 data URL
    return this.canvas.toDataURL("image/jpeg", 0.9);
  }
}
// ==========================================
// WEBCAM STREAM MANAGER - END
// ==========================================


// ==========================================
// STUDENT FACE REGISTRATION WORKFLOW - START
// ==========================================
let regCamera = null;

function initRegistrationCamera(videoId = "regVideo", canvasId = "regCanvas") {
  if (!regCamera) {
    regCamera = new MessCamera(videoId, canvasId);
  }
  return regCamera;
}

async function startRegCamera() {
  const cam = initRegistrationCamera();
  const started = await cam.start();
  if (started) {
    document.getElementById("btnStartCam")?.classList.add("d-none");
    document.getElementById("btnCaptureFace")?.classList.remove("d-none");
    document.getElementById("btnRetakeFace")?.classList.add("d-none");
    document.getElementById("regPreview")?.classList.add("d-none");
    document.getElementById("regVideo")?.classList.remove("d-none");
  }
}

function captureRegFace() {
  if (!regCamera) return;
  const b64 = regCamera.captureBase64();
  if (!b64) {
    showToast("Unable to capture frame. Ensure camera is running.", "warning");
    return;
  }

  // Update hidden form field and image preview
  const hiddenField = document.getElementById("face_image_b64");
  const previewImg = document.getElementById("regPreview");
  const videoElem = document.getElementById("regVideo");

  if (hiddenField) hiddenField.value = b64;
  if (previewImg) {
    previewImg.src = b64;
    previewImg.classList.remove("d-none");
  }
  if (videoElem) videoElem.classList.add("d-none");

  document.getElementById("btnCaptureFace")?.classList.add("d-none");
  document.getElementById("btnRetakeFace")?.classList.remove("d-none");
  showToast("Face frame captured. Review preview or save student.", "info");
}

function retakeRegFace() {
  const hiddenField = document.getElementById("face_image_b64");
  const previewImg = document.getElementById("regPreview");
  const videoElem = document.getElementById("regVideo");

  if (hiddenField) hiddenField.value = "";
  if (previewImg) previewImg.classList.add("d-none");
  if (videoElem) videoElem.classList.remove("d-none");

  document.getElementById("btnCaptureFace")?.classList.remove("d-none");
  document.getElementById("btnRetakeFace")?.classList.add("d-none");
}
// ==========================================
// STUDENT FACE REGISTRATION WORKFLOW - END
// ==========================================


// ==========================================
// LIVE ATTENDANCE SCANNER WORKFLOW - START
// ==========================================
let attendanceCamera = null;
let autoScanInterval = null;
let isScanningActive = false;

function initAttendanceScanner() {
  if (!attendanceCamera) {
    attendanceCamera = new MessCamera("attendVideo", "attendCanvas");
  }

  const startBtn = document.getElementById("btnStartAttendance");
  const stopBtn = document.getElementById("btnStopAttendance");
  const scanBtn = document.getElementById("btnScanOnce");
  const autoBtn = document.getElementById("btnAutoScan");

  if (startBtn) {
    startBtn.addEventListener("click", async () => {
      const ok = await attendanceCamera.start();
      if (ok) {
        startBtn.style.display = "none";
        if (stopBtn) stopBtn.style.display = "inline-flex";
        if (scanBtn) scanBtn.style.display = "inline-flex";
        if (autoBtn) autoBtn.style.display = "inline-flex";
        updateScannerStatus("Camera active. Position student's face inside the frame.", "ready");
      }
    });
  }

  if (stopBtn) {
    stopBtn.addEventListener("click", () => {
      stopAutoScan();
      attendanceCamera.stop();
      startBtn.style.display = "inline-flex";
      stopBtn.style.display = "none";
      scanBtn.style.display = "none";
      autoBtn.style.display = "none";
      updateScannerStatus("Camera stopped.", "ready");
    });
  }

  if (scanBtn) {
    scanBtn.addEventListener("click", () => {
      performAttendanceScan();
    });
  }

  if (autoBtn) {
    autoBtn.addEventListener("click", () => {
      if (autoScanInterval) {
        stopAutoScan();
      } else {
        startAutoScan();
      }
    });
  }
}

function startAutoScan() {
  const autoBtn = document.getElementById("btnAutoScan");
  if (autoBtn) {
    autoBtn.innerHTML = "⏹️ Stop Auto-Scan";
    autoBtn.classList.remove("btn-secondary");
    autoBtn.classList.add("btn-danger");
  }
  showToast("Auto-Scan Mode enabled (Scanning every 2s)", "info");
  
  // Trigger initial scan immediately then interval
  performAttendanceScan();
  autoScanInterval = setInterval(() => {
    if (attendanceCamera && attendanceCamera.isStreaming && !isScanningActive) {
      performAttendanceScan();
    }
  }, 2000);
}

function stopAutoScan() {
  if (autoScanInterval) {
    clearInterval(autoScanInterval);
    autoScanInterval = null;
  }
  const autoBtn = document.getElementById("btnAutoScan");
  if (autoBtn) {
    autoBtn.innerHTML = "⚡ Auto-Scan Mode";
    autoBtn.classList.remove("btn-danger");
    autoBtn.classList.add("btn-secondary");
  }
}

async function performAttendanceScan() {
  if (!attendanceCamera || !attendanceCamera.isStreaming || isScanningActive) return;

  const imageB64 = attendanceCamera.captureBase64();
  if (!imageB64) return;

  isScanningActive = true;
  const wrapper = document.querySelector(".video-wrapper");
  if (wrapper) wrapper.classList.add("scanning");

  const selectedMeal = document.querySelector("input[name='meal_type']:checked")?.value || "Lunch";
  updateScannerStatus("Processing facial contours...", "ready");

  try {
    const response = await fetch("/admin/attendance/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_b64: imageB64,
        meal: selectedMeal
      })
    });

    const data = await response.json();

    if (data.status === "marked") {
      // SUCCESSFUL ATTENDANCE
      AudioFeedback.playSuccess();
      updateScannerStatus(`✅ ${data.message}`, "success");
      renderScanResultCard(data, "success");
      prependRecentScanLog(data);
      showToast(`Attendance marked for ${data.student_name} (${data.student_id})`, "success");
    } else if (data.status === "already_marked") {
      // DUPLICATE ATTENDANCE
      AudioFeedback.playWarning();
      updateScannerStatus(`⚠️ ${data.message}`, "warning");
      renderScanResultCard(data, "duplicate");
      showToast(data.message, "warning");
    } else if (data.status === "no_face") {
      updateScannerStatus("No face detected in frame. Please center your face.", "ready");
    } else if (data.status === "multiple_faces") {
      AudioFeedback.playWarning();
      updateScannerStatus("⚠️ Please ensure only one student is visible.", "warning");
      showToast("Multiple faces detected", "warning");
    } else {
      // UNKNOWN STUDENT
      AudioFeedback.playWarning();
      updateScannerStatus("❌ Student not recognized in database.", "danger");
      showToast("Student not recognized.", "danger");
    }

  } catch (err) {
    console.error("[AttendanceScan] Scan request failed:", err);
    updateScannerStatus("Server communication error.", "danger");
  } finally {
    isScanningActive = false;
    if (wrapper) wrapper.classList.remove("scanning");
  }
}

function updateScannerStatus(text, level) {
  const banner = document.getElementById("scannerStatusBanner");
  if (!banner) return;
  banner.className = `camera-status-banner status-${level}`;
  banner.innerText = text;
}

function renderScanResultCard(data, mode) {
  const container = document.getElementById("liveScanResult");
  if (!container) return;

  const isSuccess = mode === "success";
  const borderClass = isSuccess ? "success-border" : "duplicate-border";
  const badgeColor = isSuccess ? "badge-paid" : "badge-pending";
  const titleText = isSuccess ? "Attendance Marked" : "Duplicate Attendance Notice";

  container.innerHTML = `
    <div class="scan-result-card ${borderClass}">
      <div style="font-size: 40px;">${isSuccess ? "🎉" : "⚠️"}</div>
      <div style="flex: 1;">
        <div style="display: flex; align-items: center; justify-content: space-between;">
          <h4 style="font-size: 16px; font-weight: 800; color: #0f172a;">${data.student_name || "Student"}</h4>
          <span class="badge ${badgeColor}">${titleText}</span>
        </div>
        <div style="font-size: 13px; color: #475569; margin-top: 4px;">
          <strong>ID:</strong> ${data.student_id} | <strong>Meal:</strong> ${data.meal} | <strong>Time:</strong> ${data.time || data.marked_at || 'Just now'}
        </div>
        <div style="font-size: 12px; color: #64748b; margin-top: 4px;">
          ${data.message}
        </div>
      </div>
    </div>
  `;
}

function prependRecentScanLog(data) {
  const tbody = document.getElementById("todayScansTableBody");
  if (!tbody) return;

  const emptyRow = tbody.querySelector(".empty-scans-row");
  if (emptyRow) emptyRow.remove();

  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><strong>${data.student_id}</strong></td>
    <td>${data.student_name}</td>
    <td>${data.roll_number || 'N/A'}</td>
    <td><span class="badge badge-${data.meal.toLowerCase()}">${data.meal}</span></td>
    <td>${data.time}</td>
    <td><span class="badge badge-paid">Present</span></td>
  `;
  tbody.insertBefore(tr, tbody.firstChild);
}
// ==========================================
// LIVE ATTENDANCE SCANNER WORKFLOW - END
// ==========================================
