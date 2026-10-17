// NFS SE Enhanced - browser patcher. Same flow and look as the command-line patcher; the Python code
// runs unchanged in Pyodide web workers (worker.js + webpatch.py).
'use strict';
const T = document.getElementById('term');
const BASE = new URL('../', location.href);          // repository layout: patcher.py, nfsse/, web/
const DEV = new URLSearchParams(location.search).get('dev');   // test mode: read the game from this URL
const REPO = 'https://github.com/sebauer/nfsse-enhanced';
const COFFEE = 'https://buymeacoffee.com/sebauer';
const MAX_WORKERS = 4;

// ---------- terminal output ----------
// follow new output like a terminal while the view is at the bottom; scrolling up stops following
let follow = true;
addEventListener('scroll', () => { follow = innerHeight + scrollY >= document.documentElement.scrollHeight - 40; }, { passive: true });
new MutationObserver(() => { if (follow) scrollTo(0, document.documentElement.scrollHeight); })
  .observe(T, { childList: true, subtree: true, characterData: true });

function span(cls, text) { const s = document.createElement('span'); s.className = cls; s.textContent = text; return s; }
function line(...parts) {
  const d = document.createElement('div'); d.className = 'line';
  for (const p of parts) d.append(Array.isArray(p) ? span(p[0], p[1]) : p);
  T.append(d); return d;
}
const blank = () => line('');
const head = t => line(['blue bold', '==>'], ' ', ['bold', t]);
const info = (k, v) => line('    ' + k.padEnd(13) + v);
const ok = t => line(['green bold', '✔'], ' ', t);
const warn = t => line(['yellow bold', '!'], ' ', t);
const fail = t => line(['red bold', 'Error:'], ' ', t);
const clock = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
function link(href, text) { const a = document.createElement('a'); a.href = href; a.textContent = text || href; a.target = '_blank'; a.rel = 'noopener'; return a; }
function button(text, onclick) {
  const b = document.createElement('button'); b.className = 'cmd'; b.textContent = text; b.onclick = onclick; return b;
}

async function logo(sub) {
  // the logo lives in nfsse/ui.py (rows 0-3 THE NEED, 4-7 FOR SPEED + SE from column 41, 8 SPECIAL EDITION, 9-12 ENHANCED)
  try {
    const src = await (await fetch(new URL('nfsse/ui.py', BASE))).text();
    const rows = src.match(/LOGO=r"""\n([\s\S]*?)"""/)[1].split('\n');
    const pre = document.createElement('div'); pre.className = 'logo';
    rows.forEach((l, i) => {
      const d = document.createElement('div');
      if (i < 8) d.append(span(i < 4 ? 'red bold' : 'yellow bold', l.slice(0, 41)), span('white bold', l.slice(41)));
      else d.append(span(i === 8 ? '' : 'cyan bold', l));
      pre.append(d);
    });
    T.append(pre); blank(); line(['dim', sub]);
  } catch { head('NFS SE Enhanced'); line('    ' + sub); }
}

// ---------- numbered menus (click, or press the number; Enter takes the default) ----------
function choose(title, options, def) {
  return new Promise(resolve => {
    line('  ', ['bold', title]);
    const menu = document.createElement('div'); menu.className = 'menu'; T.append(menu);
    const opts = options.map(([value, label], k) => {
      const d = document.createElement('div'); d.className = 'line opt'; d.tabIndex = 0;
      d.append('    ', span('num', String(k + 1)), ') ' + label + (k + 1 === def ? '  ' : ''));
      if (k + 1 === def) d.append(span('dim', '(default)'));
      d.onclick = () => pick(k);
      d.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(k); } };
      menu.append(d); return d;
    });
    function key(e) {
      if (e.target.closest && e.target.closest('.opt')) return;   // handled by the focused option
      const n = parseInt(e.key, 10);
      if (n >= 1 && n <= options.length) pick(n - 1);
      else if (e.key === 'Enter') pick(def - 1);
    }
    function pick(k) {
      document.removeEventListener('keydown', key);
      menu.classList.add('closed'); opts[k].classList.add('chosen');
      opts.forEach(o => { o.tabIndex = -1; o.onclick = o.onkeydown = null; });
      opts[k].prepend(span('green', '✔')); opts[k].firstChild.nextSibling.textContent = '   ';
      blank(); resolve(options[k][0]);
    }
    document.addEventListener('keydown', key);
    opts[def - 1].focus({ preventScroll: true });
  });
}

