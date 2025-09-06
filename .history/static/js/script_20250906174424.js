// DOM Elements
const uploadForm = document.getElementById("uploadForm");
const submitBtn = document.getElementById("submitBtn");
const progressContainer = document.getElementById("progressContainer");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const resultContainer = document.getElementById("resultContainer");
const downloadBtn = document.getElementById("downloadBtn");
const errorContainer = document.getElementById("errorContainer");
const errorText = document.getElementById("errorText");

// File input elements
const videoInput = document.getElementById("video");
const video2Input = document.getElementById("video2");

// File info elements
const videoInfo = document.getElementById("videoInfo");
const video2Info = document.getElementById("video2Info");

// Initialize file input listeners
document.addEventListener("DOMContentLoaded", function () {
  initializeFileInputs();
  initializeNavigation();
  initializeSmoothScrolling();
  testAPIConnection();
});

// Test API connection
async function testAPIConnection() {
  try {
    const API_BASE = window.API_BASE || "http://localhost:5000";
    console.log("Testing API connection to:", API_BASE);

    const response = await fetch(`${API_BASE}/api/test`);

    if (response.ok) {
      const result = await response.json();
      console.log("✅ API connection successful:", result);
    } else {
      console.error(
        "❌ API connection failed:",
        response.status,
        response.statusText
      );
      showError(
        `خطأ في الاتصال بالخادم: ${response.status} ${response.statusText}`
      );
    }
  } catch (error) {
    console.error("❌ API connection error:", error);
    showError(`خطأ في الاتصال بالخادم: ${error.message}`);
  }
}

// Initialize file input listeners
function initializeFileInputs() {
  videoInput.addEventListener("change", function (e) {
    handleFileSelect(e.target, videoInfo, "video");
  });

  video2Input.addEventListener("change", function (e) {
    handleFileSelect(e.target, video2Info, "video");
  });
}

// Handle file selection
function handleFileSelect(input, infoElement, fileType) {
  const file = input.files[0];
  if (file) {
    const fileSize = formatFileSize(file.size);
    const fileName = file.name;

    infoElement.innerHTML = `
            <div class="file-selected">
                <i class="fas fa-check-circle"></i>
                <span>${fileName}</span>
                <small>(${fileSize})</small>
            </div>
        `;

    // Validate file size (500MB max)
    if (file.size > 500 * 1024 * 1024) {
      showError(`حجم الملف كبير جداً. الحد الأقصى هو 500 ميجابايت`);
      input.value = "";
      infoElement.innerHTML = "";
      return;
    }

    // Validate file type
    if (!isValidFileType(file, fileType)) {
      showError(
        `نوع الملف غير مدعوم. يرجى اختيار ملف ${
          fileType === "video" ? "فيديو" : "صورة"
        } صحيح`
      );
      input.value = "";
      infoElement.innerHTML = "";
      return;
    }
  } else {
    infoElement.innerHTML = "";
  }
}

// Format file size
function formatFileSize(bytes) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

// Validate file type
function isValidFileType(file, fileType) {
  if (fileType === "video") {
    const videoTypes = [
      "video/mp4",
      "video/avi",
      "video/mov",
      "video/mkv",
      "video/wmv",
      "video/flv",
    ];
    return videoTypes.includes(file.type);
  } else if (fileType === "image") {
    const imageTypes = ["image/jpeg", "image/png", "image/gif", "image/bmp"];
    return imageTypes.includes(file.type);
  }
  return false;
}

// Initialize navigation
function initializeNavigation() {
  const navLinks = document.querySelectorAll(".nav-link");
  const sections = document.querySelectorAll("section[id]");

  window.addEventListener("scroll", () => {
    let current = "";
    sections.forEach((section) => {
      const sectionTop = section.offsetTop;
      const sectionHeight = section.clientHeight;
      if (scrollY >= sectionTop - 200) {
        current = section.getAttribute("id");
      }
    });

    navLinks.forEach((link) => {
      link.classList.remove("active");
      if (link.getAttribute("href") === `#${current}`) {
        link.classList.add("active");
      }
    });
  });
}

