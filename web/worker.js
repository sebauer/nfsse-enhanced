// Web worker: runs the Python patcher in Pyodide. Messages from the page:
//   {type:'init', base}              load Pyodide, numpy/scipy/Pillow and the patcher sources
//   {type:'files', files, dirs}      copy game files [{path, data}] into the in-memory game folder
//   {type:'check'}                   verify the installation
//   {type:'plan', res, steer, view}  build the job list
//   {type:'run', jobs}               run jobs (indices into the plan); posts 'start' and 'done' (with files)
// Every reply carries the request id; errors come back as {type:'error', message}.
const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.29.3/full/';
importScripts(PYODIDE + 'pyodide.js');

const SOURCES = ['patcher.py', 'web/webpatch.py'].concat(
  ['cockpit', 'exe', 'ffn', 'fsh', 'hud', 'huff', 'layout', 'le', 'masks', 'qfs', 'stackfix',
   'tickets', 'title', 'ui', 'version'].map(m => `nfsse/${m}.py`));

let py, api, plan;

function mkdirs(path) {
  let cur = '';
  for (const part of path.split('/').filter(Boolean)) {
    cur += '/' + part;
    if (!py.FS.analyzePath(cur).exists) py.FS.mkdir(cur);
  }
}

const handlers = {
  async init({ base }) {
    py = await loadPyodide({ indexURL: PYODIDE });
    await py.loadPackage(['numpy', 'scipy', 'pillow']);
    for (const src of SOURCES) {
      const r = await fetch(new URL(src, base));
      if (!r.ok) throw new Error(`cannot load ${src} (${r.status})`);
      const dst = src.startsWith('web/') ? '/py/' + src.slice(4) : '/py/' + src;
      mkdirs(dst.slice(0, dst.lastIndexOf('/')));
      py.FS.writeFile(dst, new Uint8Array(await r.arrayBuffer()));
    }
    mkdirs('/game'); mkdirs('/out');
    py.runPython("import sys; sys.path.insert(0, '/py')");
    api = py.pyimport('webpatch');
    return api.candidates().toJs({ dict_converter: Object.fromEntries });
  },
  files({ files, dirs }) {
    for (const d of dirs) mkdirs('/game/' + d);
    for (const f of files) {
      if (f.path.includes('/')) mkdirs('/game/' + f.path.slice(0, f.path.lastIndexOf('/')));
      py.FS.writeFile('/game/' + f.path, new Uint8Array(f.data));
    }
    return files.length;
  },
  check() { return api.check().toJs({ dict_converter: Object.fromEntries }); },
  notes({ res }) { return api.notes(py.toPy(res)); },
  plan({ res, steer, view }) {
    plan = api.plan(py.toPy(res), steer, view).toJs({ dict_converter: Object.fromEntries });
    return plan;
  },
  run({ jobs }, id) {
    for (const i of jobs) {
      postMessage({ id, type: 'start', i });
      const dt = api.run(i);
      const files = plan[i].files.map(p => {
        const data = py.FS.readFile('/out/' + p);
        py.FS.unlink('/out/' + p);   // free the memory, the page owns the file now
        return { path: p, data: data.buffer };
      });
      postMessage({ id, type: 'done', i, dt, files }, files.map(f => f.data));
    }
    return jobs.length;
  },
};

onmessage = async (e) => {
  const { id, type } = e.data;
  try {
    const result = await handlers[type](e.data, id);
    postMessage({ id, type: 'result', result });
  } catch (err) {
    postMessage({ id, type: 'error', message: String(err.message || err) });
  }
};
