/* MANIT Canteen — page wiring */
"use strict";

// TODO-OWNER: fill these in and the WhatsApp / call / mail buttons go live
// instantly. Until then the composer's copy button still works everywhere.
var OWNER = {
  whatsapp: "", // e.g. "919876543210" (country code + number, no +)
  phone: "",    // e.g. "+919876543210"
  email: ""     // e.g. "canteen@manit.ac.in"
};

(function () {
  var api = window.MANIT;

  /* Contact buttons from OWNER config; missing ones route to the composer.
     WhatsApp works numberless today (share-sheet), upgrades when OWNER fills. */
  document.querySelectorAll("[data-contact]").forEach(function (el) {
    var kind = el.getAttribute("data-contact");
    var msg = encodeURIComponent("Hello MANIT Canteen — I have an inquiry.");
    var href = null;
    if (kind === "wa") href = "https://wa.me/" + OWNER.whatsapp + "?text=" + msg;
    if (kind === "tel" && OWNER.phone) href = "tel:" + OWNER.phone;
    if (kind === "mail" && OWNER.email) href = "mailto:" + OWNER.email + "?subject=" + msg;
    if (href) el.setAttribute("href", href);
    else {
      el.setAttribute("href", "contact.html#composer");
      el.setAttribute("title", "Contact details pending — use the inquiry composer");
      el.querySelector(".btn-label").textContent =
        el.querySelector(".btn-label").getAttribute("data-pending") || el.querySelector(".btn-label").textContent;
    }
  });

  /* Scroll reveals, staggered in reading order */
  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { threshold: 0.15 });
    revealEls.forEach(function (el, i) {
      el.style.setProperty("--d", (i % 6) * 80 + "ms");
      io.observe(el);
    });
  } else {
    revealEls.forEach(function (el) { el.classList.add("in"); });
  }

  /* Inquiry composer */
  var composer = document.getElementById("composer");
  if (!composer) return;

  var state = {};           // name -> qty
  var preview = composer.querySelector(".preview");
  var noteEl = composer.querySelector(".note");

  composer.querySelectorAll(".chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      var name = chip.getAttribute("data-item");
      if (state[name]) {
        delete state[name];
        chip.setAttribute("aria-pressed", "false");
      } else {
        state[name] = 1;
        chip.setAttribute("aria-pressed", "true");
      }
      renderPicks();
    });
  });

  function renderPicks() {
    var wrap = composer.querySelector(".picks");
    wrap.textContent = "";
    Object.keys(state).forEach(function (name) {
      var row = document.createElement("div");
      row.className = "pick-row";

      var label = document.createElement("span");
      label.className = "name";
      label.textContent = name;
      row.appendChild(label);

      var step = document.createElement("span");
      step.className = "stepper";
      var minus = document.createElement("button");
      minus.type = "button";
      minus.textContent = "\u2212";
      minus.setAttribute("aria-label", "One less " + name);
      var out = document.createElement("output");
      out.textContent = state[name];
      var plus = document.createElement("button");
      plus.type = "button";
      plus.textContent = "+";
      plus.setAttribute("aria-label", "One more " + name);

      function setQty(q) {
        state[name] = api.clampQty(q);
        if (state[name] === 0) {
          delete state[name];
          composer.querySelector('[data-item="' + name + '"]').setAttribute("aria-pressed", "false");
          renderPicks();
          return;
        }
        out.textContent = state[name];
        update();
      }
      minus.addEventListener("click", function () { setQty(state[name] - 1); });
      plus.addEventListener("click", function () { setQty(state[name] + 1); });

      step.appendChild(minus); step.appendChild(out); step.appendChild(plus);
      row.appendChild(step);
      wrap.appendChild(row);
    });
    update();
  }

  function items() {
    return Object.keys(state).map(function (name) { return { name: name, qty: state[name] }; });
  }

  function update() {
    var text = api.compose(items(), api.clampNote(noteEl.value), "plain");
    preview.textContent = text;
    var wa = composer.querySelector(".act-wa");
    wa.href = "https://wa.me/" + OWNER.whatsapp + "?text=" + encodeURIComponent(text);
    var mail = composer.querySelector(".act-mail");
    if (OWNER.email) {
      mail.href = "mailto:" + OWNER.email + "?subject=" +
        encodeURIComponent("Order inquiry — MANIT Canteen") + "&body=" + encodeURIComponent(text);
    } else {
      mail.hidden = true;
    }
  }

  noteEl.addEventListener("input", update);

  composer.querySelector(".act-copy").addEventListener("click", function () {
    var btn = this;
    function done(ok) {
      var state2 = composer.querySelector(".copy-state");
      state2.textContent = ok ? "Copied \u2713" : "Copy failed \u2014 select the text above";
      state2.classList.add("show");
      setTimeout(function () { state2.classList.remove("show"); }, 2000);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(preview.textContent).then(function () { done(true); }, function () { done(false); });
    } else {
      /* fallback: select the preview text so Ctrl-C works */
      var range = document.createRange();
      range.selectNodeContents(preview);
      var sel = window.getSelection();
      sel.removeAllRanges(); sel.addRange(range);
      done(false);
    }
  });

  update();
})();
