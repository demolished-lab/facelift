/* Shree Krishna Chaat — shared behaviour */
(function () {
  "use strict";

  /* Integration boundary: fill with owner's WhatsApp number in international
     format (e.g. "919876543210") to activate the wa.me send button. */
  var WHATSAPP_NUMBER = "";

  /* mobile nav */
  var btn = document.querySelector(".menu-btn");
  var nav = document.getElementById("site-nav");
  if (btn && nav) {
    btn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  /* sequenced scroll reveals, reading order */
  var els = document.querySelectorAll(".rv");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    els.forEach(function (el, i) {
      el.style.transitionDelay = Math.min(i * 70, 280) + "ms";
      io.observe(el);
    });
  } else {
    els.forEach(function (el) { el.classList.add("in"); });
  }

  /* FAQ accordion */
  document.querySelectorAll(".faq-item button").forEach(function (b) {
    b.addEventListener("click", function () {
      var expanded = b.getAttribute("aria-expanded") === "true";
      b.setAttribute("aria-expanded", expanded ? "false" : "true");
      var panel = document.getElementById(b.getAttribute("aria-controls"));
      if (panel) panel.classList.toggle("open", !expanded);
    });
  });

  /* ---- Order Note Composer (signature component) ---- */
  var root = document.getElementById("composer");
  if (!root) return;

  var state = { items: {}, mode: "Pickup", spice: "Medium" };

  function money(n) { return n > 0 ? n + " plate" + (n > 1 ? "s" : "") : ""; }

  function buildMessage() {
    var lines = ["Order note - Shree Krishna Chaat", ""];
    var picked = Object.keys(state.items).filter(function (k) { return state.items[k] > 0; });
    if (picked.length) {
      lines.push("Items:");
      picked.forEach(function (name) { lines.push("  " + state.items[name] + " x " + name); });
    }
    lines.push("Mode: " + state.mode);
    lines.push("Spice: " + state.spice);
    var name = (root.querySelector("#c-name").value || "").trim();
    var note = (root.querySelector("#c-note").value || "").trim();
    if (name) lines.push("Name: " + name);
    if (note) lines.push("Note: " + note);
    lines.push("", "(sent from shreekrishnachaat website order composer)");
    return lines.join("\n");
  }

  function refresh() {
    root.querySelector("output").textContent = buildMessage();
    var any = Object.keys(state.items).some(function (k) { return state.items[k] > 0; }) ||
              (root.querySelector("#c-note").value || "").trim().length > 0;
    root.querySelector(".err").classList.toggle("show", !any);
    return any;
  }

  /* item checkboxes + steppers */
  root.querySelectorAll(".item").forEach(function (row) {
    var name = row.getAttribute("data-item");
    var cb = row.querySelector('input[type="checkbox"]');
    var out = row.querySelector("output");
    var minus = row.querySelector("[data-step='-1']");
    var plus = row.querySelector("[data-step='1']");
    function setQty(q) {
      q = Math.max(0, Math.min(6, q));
      state.items[name] = q;
      out.textContent = q;
      cb.checked = q > 0;
      refresh();
    }
    cb.addEventListener("change", function () { setQty(cb.checked ? 1 : 0); });
    minus.addEventListener("click", function () { setQty((state.items[name] || 0) - 1); });
    plus.addEventListener("click", function () { setQty((state.items[name] || 0) + 1); });
    state.items[name] = 0;
  });

  /* segmented toggles */
  root.querySelectorAll(".seg").forEach(function (seg) {
    seg.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-value]");
      if (!b) return;
      seg.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", "false"); });
      b.setAttribute("aria-pressed", "true");
      state[seg.getAttribute("data-key")] = b.getAttribute("data-value");
      refresh();
    });
  });

  root.querySelector("#c-name").addEventListener("input", refresh);
  root.querySelector("#c-note").addEventListener("input", refresh);

  /* copy handoff — works today, zero setup */
  var copyBtn = root.querySelector("[data-copy]");
  copyBtn.addEventListener("click", function () {
    if (!refresh()) return;
    var msg = buildMessage();
    function done() {
      copyBtn.classList.add("copied");
      copyBtn.textContent = "Copied \u2713";
      setTimeout(function () {
        copyBtn.classList.remove("copied");
        copyBtn.textContent = "Copy order note";
      }, 1500);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(msg).then(done, done);
    } else {
      var ta = document.createElement("textarea");
      ta.value = msg; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); } catch (err) {}
      document.body.removeChild(ta); done();
    }
  });

  /* wa.me handoff — activates only when number configured */
  var sendBtn = root.querySelector("[data-send]");
  if (WHATSAPP_NUMBER) {
    sendBtn.hidden = false;
    root.querySelector(".owner-banner").hidden = true;
    sendBtn.addEventListener("click", function () {
      if (!refresh()) return;
      window.open("https://wa.me/" + WHATSAPP_NUMBER + "?text=" + encodeURIComponent(buildMessage()), "_blank", "noopener");
    });
  }
})();
