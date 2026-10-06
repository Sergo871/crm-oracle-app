/* Plan de lucru (Gantt): tragerea barelor (mutare / termen), salvarea prin POST cu token CSRF,
   sagetile intre sarcinile dependente si restrangerea sarcinilor unui proiect. */
(function () {
  'use strict';
  var gantt = document.getElementById('gantt');
  if (!gantt) return;
  var DAY = 864e5;
  var lo = Date.parse(gantt.dataset.lo), days = parseInt(gantt.dataset.days, 10);
  var today = Date.parse(gantt.dataset.today);
  var svg = gantt.querySelector('.g-links');
  var toastEl = document.getElementById('g-toast'), toastTimer;
  var STATES = {done: 'gata', lost: 'anulat', late: 'întârziat', work: 'în lucru', plan: 'planificat'};

  // ---- utilitare
  function iso(t) { return new Date(t).toISOString().slice(0, 10); }
  function ro(t) { var s = iso(t); return s.slice(8, 10) + '.' + s.slice(5, 7) + '.' + s.slice(0, 4); }
  function pct(n) { return (n * 100 / days).toFixed(4) + '%'; }
  function toast(msg, isErr) {
    toastEl.textContent = msg;
    toastEl.className = 'kb-toast show' + (isErr ? ' err' : '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.className = 'kb-toast'; }, isErr ? 5000 : 2200);
  }
  function stateOf(bar) {
    return (bar.className.match(/\bs-(\w+)/) || [])[1];
  }

  // pozitioneaza bara (si partea intarziata) dupa data-start / data-end
  function place(bar, start, end) {
    bar.style.left = pct((start - lo) / DAY);
    bar.style.width = pct((end - start) / DAY + 1);
    var track = bar.parentNode, over = track.querySelector('.g-overdue');
    var st = stateOf(bar);
    if (st === 'late' || st === 'work' || st === 'plan') {
      var late = end < today;
      bar.classList.remove('s-late', 's-work', 's-plan');
      bar.classList.add(late ? 's-late' : (bar.dataset.base || 'work') === 'plan' ? 's-plan' : 's-work');
      if (late) {
        if (!over) { over = document.createElement('div'); over.className = 'g-overdue'; track.appendChild(over); }
        over.style.left = pct((end - lo) / DAY + 1);
        over.style.width = pct((today - end) / DAY);
      } else if (over) {
        over.remove();
      }
    }
  }

  // ---- sagetile „dupa sarcina”
  function drawLinks() {
    while (svg.lastChild && svg.lastChild.nodeName !== 'defs') svg.removeChild(svg.lastChild);
    var box = svg.getBoundingClientRect();
    gantt.querySelectorAll('.g-bar[data-dep]').forEach(function (b) {
      var a = gantt.querySelector('.g-bar[data-kind="' + b.dataset.kind + '"][data-id="' + b.dataset.dep + '"]');
      if (!a || !a.offsetParent || !b.offsetParent) return;  // randuri restranse
      var ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
      // din coltul de jos al celei precedente, in jos pana la randul sarcinii, apoi spre inceputul ei
      var x1 = Math.max(ra.left + 2, ra.right - 4) - box.left, y1 = ra.bottom - box.top;
      var x2 = rb.left - box.left, y2 = rb.top + rb.height / 2 - box.top;
      var p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      p.setAttribute('d', 'M' + x1 + ' ' + y1 + 'V' + y2 + 'H' + (x2 - 1));
      p.setAttribute('marker-end', 'url(#g-arrow)');
      if (Date.parse(b.dataset.start) < Date.parse(a.dataset.end)) {
        p.setAttribute('class', 'bad');
        p.setAttribute('marker-end', 'url(#g-arrow-bad)');
        p.appendChild(document.createElementNS('http://www.w3.org/2000/svg', 'title'))
          .textContent = 'Sarcina începe înainte să se termine cea precedentă';
      }
      svg.appendChild(p);
    });
  }

  // ---- restrangerea sarcinilor unui proiect
  gantt.addEventListener('click', function (e) {
    var btn = e.target.closest('.g-fold');
    if (!btn) return;
    var row = btn.closest('.g-row'), id = row.dataset.group;
    var folded = row.classList.toggle('folded');
    btn.setAttribute('aria-expanded', String(!folded));
    gantt.querySelectorAll('.g-row[data-parent="' + id + '"]').forEach(function (r) { r.hidden = folded; });
    drawLinks();
  });

  // ---- dublu clic deschide fisa
  gantt.addEventListener('dblclick', function (e) {
    var bar = e.target.closest('.g-bar');
    if (bar) window.location.href = bar.dataset.href;
  });

  // ---- tragerea barelor (mouse si touch, prin Pointer Events)
  var drag = null, tip = null;
  function showTip(x, y, text) {
    if (!tip) { tip = document.createElement('div'); tip.className = 'g-tip'; document.body.appendChild(tip); }
    tip.textContent = text;
    tip.style.left = (x + 14) + 'px';
    tip.style.top = (y - 34) + 'px';
  }
  function hideTip() { if (tip) { tip.remove(); tip = null; } }

  gantt.querySelectorAll('.g-bar.mov').forEach(function (b) {
    var st = stateOf(b);
    if (st === 'plan' || st === 'work') b.dataset.base = st;
  });

  gantt.addEventListener('pointerdown', function (e) {
    var bar = e.target.closest('.g-bar.mov');
    if (!bar || e.button > 0 || bar.classList.contains('saving')) return;
    e.preventDefault();
    bar.setPointerCapture(e.pointerId);
    drag = {
      bar: bar, x0: e.clientX, mode: e.target.classList.contains('g-h') ? 'end' : 'move',
      start: Date.parse(bar.dataset.start), end: Date.parse(bar.dataset.end), dd: 0,
      dayPx: bar.parentNode.getBoundingClientRect().width / days
    };
  });

  gantt.addEventListener('pointermove', function (e) {
    if (!drag) return;
    var dd = Math.round((e.clientX - drag.x0) / drag.dayPx);
    if (drag.mode === 'end') dd = Math.max(dd, (drag.start - drag.end) / DAY);
    if (dd !== drag.dd) {
      drag.dd = dd;
      drag.bar.classList.add('dragging');
      var s = drag.mode === 'move' ? drag.start + dd * DAY : drag.start, en = drag.end + dd * DAY;
      place(drag.bar, s, en);
      drawLinks();
    }
    if (drag.dd) {
      var s2 = drag.mode === 'move' ? drag.start + drag.dd * DAY : drag.start;
      showTip(e.clientX, e.clientY, ro(s2) + ' — ' + ro(drag.end + drag.dd * DAY) +
              ' (' + (drag.dd > 0 ? '+' : '') + drag.dd + ' z)');
    }
  });

  function finish(e, cancel) {
    if (!drag) return;
    var d = drag; drag = null;
    hideTip();
    d.bar.classList.remove('dragging');
    if (!d.dd) return;
    var start = d.mode === 'move' ? d.start + d.dd * DAY : d.start, end = d.end + d.dd * DAY;
    if (cancel) { place(d.bar, d.start, d.end); drawLinks(); return; }
    save(d.bar, start, end, d.start, d.end);
  }
  gantt.addEventListener('pointerup', function (e) { finish(e, false); });
  gantt.addEventListener('pointercancel', function (e) { finish(e, true); });

  function save(bar, start, end, oldStart, oldEnd) {
    bar.classList.add('saving');
    var body = new FormData();
    body.append('_csrf', gantt.dataset.csrf);
    body.append('start', iso(start));
    body.append('end', iso(end));
    fetch(bar.dataset.url, {
      method: 'POST', body: body, credentials: 'same-origin',
      headers: {'X-Requested-With': 'fetch', 'Accept': 'application/json'}
    }).then(function (r) {
      return r.json().catch(function () { return {ok: false, error: 'Răspuns neașteptat (' + r.status + ').'}; });
    }).then(function (res) {
      if (!res.ok) throw new Error(res.error || 'Eroare la salvare.');
      bar.classList.remove('saving');
      bar.dataset.start = iso(start);
      bar.dataset.end = iso(end);
      var name = bar.title.slice(0, bar.title.lastIndexOf(': '));
      bar.title = name + ': ' + res.start + ' — ' + res.end + ' · ' + STATES[stateOf(bar)];
      drawLinks();
      toast('Salvat: ' + res.start + ' — ' + res.end);
    }).catch(function (err) {
      bar.classList.remove('saving');
      place(bar, oldStart, oldEnd);
      drawLinks();
      toast(err.message, true);
    });
  }

  drawLinks();
  window.addEventListener('resize', drawLinks);
  if (window.ResizeObserver) new ResizeObserver(drawLinks).observe(gantt);
})();