// ---------- game folder access ----------
// A source reads files by their path in the game folder (case-insensitive, like DOS) and, if it can,
// writes the new files back. 'fsa': File System Access API (Chrome, Edge) writes in place;
// 'upload': a folder chosen with <input webkitdirectory>, results as a zip; 'dev': files from a URL.
const split = p => { const i = p.lastIndexOf('/'); return [i < 0 ? '' : p.slice(0, i), p.slice(i + 1)]; };

function fsaSource(root) {
  const cache = new Map();   // lower-case dir path -> Map(lower-case name -> handle), with .dir = its handle
  async function list(dir) {
    const key = dir.toLowerCase();
    if (cache.has(key)) return cache.get(key);
    let h = root;
    if (dir) {
      const [parent, name] = split(dir); const m = await list(parent);
      const e = m && m.get(name.toLowerCase());
      if (!e || e.kind !== 'directory') { cache.set(key, null); return null; }
      h = e;
    }
    const m = new Map(); m.dir = h;
    for await (const [name, handle] of h.entries()) m.set(name.toLowerCase(), handle);
    cache.set(key, m); return m;
  }
  return {
    kind: 'fsa', name: root.name,
    async read(path) {
      const [d, n] = split(path); const m = await list(d); const h = m && m.get(n.toLowerCase());
      return h && h.kind === 'file' ? (await h.getFile()).arrayBuffer() : null;
    },
    async isDir(path) { return !!(await list(path)); },
    async exists(path) { const [d, n] = split(path); const m = await list(d); return !!(m && m.get(n.toLowerCase())); },
    async write(path, data) {
      const [d, n] = split(path); let cur = '';
      for (const part of d.split('/').filter(Boolean)) {   // create missing folders (normally they all exist)
        const m = await list(cur); const next = cur ? cur + '/' + part : part;
        if (!m.get(part.toLowerCase())) { m.set(part.toLowerCase(), await m.dir.getDirectoryHandle(part, { create: true })); cache.delete(next.toLowerCase()); }
        cur = next;
      }
      const m = await list(d);
      const fh = m.get(n.toLowerCase()) || await m.dir.getFileHandle(n, { create: true });
      m.set(n.toLowerCase(), fh);
      const w = await fh.createWritable(); await w.write(data); await w.close();
    },
  };
}

function uploadSource(fileList) {
  const files = new Map(); let name = '';
  for (const f of fileList) {
    const parts = f.webkitRelativePath.split('/'); name = parts[0];
    files.set(parts.slice(1).join('/').toLowerCase(), f);
  }
  const out = {};
  return {
    kind: 'upload', name, out,
    async read(path) { const f = files.get(path.toLowerCase()); return f ? f.arrayBuffer() : null; },
    async isDir(path) { const p = path.toLowerCase() + '/'; for (const k of files.keys()) if (k.startsWith(p)) return true; return false; },
    async exists() { return false; },
    async write(path, data) { out[path] = new Uint8Array(data); },
  };
}

function devSource(base) {
  const got = new Set(); const hashes = {};
  return {
    kind: 'dev', name: base, hashes,
    async read(path) { const r = await fetch(new URL(path, new URL(base, location.href))); if (!r.ok) return null; got.add(path.toLowerCase()); return r.arrayBuffer(); },
    async isDir(path) { const p = path.toLowerCase() + '/'; for (const k of got) if (k.startsWith(p)) return true; return false; },
    async exists() { return false; },
    async write(path, data) {
      const h = new Uint8Array(await crypto.subtle.digest('SHA-256', data));
      hashes[path] = Array.from(h, b => b.toString(16).padStart(2, '0')).join('');
    },
  };
}

function pickFolder() {
  return new Promise(resolve => {
    if (DEV) { resolve(devSource(DEV)); return; }
    const row = line('    ');
    if (window.showDirectoryPicker) {
      row.append(button('Select game folder', async () => {
        try { const h = await showDirectoryPicker({ id: 'nfsse', mode: 'readwrite' }); row.querySelector('button').disabled = true; resolve(fsaSource(h)); }
        catch (e) { if (e.name !== 'AbortError') fail(e.message); }
      }));
      line(['dim', '    The new files are written straight into the game folder; the originals stay untouched.']);
    } else {
      const input = document.createElement('input'); input.type = 'file'; input.webkitdirectory = true;
      input.onchange = () => { if (input.files.length) { row.querySelector('button').disabled = true; resolve(uploadSource(input.files)); } };
      row.append(button('Select game folder', () => input.click()), input);
      line(['dim', '    Your browser cannot write into folders: you will get the new files as a zip to unpack']);
      line(['dim', '    into the game folder. (Chrome or Edge can patch the folder directly.)']);
    }
  });
}

