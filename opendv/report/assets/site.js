// Sidebar: list of regressions (assets/runs.js); tests are reached via the main page.
(function () {
  var b = document.body, root = b.dataset.root, cur = b.dataset.run, curT = b.dataset.target;
  var side = document.getElementById('side'), runs = window.RUNS || [];
  function h(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
  var out = '<button class="theme" id="thm" title="Color theme"></button><a class="home" href="' + root + 'index.html">All regressions</a>' +
            '<input id="flt" placeholder="Filter regressions"><div id="runs">';
  runs.forEach(function (r) {
    out += '<a class="run' + (r.id === cur && !curT ? ' cur' : '') + '" data-id="' + h(r.id) + '" href="' + root + r.id +
      '/index.html" title="' + h(r.argv) + '"><span class="dot d-' + r.status + '"></span>' + h(r.id) + '</a>';
    if (r.id === cur) r.targets.forEach(function (t) {
      out += '<a class="run tgt' + (t.name === curT ? ' cur' : '') + '" data-id="' + h(r.id) + '" href="' + root + r.id + '/' +
        h(t.name) + '/index.html"><span class="dot d-' + t.status + '"></span>' + h(t.name) + '</a>';
    });
  });
  var staticSide = side.dataset.static;
  if (staticSide) side.insertAdjacentHTML('afterbegin', '<button class="theme" id="thm" title="Color theme"></button>');
  else side.innerHTML = out + '</div>';
  document.getElementById('navtoggle').addEventListener('click', function () {
    var off = document.documentElement.classList.toggle('nav-off');
    try { if (off) localStorage.setItem('nav', 'off'); else localStorage.removeItem('nav'); } catch (e) {}
  });
  var modes = ['auto', 'light', 'dark'], btn = document.getElementById('thm');
  function mode() { try { return localStorage.getItem('theme') || 'auto'; } catch (e) { return 'auto'; } }
  function show() { btn.textContent = {auto: '◐ Auto', light: '☀ Light', dark: '☾ Dark'}[mode()]; }
  btn.addEventListener('click', function () {
    var m = modes[(modes.indexOf(mode()) + 1) % 3], el = document.documentElement;
    try { if (m === 'auto') localStorage.removeItem('theme'); else localStorage.setItem('theme', m); } catch (e) {}
    if (m === 'auto') delete el.dataset.theme; else el.dataset.theme = m;
    show();
  });
  show();
  var cs = side.querySelector('.cur'); if (cs) { var box = document.getElementById('runs'); box.scrollTop = Math.max(0, cs.offsetTop - box.offsetTop - box.clientHeight / 2); }
  if (!staticSide) document.getElementById('flt').addEventListener('input', function (e) {
    var q = e.target.value.toLowerCase();
    side.querySelectorAll('.run').forEach(function (a) {
      a.style.display = a.dataset.id.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
    });
  });
})();
// Sortable tables: click a header to sort by the cells' data-v (numbers or text), else their text.
document.querySelectorAll('table.sortable').forEach(function (t) {
  var head = t.rows[0], body = Array.prototype.slice.call(t.rows, 1);
  function val(tr, i) {
    var c = tr.cells[i], v = c.dataset.v !== undefined ? c.dataset.v : c.textContent.trim();
    return v !== '' && !isNaN(v) ? parseFloat(v) : v.toLowerCase();
  }
  Array.prototype.forEach.call(head.cells, function (th, i) {
    th.addEventListener('click', function () {
      var dir = th.classList.contains('asc') ? -1 : 1;
      Array.prototype.forEach.call(head.cells, function (o) { o.classList.remove('asc', 'desc'); });
      th.classList.add(dir === 1 ? 'asc' : 'desc');
      body.slice().sort(function (a, b) {
        var x = val(a, i), y = val(b, i);
        return (x < y ? -1 : x > y ? 1 : 0) * dir;
      }).forEach(function (tr) { t.tBodies[0].appendChild(tr); });
    });
  });
});
// Target filter: matches target name or toplevel.
(function () {
  var f = document.getElementById('tflt'); if (!f) return;
  var rows = document.querySelectorAll('table.sortable tr[data-name]'), none = document.getElementById('tnone');
  f.addEventListener('input', function () {
    var q = f.value.toLowerCase(), n = 0;
    rows.forEach(function (tr) {
      var show = tr.dataset.name.toLowerCase().indexOf(q) >= 0;
      tr.style.display = show ? '' : 'none'; if (show) n++;
    });
    none.hidden = n > 0;
  });
})();
// Copy buttons: data-copy holds the text. Clipboard API, with a textarea fallback.
document.addEventListener('click', function (e) {
  var b = e.target.closest && e.target.closest('button.copy'); if (!b) return;
  var text = b.dataset.copy, old = b.innerHTML;
  function ok() {
    b.classList.add('done'); b.innerHTML = '__CHECK__';
    setTimeout(function () { b.classList.remove('done'); b.innerHTML = old; }, 1500);
  }
  function fallback() {
    var ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { if (document.execCommand('copy')) ok(); } catch (err) {}
    document.body.removeChild(ta);
  }
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(ok, fallback);
  else fallback();
});