// Initialize smooth scrolling
function initializeSmoothScrolling() {
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute("href"));
      if (target) {
        target.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }
    });
  });
}

// Scroll to upload section
function scrollToUpload() {
  const uploadSection = document.querySelector(".upload-section");
  uploadSection.scrollIntoView({ behavior: "smooth" });
}

// Scroll to features section
function scrollToFeatures() {
  const featuresSection = document.querySelector("#features");
  featuresSection.scrollIntoView({ behavior: "smooth" });
}

// Handle form submission
uploadForm.addEventListener("submit", async function (e) {
  e.preventDefault();

  // Validate form
  if (!validateForm()) {
    return;
  }

  // Show progress
  showProgress();

  try {
    const formData = new FormData(uploadForm);

    // سيتم تتبع التقدم الحقيقي من Celery

    const API_BASE = window.API_BASE || "http://localhost:5000";
    console.log("Uploading to:", `${API_BASE}/upload`);

    const response = await fetch(`${API_BASE}/upload`, {
      method: "POST",
      body: formData,
      headers: {
        // لا نضع Content-Type لأن FormData يضعه تلقائياً
      },
    });

    console.log("Response status:", response.status);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    console.log("Response data:", result);

    if (result.success && result.job_id) {
      // بدء تتبع حالة المهمة
      trackJobProgress(result.job_id, result.output_filename);
    } else {
      showError(result.error || "حدث خطأ أثناء معالجة الفيديو", result);
    }
  } catch (error) {
    console.error("🚨 UPLOAD ERROR:", error);
    
    // جمع معلومات تفصيلية عن الخطأ
    const errorDetails = {
      error_message: error.message,
      error_stack: error.stack,
      api_base: window.API_BASE,
      current_url: window.location.href,
      timestamp: new Date().toISOString(),
      browser_info: {
        userAgent: navigator.userAgent,
        language: navigator.language,
        platform: navigator.platform
      }
    };
    
    showError("حدث خطأ في الاتصال بالخادم - تحقق من Console للتفاصيل", errorDetails);
  }
});

// Validate form
function validateForm() {
  const video = videoInput.files[0];

  if (!video) {
    showError("يرجى اختيار ملف الفيديو");
    return false;
  }

  return true;
}

// Show progress
function showProgress() {
  hideAll();
  progressContainer.style.display = "block";
  submitBtn.disabled = true;
  submitBtn.innerHTML =
    '<i class="fas fa-spinner fa-spin"></i> جاري المعالجة...';
}

// تم حذف simulateProgress - نستخدم التقدم الحقيقي من Celery الآن

// Update progress bar
function updateProgress(percentage, status = null) {
  progressFill.style.width = `${percentage}%`;
  if (status) {
    progressText.textContent = `${status} ${Math.round(percentage)}%`;
  } else {
    progressText.textContent = `جاري المعالجة... ${Math.round(percentage)}%`;
  }
}

