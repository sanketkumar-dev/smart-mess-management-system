/*
==================================================
SMART MESS MANAGEMENT SYSTEM - CORE JAVASCRIPT
==================================================
Description: Global utility functions, toast notifications,
modal controller, client-side table searching, and filters.
==================================================
*/

// ==========================================
// TOAST NOTIFICATION ENGINE - START
// ==========================================
function showToast(message, type = "info", duration = 4000) {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  
  // Choose icon based on type
  let icon = "ℹ️";
  if (type === "success") icon = "✅";
  if (type === "danger") icon = "❌";
  if (type === "warning") icon = "⚠️";

  toast.innerHTML = `
    <span style="font-size: 16px;">${icon}</span>
    <span style="flex: 1;">${message}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }, duration);
}
// ==========================================
// TOAST NOTIFICATION ENGINE - END
// ==========================================


// ==========================================
// MODAL CONTROLLER - START
// ==========================================
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add("active");
    document.body.style.overflow = "hidden";
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("active");
    document.body.style.overflow = "auto";
  }
}

// Close modal when clicking outside modal-container
document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("appSidebar");
  const menuToggle = document.getElementById("mobileMenuToggle");
  const sidebarBackdrop = document.getElementById("sidebarBackdrop");

  const closeSidebar = () => {
    if (!sidebar || !menuToggle) return;
    sidebar.classList.remove("open");
    sidebarBackdrop?.classList.remove("visible");
    menuToggle.setAttribute("aria-expanded", "false");
  };

  menuToggle?.addEventListener("click", () => {
    const isOpen = sidebar.classList.toggle("open");
    sidebarBackdrop?.classList.toggle("visible", isOpen);
    menuToggle.setAttribute("aria-expanded", String(isOpen));
  });
  sidebarBackdrop?.addEventListener("click", closeSidebar);
  sidebar?.querySelectorAll(".menu-link").forEach(link => link.addEventListener("click", closeSidebar));

  document.querySelectorAll(".modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        overlay.classList.remove("active");
        document.body.style.overflow = "auto";
      }
    });
  });
});
// ==========================================
// MODAL CONTROLLER - END
// ==========================================


// ==========================================
// TABLE SEARCH & FILTER ENGINE - START
// ==========================================
function filterTable(inputId, tableId) {
  const input = document.getElementById(inputId);
  const filter = input.value.toLowerCase();
  const table = document.getElementById(tableId);
  if (!table) return;

  const tr = table.getElementsByTagName("tr");
  for (let i = 1; i < tr.length; i++) {
    let match = false;
    const tds = tr[i].getElementsByTagName("td");
    for (let j = 0; j < tds.length; j++) {
      if (tds[j]) {
        const txtValue = tds[j].textContent || tds[j].innerText;
        if (txtValue.toLowerCase().indexOf(filter) > -1) {
          match = true;
          break;
        }
      }
    }
    tr[i].style.display = match ? "" : "none";
  }
}
// ==========================================
// TABLE SEARCH & FILTER ENGINE - END
// ==========================================


// ==========================================
// AUDIO FEEDBACK SYNTHESIZER - START
// ==========================================
// Web Audio API synthesizer for instant audio cues on face scan
const AudioFeedback = {
  ctx: null,
  init() {
    if (!this.ctx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        this.ctx = new AudioContext();
      }
    }
  },
  playSuccess() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      
      osc.type = "sine";
      osc.frequency.setValueAtTime(587.33, this.ctx.currentTime); // D5
      osc.frequency.setValueAtTime(880, this.ctx.currentTime + 0.1); // A5
      gain.gain.setValueAtTime(0.15, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.3);
      
      osc.start(this.ctx.currentTime);
      osc.stop(this.ctx.currentTime + 0.3);
    } catch (e) {}
  },
  playWarning() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      
      osc.type = "triangle";
      osc.frequency.setValueAtTime(320, this.ctx.currentTime);
      osc.frequency.setValueAtTime(220, this.ctx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.2, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.35);
      
      osc.start(this.ctx.currentTime);
      osc.stop(this.ctx.currentTime + 0.35);
    } catch (e) {}
  }
};
// ==========================================
// AUDIO FEEDBACK SYNTHESIZER - END
// ==========================================
