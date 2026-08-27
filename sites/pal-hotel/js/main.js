(function () {
  "use strict";

  var CFG = window.PAL_CONFIG || {};
  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- mobile nav ---- */
  var toggle = document.querySelector(".nav-toggle");
  var links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", function () {
      var open = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    links.addEventListener("click", function (e) {
      if (e.target.matches("a")) links.classList.remove("open");
    });
  }

  /* ---- sequenced scroll reveals (reading order, staggered) ---- */
  var revealEls = Array.prototype.slice.call(document.querySelectorAll("[data-reveal]"));
  if (!reducedMotion && "IntersectionObserver" in window) {
    var groups = new Map();
    revealEls.forEach(function (el) {
      var parent = el.parentElement;
      var idx = groups.get(parent) || 0;
      groups.set(parent, idx + 1);
      el.style.setProperty("--rd", Math.min(idx * 80, 400) + "ms");
    });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("in"); });
  }

  /* ---- micro-interactions: glow-follow CTAs + tilt cards (fine pointers only) ---- */
  var finePointer = window.matchMedia("(pointer: fine)").matches;
  if (finePointer && !reducedMotion) {
    document.querySelectorAll(".btn-primary").forEach(function (btn) {
      btn.addEventListener("pointermove", function (e) {
        var r = btn.getBoundingClientRect();
        btn.style.setProperty("--mx", ((e.clientX - r.left) / r.width) * 100 + "%");
        btn.style.setProperty("--my", ((e.clientY - r.top) / r.height) * 100 + "%");
      });
    });
    document.querySelectorAll(".room-card").forEach(function (card) {
      card.addEventListener("pointermove", function (e) {
        var r = card.getBoundingClientRect();
        var x = (e.clientX - r.left) / r.width - 0.5;
        var y = (e.clientY - r.top) / r.height - 0.5;
        card.style.transform = "perspective(700px) rotateX(" + (-y * 5) + "deg) rotateY(" + (x * 5) + "deg)";
      });
      card.addEventListener("pointerleave", function () {
        card.style.transform = "";
      });
    });
  }

  /* ---- contact actions from config (hidden until configured — no dead buttons) ---- */
  document.querySelectorAll("[data-contact]").forEach(function (el) {
    var kind = el.getAttribute("data-contact");
    var live = false;
    if (kind === "whatsapp" && CFG.whatsapp) {
      el.href = "https://wa.me/" + CFG.whatsapp.replace(/\D/g, "");
      live = true;
    } else if (kind === "tel" && CFG.phoneDisplay) {
      el.href = "tel:" + CFG.phoneDisplay.replace(/[^\d+]/g, "");
      el.textContent = CFG.phoneDisplay;
      live = true;
    } else if (kind === "email" && CFG.email) {
      el.href = "mailto:" + CFG.email + "?subject=Room%20enquiry%20%E2%80%94%20Pal%20Hotel";
      el.textContent = CFG.email;
      live = true;
    } else if (kind === "maps") {
      el.href = "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(CFG.mapsQuery || "Pal Hotel");
      live = true;
    }
    if (!live) {
      // TODO-OWNER: add the matching value in js/config.js to activate this action.
      // Hidden rather than dead — nothing on the page pretends to work.
      el.hidden = true;
    }
  });

  /* ============================================================
     SIGNATURE: room-selector booking inquiry composer
     ============================================================ */
  var form = document.getElementById("selector");
  if (!form) return;

  var state = { room: "", checkin: null, checkout: null, guests: 1 };
  var previewEl = form.querySelector(".preview-msg");
  var errorEl = form.querySelector(".selector-error");
  var sendWa = form.querySelector("[data-send='wa']");
  var sendMail = form.querySelector("[data-send='mail']");
  var copyBtn = form.querySelector(".copy-btn");
  var outInput = form.querySelector("#checkout");

  function fmt(iso) {
    if (!iso) return "—";
    var d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  }

  function nights() {
    if (!state.checkin || !state.checkout) return null;
    return Math.round((new Date(state.checkout) - new Date(state.checkin)) / 86400000);
  }

  function compose() {
    if (!state.room) {
      return "Hi! I'd like to enquire about a stay at Pal Hotel.";
    }
    var dates = state.checkin
      ? fmt(state.checkin) + (state.checkout ? " to " + fmt(state.checkout) : "")
      : "dates to be confirmed";
    var n = nights();
    var nPart = n > 0 ? " (" + n + " night" + (n > 1 ? "s" : "") + ")" : "";
    return (
      "Hi! I'd like the " + state.room +
      " for " + dates + nPart +
      ", " + state.guests + " guest" + (state.guests > 1 ? "s" : "") +
      " — available?"
    );
  }

  function validate() {
    if (!state.room) return "Pick a room type first.";
    if (!state.checkin) return "Add your check-in date.";
    if (!state.checkout) return "Add your check-out date.";
    if (nights() <= 0) return "Check-out must be after check-in.";
    return "";
  }

  function render() {
    previewEl.textContent = compose();
    var msg = validate();
    errorEl.textContent = msg;
    errorEl.classList.toggle("show", !!msg);
    outInput.classList.toggle("invalid", !!(state.checkin && state.checkout && nights() <= 0));
    var ready = !msg;
    [sendWa, sendMail].forEach(function (b) {
      b.disabled = !ready;
      b.style.opacity = ready ? "" : "0.45";
    });
  }

  form.querySelectorAll(".pick-option input").forEach(function (input) {
    input.addEventListener("change", function () {
      state.room = input.value;
      render();
    });
  });
  form.querySelector("#checkin").addEventListener("change", function () {
    state.checkin = this.value || null;
    render();
  });
  outInput.addEventListener("change", function () {
    state.checkout = this.value || null;
    render();
  });
  form.querySelectorAll(".stepper button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var delta = Number(btn.getAttribute("data-step"));
      state.guests = Math.min(10, Math.max(1, state.guests + delta));
      form.querySelector(".stepper output").textContent = state.guests;
      render();
    });
  });

  if (CFG.whatsapp) {
    sendWa.addEventListener("click", function () {
      if (validate()) return render();
      window.open(
        "https://wa.me/" + CFG.whatsapp.replace(/\D/g, "") +
        "?text=" + encodeURIComponent(compose()),
        "_blank",
        "noopener"
      );
    });
  } else {
    sendWa.hidden = true; // no fabricated link — copy path below always works
  }
  if (CFG.email) {
    sendMail.addEventListener("click", function () {
      if (validate()) return render();
      window.location.href =
        "mailto:" + CFG.email +
        "?subject=" + encodeURIComponent("Room enquiry — Pal Hotel") +
        "&body=" + encodeURIComponent(compose());
    });
  } else {
    sendMail.hidden = true;
  }

  copyBtn.addEventListener("click", function () {
    var text = compose();
    function done() {
      copyBtn.classList.add("copied");
      copyBtn.querySelector(".copy-label").textContent = "Copied!";
      setTimeout(function () {
        copyBtn.classList.remove("copied");
        copyBtn.querySelector(".copy-label").textContent = "Copy message";
      }, 1600);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done);
    } else {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch (e) { /* ponytail: execCommand fallback ceiling — modern browsers all ship navigator.clipboard */ }
      document.body.removeChild(ta);
      done();
    }
  });

  /* preselect room when arriving from a teaser card (?room=Double%20Room#selector) */
  var wanted = new URLSearchParams(window.location.search).get("room");
  if (wanted) {
    var match = form.querySelector('.pick-option input[value="' + CSS.escape(wanted) + '"]');
    if (match) {
      match.checked = true;
      state.room = match.value;
    }
  }

  render();
})();