// Track job progress
async function trackJobProgress(jobId, outputFilename) {
  const pollInterval = 2000; // 2 seconds
  let attempts = 0;
  const maxAttempts = 300; // 10 minutes maximum

  const poll = async () => {
    try {
      attempts++;

      const response = await fetch(`${API_BASE}/status/${jobId}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const status = await response.json();
      console.log("Status response:", status);

      console.log("Job status:", status);

      if (status.state === "PENDING") {
        updateProgress(5, "في الانتظار...");
      } else if (status.state === "PROCESSING") {
        updateProgress(status.progress || 0, status.status);
      } else if (status.state === "SUCCESS") {
        updateProgress(100, "تمت المعالجة بنجاح!");
        showResult({
          success: true,
          message: "تمت معالجة الفيديو بنجاح",
          download_url: `/download/${outputFilename}`,
          filename: outputFilename,
        });
        return; // Stop polling
      } else {
        // FAILURE or other error states
        showError(status.status || status.error || "حدث خطأ في المعالجة");
        return; // Stop polling
      }

      // Continue polling if not finished and within limits
      if (attempts < maxAttempts) {
        setTimeout(poll, pollInterval);
      } else {
        showError("انتهت مهلة المعالجة. يرجى المحاولة مرة أخرى.");
      }
    } catch (error) {
      console.error("Error polling status:", error);
      showError("خطأ في تتبع حالة المعالجة");
    }
  };

  // Start polling
  poll();
}

// Show result
function showResult(result) {
  hideAll();
  resultContainer.style.display = "block";

  // تعيين رابط التحميل
  if (result.download_url) {
    downloadBtn.href = result.download_url;
    downloadBtn.download = result.filename;
    console.log("Download URL set to:", result.download_url);
    console.log("Filename set to:", result.filename);
  } else {
    console.error("No download URL provided in result:", result);
  }

  // Reset form
  uploadForm.reset();
  videoInfo.innerHTML = "";
  video2Info.innerHTML = "";

  // Reset button
  submitBtn.disabled = false;
  submitBtn.innerHTML = '<i class="fas fa-cog"></i> معالجة الفيديو';
}

// Show error with detailed logging
function showError(message, errorData = null) {
  hideAll();
  errorContainer.style.display = "block";
  
  // عرض الرسالة الأساسية
  errorText.innerHTML = `
    <div class="error-main">${message}</div>
    ${errorData ? `<div class="error-details">
      <details>
        <summary>تفاصيل تقنية (للمطورين)</summary>
        <pre>${JSON.stringify(errorData, null, 2)}</pre>
      </details>
    </div>` : ''}
  `;

  // طباعة تفصيلية في Console
  console.error("🚨 ERROR DETAILS:", {
    message: message,
    timestamp: new Date().toISOString(),
    url: window.location.href,
    userAgent: navigator.userAgent,
    errorData: errorData
  });

  // Reset button
  submitBtn.disabled = false;
  submitBtn.innerHTML = '<i class="fas fa-cog"></i> معالجة الفيديو';
}

// Hide error
function hideError() {
  errorContainer.style.display = "none";
}

// Hide all containers
function hideAll() {
  progressContainer.style.display = "none";
  resultContainer.style.display = "none";
  errorContainer.style.display = "none";
}

// Add CSS for file selection
const style = document.createElement("style");
style.textContent = `
    .file-selected {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem;
        background: #e8f5e8;
        border: 1px solid #c3e6cb;
        border-radius: 8px;
        color: #155724;
    }
    
    .file-selected i {
        color: #28a745;
    }
    
    .file-selected small {
        opacity: 0.7;
    }
    
    .btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
        transform: none !important;
    }
    
    .fa-spinner {
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);

// Add loading animation for buttons
document.addEventListener("DOMContentLoaded", function () {
  // Add ripple effect to buttons
  document.querySelectorAll(".btn").forEach((button) => {
    button.addEventListener("click", function (e) {
      const ripple = document.createElement("span");
      const rect = this.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      const x = e.clientX - rect.left - size / 2;
      const y = e.clientY - rect.top - size / 2;

      ripple.style.width = ripple.style.height = size + "px";
      ripple.style.left = x + "px";
      ripple.style.top = y + "px";
      ripple.classList.add("ripple");

      this.appendChild(ripple);

      setTimeout(() => {
        ripple.remove();
      }, 600);
    });
  });
});

// Add ripple effect CSS
const rippleStyle = document.createElement("style");
rippleStyle.textContent = `
    .btn {
        position: relative;
        overflow: hidden;
    }
    
    .ripple {
        position: absolute;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.3);
        transform: scale(0);
        animation: ripple-animation 0.6s linear;
        pointer-events: none;
    }
    
    @keyframes ripple-animation {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
`;
document.head.appendChild(rippleStyle);
