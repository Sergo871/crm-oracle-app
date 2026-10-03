/* Kanban: mutarea cardurilor intre coloane (mouse si touch, prin Pointer Events)
   si salvarea noii etape prin POST cu token CSRF. */
(function () {
  'use strict';
  var board = document.getElementById('kanban');
  if (!board) return;
  var toastEl = document.getElementById('kb-toast');
  var hasSum = board.dataset.hasSum === '1';
  var drag = null;          // starea gestului curent
  var suppressClick = false;
  var toastTimer;

  // ---- utilitare
  function money(n) {
    var neg = n < 0, s = Math.abs(n).toFixed(2).split('.');
    s[0] = s[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    return (neg ? '-' : '') + s[0] + ',' + s[1];
  }
  function toast(msg, isErr) {
    toastEl.textContent = msg;
    toastEl.className = 'kb-toast show' + (isErr ? ' err' : '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.className = 'kb-toast'; }, isErr ? 5000 : 2200);
  }
  function colOf(el) { return el && el.closest('.kb-col'); }
  function adjust(col, dn, ds) {
    var n = col.querySelector('.kb-n');
    var cnt = parseInt(n.dataset.n, 10) + dn;
    n.dataset.n = cnt; n.textContent = cnt;
    if (hasSum) {
      var s = col.querySelector('.kb-sum');
      var tot = parseFloat(s.dataset.total) + ds;
      s.dataset.total = tot;
      s.firstChild.nodeValue = money(tot) + ' ';
    }
    var empty = col.querySelector('.kb-empty');
    if (empty) empty.hidden = cnt > 0;
  }

  // ---- mutarea propriu-zisa (optimist, cu revenire la eroare)
  function move(card, target) {
    var from = colOf(card);
    if (!target || target === from || target.classList.contains('nodrop')) return;
    var amount = parseFloat(card.dataset.amount) || 0;
    var anchor = card.nextSibling;
    target.querySelector('.kb-cards').prepend(card);
    adjust(from, -1, -amount); adjust(target, 1, amount);
    card.classList.add('saving');

    var body = new FormData();
    body.append('_csrf', board.dataset.csrf);
    body.append('value', target.dataset.value);
    fetch(card.dataset.url, {
      method: 'POST', body: body, credentials: 'same-origin',
      headers: {'X-Requested-With': 'fetch', 'Accept': 'application/json'}
    }).then(function (r) {
      return r.json().catch(function () { return {ok: false, error: 'Răspuns neașteptat (' + r.status + ').'}; });
    }).then(function (res) {
      if (!res.ok) throw new Error(res.error || 'Eroare la salvare.');
      card.classList.remove('saving');
      if (board.dataset.table === 'tasks') {   // etapa Gata <=> sarcina facuta
        var done = target.dataset.value === 'Готово';
        card.classList.toggle('done', done);
        if (done) card.classList.remove('late');
      }
      flash(card);
      toast('Mutat în „' + target.dataset.label + '”.');
    }).catch(function (err) {
      card.classList.remove('saving');
      from.querySelector('.kb-cards').insertBefore(card, anchor && anchor.parentNode ? anchor : null);
      adjust(target, -1, -amount); adjust(from, 1, amount);
      toast(err.message || 'Nu s-a putut salva.', true);
    });
  }
  function flash(card) {
    card.classList.remove('moved'); void card.offsetWidth; card.classList.add('moved');
  }

  // ---- drag & drop cu Pointer Events
  function onDown(e) {
    var card = e.target.closest('.kb-card');
    if (!card || e.button > 0 || e.target.closest('.kb-menu')) return;
    drag = {card: card, id: e.pointerId, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY,
            touch: e.pointerType !== 'mouse', active: false, timer: null};
    if (drag.touch) {
      // pe telefon: apasare lunga, ca derularea orizontala a tablei sa ramana libera
      drag.timer = setTimeout(function () { if (drag && !drag.active) begin(); }, 350);
    }
    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
    document.addEventListener('pointercancel', onCancel);
  }
  function begin() {
    var card = drag.card, r = card.getBoundingClientRect();
    drag.active = true;
    drag.dx = drag.x0 - r.left; drag.dy = drag.y0 - r.top;
    var g = card.cloneNode(true);
    g.classList.add('kb-ghost');
    g.style.width = r.width + 'px';
    document.body.appendChild(g);
    drag.ghost = g;
    card.classList.add('kb-placeholder');
    document.documentElement.classList.add('kb-dragging');
    if (navigator.vibrate && drag.touch) { try { navigator.vibrate(25); } catch (x) {} }
    place();
    tick();
  }
  function onMove(e) {
    if (!drag || e.pointerId !== drag.id) return;
    drag.x = e.clientX; drag.y = e.clientY;
    var dist = Math.abs(drag.x - drag.x0) + Math.abs(drag.y - drag.y0);
    if (!drag.active) {
      if (drag.touch) { if (dist > 10) cleanup(); }   // utilizatorul deruleaza
      else if (dist > 5) begin();
      return;
    }
    e.preventDefault();
    place();
  }
  function place() {
    drag.ghost.style.transform = 'translate(' + (drag.x - drag.dx) + 'px,' + (drag.y - drag.dy) + 'px) rotate(2deg)';
    var under = document.elementFromPoint(drag.x, drag.y);
    var col = colOf(under);
    if (col !== drag.over) {
      if (drag.over) drag.over.classList.remove('kb-over');
      drag.over = col && !col.classList.contains('nodrop') ? col : null;
      if (drag.over) drag.over.classList.add('kb-over');
    }
  }
  // derulare automata cand cardul ajunge la marginea tablei sau a ferestrei
  function tick() {
    if (!drag || !drag.active) return;
    var b = board.getBoundingClientRect(), edge = 60, step = 0;
    if (drag.x < b.left + edge) step = -14; else if (drag.x > b.right - edge) step = 14;
    if (step) { board.scrollLeft += step; place(); }
    var vy = 0;
    if (drag.y < 70) vy = -12; else if (drag.y > window.innerHeight - 50) vy = 12;
    if (vy) { window.scrollBy(0, vy); place(); }
    drag.raf = requestAnimationFrame(tick);
  }
  function onUp(e) {
    if (!drag || e.pointerId !== drag.id) return;
    if (drag.active) {
      var card = drag.card, target = drag.over;
      suppressClick = true;
      setTimeout(function () { suppressClick = false; }, 50);
      cleanup();
      move(card, target);
    } else cleanup();
  }
  function onCancel() { cleanup(); }
  function cleanup() {
    if (!drag) return;
    clearTimeout(drag.timer);
    cancelAnimationFrame(drag.raf);
    if (drag.ghost) drag.ghost.remove();
    if (drag.over) drag.over.classList.remove('kb-over');
    drag.card.classList.remove('kb-placeholder');
    document.documentElement.classList.remove('kb-dragging');
    document.removeEventListener('pointermove', onMove);
    document.removeEventListener('pointerup', onUp);
    document.removeEventListener('pointercancel', onCancel);
    drag = null;
  }

  board.addEventListener('pointerdown', onDown);
  // in timpul tragerii pe ecran tactil pagina nu trebuie sa se derulze
  document.addEventListener('touchmove', function (e) {
    if (drag && drag.active) e.preventDefault();
  }, {passive: false});
  board.addEventListener('contextmenu', function (e) {
    if (drag && e.target.closest('.kb-card')) e.preventDefault();   // apasarea lunga pe telefon
  });
  board.addEventListener('click', function (e) {
    if (suppressClick) { e.preventDefault(); e.stopPropagation(); }
  }, true);
  board.addEventListener('dragstart', function (e) { e.preventDefault(); });

  // ---- alternativa fara tragere: meniul ⋯ de pe card
  var menu = document.createElement('div');
  menu.className = 'kb-pop';
  menu.setAttribute('role', 'menu');
  document.body.appendChild(menu);
  var menuCard = null;
  function closeMenu() { menu.classList.remove('open'); menuCard = null; }
  board.addEventListener('click', function (e) {
    var btn = e.target.closest('.kb-menu');
    if (!btn) return;
    e.preventDefault(); e.stopPropagation();
    var card = btn.closest('.kb-card');
    if (menuCard === card) { closeMenu(); return; }
    menuCard = card;
    var cur = colOf(card);
    menu.innerHTML = '<div class="kb-pop-h">Mută în:</div>';
    board.querySelectorAll('.kb-col:not(.nodrop)').forEach(function (col) {
      var it = document.createElement('button');
      it.type = 'button';
      it.className = 'kb-pop-i' + (col === cur ? ' cur' : '');
      it.style.setProperty('--c', col.style.getPropertyValue('--c'));
      it.textContent = col.dataset.label;
      it.disabled = col === cur;
      it.addEventListener('click', function () { closeMenu(); move(card, col); });
      menu.appendChild(it);
    });
    var r = btn.getBoundingClientRect();
    menu.classList.add('open');
    var w = menu.offsetWidth, h = menu.offsetHeight;
    var left = Math.min(r.right - w, window.innerWidth - w - 8);
    var top = r.bottom + 4 + h > window.innerHeight ? r.top - h - 4 : r.bottom + 4;
    menu.style.left = Math.max(8, left) + window.scrollX + 'px';
    menu.style.top = Math.max(8, top) + window.scrollY + 'px';
  });
  document.addEventListener('click', function (e) { if (!menu.contains(e.target)) closeMenu(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenu(); });
  board.addEventListener('scroll', closeMenu, {passive: true});
})();