// ---------- Python workers ----------
class PyWorker {
  constructor() {
    this.w = new Worker('worker.js'); this.n = 0; this.calls = new Map();
    this.w.onmessage = e => {
      const m = e.data, c = this.calls.get(m.id);
      if (!c) return;
      if (m.type === 'result') { this.calls.delete(m.id); c.resolve(m.result); }
      else if (m.type === 'error') { this.calls.delete(m.id); c.reject(new Error(m.message)); }
      else if (c.onEvent) c.onEvent(m);
    };
    this.w.onerror = e => { for (const c of this.calls.values()) c.reject(new Error(e.message || 'worker failed')); this.calls.clear(); };
  }
  call(type, data = {}, onEvent) {
    const id = ++this.n;
    return new Promise((resolve, reject) => { this.calls.set(id, { resolve, reject, onEvent }); this.w.postMessage({ id, type, ...data }); });
  }
  terminate() { this.w.terminate(); }
}

async function readGame(src, cand) {
  const files = [];
  for (const path of cand.files) {
    const data = await src.read(path);
    if (data) files.push({ path, data });
  }
  const dirs = [];
  for (const d of cand.dirs) if (await src.isDir(d)) dirs.push(d);
  return { files, dirs };
}

// ---------- progress block (bar at the bottom, running jobs above it) ----------
function progress(plan) {
  const total = plan.reduce((n, j) => n + j.files.length, 0), wl = Math.max(...plan.map(j => j.label.length));
  const block = document.createElement('div'); T.append(block);
  const running = new Map(); const t0 = performance.now(); let done = 0, tick = 0;
  const SPIN = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏';
  function draw() {
    tick++; block.replaceChildren();
    const now = performance.now(); let k = 0;
    for (const [i, t] of running) {
      const d = document.createElement('div'); d.className = 'line';
      d.append('  ', span('spin', SPIN[(tick + k++) % SPIN.length]), ' ' + plan[i].label.padEnd(wl) + '  ', span('dim', ((now - t) / 1000).toFixed(1).padStart(5) + 's'));
      block.append(d);
    }
    const bw = 40, f = Math.round(bw * done / total), d = document.createElement('div'); d.className = 'line';
    d.append('  ', span('green', '█'.repeat(f)), span('dim', '░'.repeat(bw - f)), ` ${String(done).padStart(String(total).length)}/${total} files  ${clock((now - t0) / 1000)}`);
    block.append(d);
  }
  const timer = setInterval(draw, 100); draw();
  return {
    total,
    start(i) { running.set(i, performance.now()); draw(); },
    finish(i, dt) {
      running.delete(i); done += plan[i].files.length;
      const d = document.createElement('div'); d.className = 'line';
      d.append('  ', span('green', '✔'), ' ' + plan[i].label.padEnd(wl) + '  ', span('dim', dt.toFixed(1).padStart(5) + 's'));
      block.before(d); draw();
    },
    end() { clearInterval(timer); block.remove(); return (performance.now() - t0) / 1000; },
  };
}

