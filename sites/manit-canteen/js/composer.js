/* MANIT Canteen — inquiry message composer (pure logic, no DOM) */
(function (root) {
  "use strict";

  var MAX_NOTE = 500;
  var MAX_QTY = 99;

  function compose(items, note, source) {
    var lines = ["Order inquiry — MANIT Canteen", ""];
    if (items.length === 0) {
      lines.push("I would like to ask about availability and today's menu.");
    } else {
      lines.push("My order:");
      items.forEach(function (it) {
        lines.push("- " + it.qty + " x " + it.name);
      });
    }
    lines.push("");
    if (note) lines.push("Note: " + note);
    lines.push("(sent from the MANIT Canteen website)");
    var text = lines.join("\n");
    if (source === "wa") text = encodeURIComponent(text);
    return text;
  }

  function clampQty(n) {
    n = Math.floor(Number(n) || 0);
    return Math.min(MAX_QTY, Math.max(0, n));
  }

  function clampNote(s) {
    return String(s || "").slice(0, MAX_NOTE);
  }

  var api = { compose: compose, clampQty: clampQty, clampNote: clampNote, MAX_NOTE: MAX_NOTE };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MANIT = api;
})(this);
