/**
 * Instrumentl Auto-Save Bookmarklet
 * ----------------------------------
 * Navigate to your Instrumentl project's Matches page, then click the bookmark.
 * The script waits for each Save button, clicks it, then waits a random 8–15 s
 * before looking for the next one (which loads automatically).
 *
 * To install: minify this file (or use the one-liner in bookmarklet.html) and
 * save it as a browser bookmark with the javascript: URL as the address.
 */
(function () {
  // If already running, stop it instead of starting a second instance
  if (window.__iasRunning) {
    window.__iasRunning = false;
    return;
  }
  window.__iasRunning = true;

  var MIN_DELAY = 8000;   // 8 s
  var MAX_DELAY = 15000;  // 15 s
  var saved = 0;

  // ── Status overlay ────────────────────────────────────────────────────────
  var box = document.createElement('div');
  box.id = '__ias_box';
  box.style.cssText = [
    'position:fixed', 'top:12px', 'right:12px', 'z-index:2147483647',
    'background:#1e293b', 'color:#f8fafc',
    'padding:14px 18px', 'border-radius:10px',
    'font:13px/1.6 system-ui,sans-serif',
    'box-shadow:0 4px 20px rgba(0,0,0,.45)',
    'min-width:230px', 'max-width:300px',
  ].join(';');
  box.innerHTML =
    '<b style="font-size:14px">🤖 Instrumentl Auto-Save</b>' +
    '<div id="__ias_msg" style="margin:6px 0 10px;color:#94a3b8">Starting…</div>' +
    '<button id="__ias_stop" style="background:#ef4444;border:0;color:#fff;' +
    'padding:5px 14px;border-radius:6px;cursor:pointer;font-size:12px">⏹ Stop</button>';
  document.body.appendChild(box);

  var msgEl = document.getElementById('__ias_msg');

  function setMsg(s) { msgEl.textContent = s; }

  document.getElementById('__ias_stop').onclick = function () {
    window.__iasRunning = false;
    setMsg('Stopped. Saved ' + saved + ' grant(s).');
    setTimeout(function () { box.remove(); }, 3000);
  };

  // ── Wait for .save-button-container > .btn to be visible ─────────────────
  function waitForBtn(timeoutMs) {
    return new Promise(function (resolve, reject) {
      var deadline = Date.now() + timeoutMs;
      var interval = setInterval(function () {
        var el = document.querySelector('.save-button-container > .btn');
        if (el && el.offsetParent !== null) {
          clearInterval(interval);
          resolve(el);
        } else if (Date.now() > deadline) {
          clearInterval(interval);
          reject(new Error('timeout'));
        }
      }, 600);
    });
  }

  // ── Countdown delay ───────────────────────────────────────────────────────
  function countdownDelay(ms) {
    return new Promise(function (resolve) {
      var end = Date.now() + ms;
      var t = setInterval(function () {
        if (!window.__iasRunning) { clearInterval(t); resolve(); return; }
        var s = Math.ceil((end - Date.now()) / 1000);
        if (s <= 0) { clearInterval(t); resolve(); }
        else setMsg('Saved ' + saved + '. Next in ' + s + 's…');
      }, 1000);
    });
  }

  // ── Main loop ─────────────────────────────────────────────────────────────
  (async function loop() {
    while (window.__iasRunning) {
      try {
        setMsg('Waiting for Save button…');
        var el = await waitForBtn(20000);
        if (!window.__iasRunning) break;

        saved++;
        setMsg('Clicking Save #' + saved + '…');
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        await new Promise(function (r) { setTimeout(r, 400); });
        el.click();

        var delay = Math.random() * (MAX_DELAY - MIN_DELAY) + MIN_DELAY;
        await countdownDelay(delay);

      } catch (e) {
        setMsg('Done! Saved ' + saved + ' grant(s).');
        window.__iasRunning = false;
        setTimeout(function () { box.remove(); }, 6000);
        break;
      }
    }
  })();
})();