// ---------- main flow ----------
async function main() {
  await logo('v0.9 - hi-res patch for Need for Speed SE (DOS), in your browser');
  blank();
  if (!window.Worker || !window.WebAssembly) { fail('This browser cannot run the patcher (needs WebAssembly and web workers).'); return; }

  head('Getting ready');
  const status = line('    Loading Python and the patcher (the first visit downloads about 40 MB) ...');
  const first = new PyWorker();
  const ready = first.call('init', { base: BASE.href }).then(c => { status.textContent = '    Python is ready.'; return c; });
  ready.catch(e => { status.textContent = ''; fail('Could not load Python: ' + e.message); });

  blank(); head('Choose your game folder');
  line('  Select the folder the game is installed in (the one with NFS.EXE).');
  const src = await pickFolder();
  const cand = await ready.catch(() => null);   // the error is already shown
  if (!cand) return;

  blank(); head('Checking your installation');
  line('    Verifying installation ...');
  const game = await readGame(src, cand);
  await first.call('files', game);
  const chk = await first.call('check');
  if (!chk.ok) { fail(chk.error); line('    Fix this and reload the page to try again.'); return; }
  info('Game folder', src.name);
  info('NFS.EXE', chk.variant);
  info('Language', `${chk.language} (NFS.CFG); generating for: ${chk.langs.join(', ')}`);
  ok('Game installation verified');

  blank(); head('Build options');
  const res = await choose('Resolution', [[[1024], '1024x768'], [[1280], '1280x960   (DOSBox-X: memsize = 64 and VESA settings, shown at the end)'], [[1024, 1280], 'both (recommended)']], 3);
  const steer = await choose('Keyboard steering (joystick/wheel are not affected)', [[1, 'original'], [2, '2x faster (recommended)'],
    [3, '3x faster (not recommended: scrubs off too much speed in corners)'], [4, '4x faster (not recommended: scrubs off too much speed in corners)']], 2);
  const view = await choose('View distance, car visibility and traffic', [['extended', 'extended (recommended)'], ['original', 'original']], 1);

  const plan = await first.call('plan', { res, steer, view });
  const total = plan.reduce((n, j) => n + j.files.length, 0);
  let existing = 0;
  for (const j of plan) for (const f of j.files) if (await src.exists(f)) existing++;
  if (existing) warn(`${existing} of the ${total} patch files already exist (earlier run) and will be replaced.`);
  await new Promise(resolve => { const row = line('  '); row.append(button(existing ? 'Replace them and start patching' : 'Start patching', () => { row.querySelector('button').disabled = true; resolve(); })); row.querySelector('button').focus(); });

  // workers: the first one is ready; the others load in the background and join when ready
  const nworkers = Math.max(1, Math.min(MAX_WORKERS, Math.floor((navigator.hardwareConcurrency || 2) / 2), plan.length));
  blank(); head(`Building ${res.map(r => r === 1024 ? '1024x768' : '1280x960').join(' and ')} (${total} files, ${nworkers} parallel worker${nworkers > 1 ? 's' : ''})`);
  info('Options', `keyboard steering x${steer}, view ${view}`);
  const guard = e => { e.preventDefault(); e.returnValue = ''; };
  window.addEventListener('beforeunload', guard);
  const pr = progress(plan);
  const queue = plan.map((_, i) => i), writes = [];
  async function work(w) {
    while (queue.length) {
      const i = queue.shift();
      await w.call('run', { jobs: [i] }, m => {
        if (m.type === 'start') pr.start(m.i);
        else if (m.type === 'done') writes.push((async () => {
          for (const f of m.files) await src.write(f.path, f.data);
          pr.finish(m.i, m.dt);
        })());
      });
    }
  }
  async function extra() {
    const w = new PyWorker();
    try {   // a worker that cannot start (e.g. not enough memory) just does not help
      await w.call('init', { base: BASE.href }); await w.call('files', game); await w.call('check'); await w.call('plan', { res, steer, view });
    } catch (e) { console.warn('extra worker not available:', e); w.terminate(); return; }
    try { await work(w); } finally { w.terminate(); }
  }
  try {
    await Promise.all([work(first), ...Array.from({ length: nworkers - 1 }, extra)]);
    await Promise.all(writes);
  } catch (e) {
    pr.end(); window.removeEventListener('beforeunload', guard);
    fail(e.message); line('    Please report this: ', link(REPO + '/issues')); return;
  }
  const secs = pr.end();
  window.removeEventListener('beforeunload', guard);

  if (src.kind === 'fsa') ok(`${total} files written in ${clock(secs)}, original files unchanged`);
  else if (src.kind === 'upload') {
    ok(`${total} files generated in ${clock(secs)}`);
    const zip = fflate.zipSync(src.out, { level: 6 });
    const url = URL.createObjectURL(new Blob([zip], { type: 'application/zip' }));
    const a = link(url, 'nfsse-enhanced-files.zip'); a.download = 'nfsse-enhanced-files.zip'; a.removeAttribute('target');
    line('    Download ', a, ` (${(zip.length / 1e6).toFixed(0)} MB) and unpack it into the game folder ${src.name},`);
    line('    merging the folders. Your original files stay untouched.');
  } else {
    ok(`${total} files generated in ${clock(secs)} (test mode, nothing written)`);
    window.devHashes = src.hashes; console.log('NFSSE_HASHES ' + JSON.stringify(src.hashes));
  }

  blank(); line(['green bold', "  Success! Your game is patched. Start your engines - let's race!"]); blank();
  const notes = await first.call('notes', { res });
  for (const l of notes.trimEnd().split('\n')) {
    if (l.startsWith('==> ')) { if (T.lastChild.textContent !== '') blank(); head(l.slice(4)); }
    else line(l.startsWith('    Tested') ? ['dim', l] : l);
  }
  blank();
  line('  Questions, problems or feedback? Visit ', link(REPO));
  line('  ☕ Enjoying the patch? Buy me a coffee: ', link(COFFEE), '  ', ['dim', '(entirely optional)']);
  first.terminate();
}

main().catch(e => { fail(e.message); console.error(e); });
