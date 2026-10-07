/* exocean — small progressive enhancements. The site works without them.
   1. E-mail addresses are assembled here, so they are not sitting in the
      markup for address harvesters.
   2. The menu button on phones.
   3. The search box and person filter on the Publications page.
   4. When visitor counting (GoatCounter) is switched on: count clicks on
      e-mail addresses, PDF downloads and links to other sites, so the
      statistics show who tried to get in touch and which resources are used. */
(function () {
  "use strict";

  document.querySelectorAll(".eml").forEach(function (el) {
    var user = el.getAttribute("data-u");
    var domain = el.getAttribute("data-d");
    if (!user || !domain) return;
    var address = user + "@" + domain;
    var a = document.createElement("a");
    a.href = "mailto:" + address;
    a.textContent = address;
    if (el.className.indexOf("big") !== -1) a.className = "big";
    el.replaceWith(a);
  });

  // --- menu button (phones and small tablets) ---------------------------
  var header = document.querySelector(".site-header");
  var toggle = document.querySelector(".menu-toggle");
  if (header && toggle) {
    var setOpen = function (open) {
      header.classList.toggle("menu-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    };
    toggle.addEventListener("click", function () {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
        setOpen(false);
        toggle.focus();
      }
    });
    document.addEventListener("click", function (e) {
      if (!header.contains(e.target)) setOpen(false);
    });
  }

  // --- publications: search box + person chips ---------------------------
  var tools = document.getElementById("pub-tools");
  if (tools) {
    tools.hidden = false;
    var search = document.getElementById("pub-search");
    var chips = tools.querySelectorAll(".chip");
    var status = document.getElementById("pub-status");
    var items = document.querySelectorAll("#pub-all .pubs li");
    var years = document.querySelectorAll("#pub-all .pub-year");
    var person = "";
    var fold = function (s) {
      return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    };
    var apply = function () {
      var q = fold(search.value.trim());
      var shown = 0;
      items.forEach(function (li) {
        var ok = (!person || (" " + li.getAttribute("data-people") + " ").indexOf(" " + person + " ") !== -1) &&
                 (!q || fold(li.textContent).indexOf(q) !== -1);
        li.hidden = !ok;
        if (ok) shown++;
      });
      years.forEach(function (y) {
        var visible = y.querySelectorAll(".pubs li:not([hidden])").length;
        var count = y.querySelector(".pub-count");
        y.hidden = !visible;
        if (count) count.textContent = (q || person) ? visible : count.getAttribute("data-total");
        if ((q || person) && visible && y.tagName === "DETAILS") y.open = true;
      });
      var filtering = q || person;
      status.textContent = filtering ? shown + " of " + items.length + " publications shown" : items.length + " publications";
    };
    search.addEventListener("input", apply);
    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        person = chip.getAttribute("data-person") || "";
        chips.forEach(function (c) { c.setAttribute("aria-pressed", c === chip ? "true" : "false"); });
        apply();
      });
    });
    apply();
  }

  // --- visitor statistics: count a few meaningful clicks as events --------
  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a[href]") : null;
    if (!a || !window.goatcounter || !window.goatcounter.count) return;
    var href = a.getAttribute("href") || "";
    var name = null;
    if (href.indexOf("mailto:") === 0) {
      name = "email-" + href.slice(7).split("@")[0];
    } else if (/\.pdf($|[?#])/i.test(href) && a.host === location.host) {
      name = "download-" + href.split("/").pop().split(/[?#]/)[0];
    } else if (a.host && a.host !== location.host) {
      name = "out-" + a.host.replace(/^www\./, "");
    }
    if (!name) return;
    window.goatcounter.count({
      path: name,
      title: (a.textContent || "").replace(/\s+/g, " ").trim().slice(0, 100),
      referrer: location.pathname,
      event: true
    });
  });
})();
