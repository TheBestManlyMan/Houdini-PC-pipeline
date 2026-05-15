/* global React, ReactDOM */
const { useState, useEffect, useCallback, useRef, useMemo } = React;

// ───────────────────────── icons (shared vocabulary w/ the gallery) ──────────────────────────
const PMIcon = ({ name, size = 14 }) => {
  const s = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' };
  const paths = {
    plus:     <><path d="M8 3v10M3 8h10" {...s}/></>,
    close:    <path d="M3 3l10 10M13 3L3 13" {...s}/>,
    chev:     <path d="M5 3l5 5-5 5" {...s}/>,
    chevD:    <path d="M3 5l5 5 5-5" {...s}/>,
    folder:   <path d="M2 5a1 1 0 011-1h3l2 2h5a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1z" {...s}/>,
    shot:     <><rect x="2" y="4" width="9" height="8" {...s}/><path d="M11 6l3-2v8l-3-2z" {...s}/></>,
    asset:    <><path d="M8 2l5 3v6l-5 3-5-3V5z" {...s}/><path d="M3 5l5 3 5-3M8 8v6" {...s}/></>,
    layer:    <><path d="M8 2l6 3-6 3-6-3z" {...s}/><path d="M2 8l6 3 6-3M2 11l6 3 6-3" {...s}/></>,
    trash:    <><path d="M3 4h10M6 4V3a1 1 0 011-1h2a1 1 0 011 1v1M5 4l1 9a1 1 0 001 1h2a1 1 0 001-1l1-9" {...s}/></>,
    refresh:  <><path d="M13 8a5 5 0 11-1.5-3.5L13 6" {...s}/><path d="M13 3v3h-3" {...s}/></>,
    gallery:  <><rect x="2" y="2" width="5" height="5" {...s}/><rect x="9" y="2" width="5" height="5" {...s}/><rect x="2" y="9" width="5" height="5" {...s}/><rect x="9" y="9" width="5" height="5" {...s}/></>,
    settings: <><circle cx="8" cy="8" r="6" {...s}/><path d="M8 2v2M8 12v2M2 8h2M12 8h2" {...s}/></>,
    check:    <path d="M3 8l3 3 7-7" {...s}/>,
  };
  return <svg width={size} height={size} viewBox="0 0 16 16" style={{ display: 'block', flexShrink: 0 }}>{paths[name]}</svg>;
};

// ───────────────────────── api client (with demo fallback) ──────────────────────────
const fetchTimeout = (url, opts = {}, ms = 2500) => {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  return fetch(url, { ...opts, signal: ctrl.signal }).finally(() => clearTimeout(t));
};

const resolveApiBase = () => {
  const params = new URLSearchParams(location.search);
  const explicit = params.get('api');
  const saved = localStorage.getItem('pm-api-base');
  return (explicit || saved || 'http://127.0.0.1:8765/api').replace(/\/+$/, '');
};

const isMockForced = () => new URLSearchParams(location.search).get('mock') === '1';

// Single object encapsulates either live REST calls or in-memory mock ops.
const makeClient = (mode, apiBase) => {
  if (mode === 'mock') {
    const M = window.PIPELINE_MOCK;
    const sleep = (ms = 80) => new Promise(r => setTimeout(r, ms));
    return {
      listProjects:     async ()           => (await sleep(), M.listProjects()),
      createProject:    async (body)       => (await sleep(), M.createProject(body)),
      deleteProject:    async (f)          => (await sleep(), M.deleteProject(f)),
      listSequences:    async (f)          => (await sleep(), M.listSequences(f)),
      createSequence:   async (f, seq)     => (await sleep(), M.createSequence(f, seq)),
      deleteSequence:   async (f, seq)     => (await sleep(), M.deleteSequence(f, seq)),
      listShots:        async (f, s)       => (await sleep(), M.listShots(f, s)),
      createShot:       async (f, s, sh)   => (await sleep(), M.createShot(f, s, sh)),
      deleteShot:       async (f, s, sh)   => (await sleep(), M.deleteShot(f, s, sh)),
      listAssets:       async (f)          => (await sleep(), M.listAssets(f)),
      createAssetType:  async (f, t)       => (await sleep(), M.createAssetType(f, t)),
      deleteAssetType:  async (f, t)       => (await sleep(), M.deleteAssetType(f, t)),
      createAsset:      async (f, t, a)    => (await sleep(), M.createAsset(f, t, a)),
      deleteAsset:      async (f, t, a)    => (await sleep(), M.deleteAsset(f, t, a)),
      publishCount:     async (f)          => (await sleep(), M.publishCount(f)),
    };
  }

  // Live FastAPI client
  const req = async (method, path, body) => {
    const r = await fetchTimeout(apiBase + path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    }, method === 'GET' ? 4000 : 15000);
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(err.detail || r.statusText);
    }
    return r.status === 204 ? null : r.json();
  };
  const qs = (obj) => Object.keys(obj || {}).length ? '?' + new URLSearchParams(obj) : '';

  return {
    listProjects:     ()                => req('GET',    `/projects`),
    createProject:    (body)            => req('POST',   `/projects`, body),
    deleteProject:    (f, del)          => req('DELETE', `/projects/${f}${qs(del ? { delete_files: true } : {})}`),
    listSequences:    (f)               => req('GET',    `/projects/${f}/sequences`),
    createSequence:   (f, seq)          => req('POST',   `/projects/${f}/sequences`, { seq }),
    deleteSequence:   (f, seq, del)     => req('DELETE', `/projects/${f}/sequences/${seq}${qs(del ? { delete_files: true } : {})}`),
    listShots:        (f, s)            => req('GET',    `/projects/${f}/sequences/${s}/shots`),
    createShot:       (f, s, shot)      => req('POST',   `/projects/${f}/sequences/${s}/shots`, { shot }),
    deleteShot:       (f, s, sh, del)   => req('DELETE', `/projects/${f}/sequences/${s}/shots/${sh}${qs(del ? { delete_files: true } : {})}`),
    listAssets:       (f)               => req('GET',    `/projects/${f}/assets`),
    createAssetType:  (f, asset_type)   => req('POST',   `/projects/${f}/asset-types`, { asset_type }),
    deleteAssetType:  (f, t, del)       => req('DELETE', `/projects/${f}/asset-types/${t}${qs(del ? { delete_files: true } : {})}`),
    createAsset:      (f, t, asset)     => req('POST',   `/projects/${f}/assets/${t}`, { asset }),
    deleteAsset:      (f, t, a, del)    => req('DELETE', `/projects/${f}/assets/${t}/${a}${qs(del ? { delete_files: true } : {})}`),
    publishCount:     async (f) => {
      try {
        const projects = await req('GET', `/projects`);
        const proj = projects.find(p => p.folder === f);
        const pubs = await req('GET', `/publishes${qs(proj ? { project: proj.name } : {})}`);
        return pubs.length;
      } catch { return 0; }
    },
  };
};

// ───────────────────────── toast ──────────────────────────
let _addToast = null;
const toast  = (m) => _addToast?.(m, 'ok');
const toastE = (m) => _addToast?.(m, 'err');

function Toaster() {
  const [items, setItems] = useState([]);
  _addToast = (msg, kind = 'ok') => {
    const id = Math.random().toString(36).slice(2);
    setItems(t => [...t, { id, msg, kind }]);
    setTimeout(() => setItems(t => t.filter(x => x.id !== id)), 3200);
  };
  return (
    <div className="pm-toasts">
      {items.map(t => (
        <div key={t.id} className={`pm-toast pm-toast-${t.kind}`}>{t.msg}</div>
      ))}
    </div>
  );
}

// ───────────────────────── confirm dialog hook ──────────────────────────
function useConfirm() {
  const [state, setState] = useState(null);
  const confirm = useCallback((opts) => new Promise(resolve => setState({ ...opts, resolve })), []);
  const node = state ? (
    <ConfirmDialog
      {...state}
      onCancel={() => { state.resolve({ confirmed: false }); setState(null); }}
      onConfirm={(deleteFiles) => { state.resolve({ confirmed: true, deleteFiles }); setState(null); }}
    />
  ) : null;
  return [confirm, node];
}

function ConfirmDialog({ title, body, danger = true, showDeleteFiles = true, onConfirm, onCancel }) {
  const [del, setDel] = useState(false);
  useEffect(() => {
    const k = (e) => { if (e.key === 'Escape') onCancel(); if (e.key === 'Enter') onConfirm(del); };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [del, onCancel, onConfirm]);
  return (
    <div className="pm-overlay" onClick={onCancel}>
      <div className="pm-dialog" onClick={e => e.stopPropagation()}>
        <div className="pm-dialog-title">{title}</div>
        <div className="pm-dialog-body">{body}</div>
        {showDeleteFiles && (
          <label className="pm-dialog-check">
            <input type="checkbox" checked={del} onChange={e => setDel(e.target.checked)}/>
            Also delete files from disk
          </label>
        )}
        <div className="pm-dialog-actions">
          <button className="pm-btn pm-btn-ghost" onClick={onCancel}>Cancel</button>
          <button className={`pm-btn ${danger ? 'pm-btn-danger' : 'pm-btn-primary'}`}
                  onClick={() => onConfirm(del)}>
            {danger ? 'Delete' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ───────────────────────── new project dialog ──────────────────────────
function NewProjectDialog({ onSubmit, onCancel }) {
  const [name, setName] = useState('');
  const [fps, setFps] = useState('24');
  const [res, setRes] = useState('1920x1080');
  const ref = useRef(null);
  useEffect(() => ref.current?.focus(), []);

  const slug = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  const submit = () => {
    if (!name.trim()) { toastE('Project name is required.'); return; }
    onSubmit({ name: name.trim(), folder: slug, fps: parseInt(fps) || 24, resolution: res || '1920x1080' });
  };
  const onKey = (e) => {
    if (e.key === 'Escape') onCancel();
    if (e.key === 'Enter' && e.metaKey) submit();
  };

  return (
    <div className="pm-overlay" onClick={onCancel} onKeyDown={onKey}>
      <div className="pm-dialog" onClick={e => e.stopPropagation()}>
        <div className="pm-dialog-title">New project</div>
        <div className="pm-dialog-form">
          <input ref={ref} className="pm-field" placeholder="Project name"
                 value={name} onChange={e => setName(e.target.value)}
                 onKeyDown={e => e.key === 'Enter' && submit()}/>
          <div className="pm-dialog-meta">folder: {slug || '—'}</div>
          <div className="pm-dialog-row">
            <input className="pm-field pm-field-mono" placeholder="FPS" style={{ maxWidth: 90 }}
                   value={fps} onChange={e => setFps(e.target.value)}/>
            <input className="pm-field pm-field-mono" placeholder="Resolution"
                   value={res} onChange={e => setRes(e.target.value)}/>
          </div>
        </div>
        <div className="pm-dialog-actions">
          <button className="pm-btn pm-btn-ghost" onClick={onCancel}>Cancel</button>
          <button className="pm-btn pm-btn-primary" onClick={submit}>Create project</button>
        </div>
      </div>
    </div>
  );
}

// ───────────────────────── inline form (single field) ──────────────────────────
function InlineForm({ placeholder, onSubmit, onCancel, mono = false, compact = false }) {
  const [val, setVal] = useState('');
  const ref = useRef(null);
  useEffect(() => ref.current?.focus(), []);
  const submit = () => {
    if (!val.trim()) { toastE(`${placeholder} is required.`); return; }
    onSubmit(val.trim());
  };
  return (
    <div className={`pm-inline-form ${compact ? 'compact' : ''}`}>
      <input ref={ref}
             className={`pm-field ${mono ? 'pm-field-mono' : ''}`}
             placeholder={placeholder}
             value={val}
             onChange={e => setVal(e.target.value)}
             onKeyDown={e => {
               if (e.key === 'Enter') submit();
               if (e.key === 'Escape') onCancel();
             }}/>
      <button className="pm-btn pm-btn-primary" onClick={submit}>Add</button>
      <button className="pm-btn pm-btn-icon" onClick={onCancel} title="Cancel">
        <PMIcon name="close" size={12}/>
      </button>
    </div>
  );
}

// ───────────────────────── projects sidebar ──────────────────────────
function ProjectsSidebar({ projects, activeFolder, onSelect, onNew, onDelete }) {
  return (
    <aside className="pm-sidebar">
      <div className="pm-side-head">
        Projects
        <button className="pm-side-add" onClick={onNew}>
          <PMIcon name="plus" size={11}/> New
        </button>
      </div>
      <div className="pm-side-list">
        {projects.length === 0 && (
          <div className="pm-side-empty">
            No projects yet.<br/>
            <span style={{ color: 'var(--text-5)' }}>Click <strong>+ New</strong> above.</span>
          </div>
        )}
        {projects.map(p => (
          <div key={p.folder}
               className={`pm-proj ${activeFolder === p.folder ? 'active' : ''}`}
               onClick={() => onSelect(p.folder)}>
            <span className="pm-proj-swatch"/>
            <div className="pm-proj-body">
              <div className="pm-proj-name">{p.name}</div>
              <div className="pm-proj-meta">{p.folder}</div>
            </div>
            <button className="pm-proj-del" onClick={e => { e.stopPropagation(); onDelete(p); }}
                    title="Delete project">
              <PMIcon name="trash" size={12}/>
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}

// ───────────────────────── overview tab ──────────────────────────
function OverviewTab({ client, project }) {
  const [stats, setStats] = useState({ sequences: 0, shots: 0, assets: 0, publishes: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let dead = false;
    setLoading(true);
    (async () => {
      try {
        const seqs = await client.listSequences(project.folder);
        const assetsMap = await client.listAssets(project.folder);
        const pubCount = await client.publishCount(project.folder);
        let shotTotal = 0;
        for (const seq of seqs) {
          const shots = await client.listShots(project.folder, seq);
          shotTotal += shots.length;
        }
        const assetTotal = Object.values(assetsMap).reduce((s, a) => s + a.length, 0);
        if (!dead) setStats({ sequences: seqs.length, shots: shotTotal, assets: assetTotal, publishes: pubCount });
      } catch (e) { /* swallow; partials are fine in demo mode */ }
      finally     { if (!dead) setLoading(false); }
    })();
    return () => { dead = true; };
  }, [project.folder, client]);

  return (
    <div className="pm-panel">
      <div className="pm-hero">
        <div>
          <h1>{project.name}</h1>
          <div className="pm-hero-meta">
            <span>{project.folder}</span>
            <span>{project.fps} fps</span>
            <span>{project.resolution}</span>
          </div>
        </div>
      </div>

      <div className="pm-stats">
        <Stat label="Sequences" value={stats.sequences} tone="blue"   loading={loading}/>
        <Stat label="Shots"     value={stats.shots}     tone="blue"   loading={loading}/>
        <Stat label="Assets"    value={stats.assets}    tone="purple" loading={loading}/>
        <Stat label="Publishes" value={stats.publishes} tone="accent" loading={loading}/>
      </div>

      <div className="pm-section-head">
        <span className="pm-section-title">Project Info</span>
        <span className="pm-section-rule"/>
      </div>
      <dl className="pm-info-grid">
        <dt>Name</dt>       <dd>{project.name}</dd>
        <dt>Folder</dt>     <dd>{project.folder}</dd>
        <dt>FPS</dt>        <dd>{project.fps}</dd>
        <dt>Resolution</dt> <dd>{project.resolution}</dd>
        <dt>Sequences</dt>  <dd className="list">{project.sequences?.length ? project.sequences.join(', ') : '—'}</dd>
      </dl>
    </div>
  );
}

function Stat({ label, value, tone, loading }) {
  return (
    <div className="pm-stat">
      <div className={`pm-stat-num pm-stat-${tone}`}>{loading ? '—' : value}</div>
      <div className="pm-stat-label">{label}</div>
    </div>
  );
}

// ───────────────────────── shots tab ──────────────────────────
function ShotsTab({ client, folder, onCountChange }) {
  const [sequences, setSequences] = useState([]);
  const [shots, setShots] = useState({});
  const [open, setOpen] = useState(new Set());
  const [addingSeq, setAddingSeq] = useState(false);
  const [addingShot, setAddingShot] = useState(null);
  const [confirm, confirmNode] = useConfirm();

  const loadAll = useCallback(async () => {
    try {
      const seqs = await client.listSequences(folder);
      setSequences(seqs);
      setOpen(prev => prev.size ? prev : new Set(seqs));
      const map = {};
      for (const s of seqs) map[s] = await client.listShots(folder, s);
      setShots(map);
      onCountChange?.(seqs.length);
    } catch (e) { toastE(e.message); }
  }, [client, folder, onCountChange]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const toggle = (s) => setOpen(prev => {
    const n = new Set(prev); n.has(s) ? n.delete(s) : n.add(s); return n;
  });

  const handleAddSeq = async (seq) => {
    try {
      await client.createSequence(folder, seq);
      toast(`Sequence ${seq.toUpperCase()} created.`);
      setAddingSeq(false);
      loadAll();
    } catch (e) { toastE(e.message); }
  };

  const handleDeleteSeq = async (seq) => {
    const r = await confirm({
      title: `Delete sequence ${seq}?`,
      body: `Removes ${seq} from the project registry. Its shot folders can optionally be deleted from disk too.`,
    });
    if (!r.confirmed) return;
    try {
      await client.deleteSequence(folder, seq, r.deleteFiles);
      toast(`Sequence ${seq} deleted.`);
      loadAll();
    } catch (e) { toastE(e.message); }
  };

  const handleAddShot = async (seq, shot) => {
    try {
      await client.createShot(folder, seq, shot);
      toast(`Shot ${shot} created.`);
      setAddingShot(null);
      loadAll();
    } catch (e) { toastE(e.message); }
  };

  const handleDeleteShot = async (seq, shot) => {
    const r = await confirm({
      title: `Delete shot ${shot}?`,
      body: `Removes ${seq}/${shot}. Work and publishes underneath are kept unless you tick the box.`,
    });
    if (!r.confirmed) return;
    try {
      await client.deleteShot(folder, seq, shot, r.deleteFiles);
      toast(`Shot ${shot} deleted.`);
      loadAll();
    } catch (e) { toastE(e.message); }
  };

  return (
    <div className="pm-panel">
      {confirmNode}
      <div className="pm-section-head">
        <span className="pm-section-title">Sequences &amp; Shots</span>
        <span className="pm-section-rule"/>
        {!addingSeq && (
          <button className="pm-btn pm-btn-ghost" onClick={() => setAddingSeq(true)}>
            <PMIcon name="plus" size={11}/> Sequence
          </button>
        )}
      </div>

      {addingSeq && (
        <InlineForm placeholder="Sequence code (e.g. SQ010)" mono
                    onSubmit={handleAddSeq} onCancel={() => setAddingSeq(false)}/>
      )}

      {sequences.length === 0 && !addingSeq && (
        <div className="pm-empty">
          <PMIcon name="shot" size={28}/>
          <div className="pm-empty-title">No sequences yet</div>
          <div className="pm-empty-sub">Add one above to start dropping shots in.</div>
        </div>
      )}

      {sequences.map(seq => {
        const isOpen = open.has(seq);
        const list = shots[seq] || [];
        const isAddingHere = addingShot === seq;
        return (
          <div key={seq} className="pm-seq">
            <div className={`pm-seq-head ${isOpen ? 'open' : ''}`} onClick={() => toggle(seq)}>
              <span className="pm-seq-caret">
                <PMIcon name={isOpen ? 'chevD' : 'chev'} size={10}/>
              </span>
              <span className="pm-seq-label">{seq}</span>
              <span className="pm-seq-count">{list.length} {list.length === 1 ? 'shot' : 'shots'}</span>
              <div className="pm-seq-actions" onClick={e => e.stopPropagation()}>
                <button className="pm-icon-btn" title="Add shot"
                        onClick={() => { setAddingShot(seq); setOpen(prev => new Set(prev).add(seq)); }}>
                  <PMIcon name="plus" size={11}/>
                </button>
                <button className="pm-icon-btn danger" title="Delete sequence"
                        onClick={() => handleDeleteSeq(seq)}>
                  <PMIcon name="trash" size={11}/>
                </button>
              </div>
            </div>
            {isOpen && (
              <div className="pm-seq-body">
                {isAddingHere && (
                  <InlineForm placeholder="Shot code (e.g. 0010 or SQ010_0010)" mono compact
                              onSubmit={(v) => handleAddShot(seq, v)}
                              onCancel={() => setAddingShot(null)}/>
                )}
                <div className="pm-shot-grid">
                  {list.map(shot => (
                    <div key={shot} className="pm-shot">
                      <span className="pm-shot-name">{shot}</span>
                      <button className="pm-shot-del" onClick={() => handleDeleteShot(seq, shot)}
                              title="Delete shot">
                        <PMIcon name="close" size={11}/>
                      </button>
                    </div>
                  ))}
                  {!isAddingHere && (
                    <button className="pm-add-card compact" onClick={() => setAddingShot(seq)}>
                      <PMIcon name="plus" size={11}/> Shot
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ───────────────────────── assets tab ──────────────────────────
function AssetsTab({ client, folder, onCountChange }) {
  const [assets, setAssets] = useState({});
  const [addingType, setAddingType] = useState(false);
  const [addingAsset, setAddingAsset] = useState(null);
  const [confirm, confirmNode] = useConfirm();

  const load = useCallback(async () => {
    try {
      const data = await client.listAssets(folder);
      setAssets(data);
      const total = Object.values(data).reduce((s, a) => s + a.length, 0);
      onCountChange?.(total);
    } catch (e) { toastE(e.message); }
  }, [client, folder, onCountChange]);

  useEffect(() => { load(); }, [load]);

  const handleAddType = async (asset_type) => {
    try {
      await client.createAssetType(folder, asset_type);
      toast(`Asset type '${asset_type.toLowerCase()}' created.`);
      setAddingType(false);
      load();
    } catch (e) { toastE(e.message); }
  };

  const handleDeleteType = async (type) => {
    const r = await confirm({
      title: `Delete '${type}' asset type?`,
      body: `Removes the entire '${type}' category. Any assets inside it are unregistered.`,
    });
    if (!r.confirmed) return;
    try {
      await client.deleteAssetType(folder, type, r.deleteFiles);
      toast(`Asset type '${type}' deleted.`);
      load();
    } catch (e) { toastE(e.message); }
  };

  const handleAddAsset = async (type, asset) => {
    try {
      await client.createAsset(folder, type, asset);
      toast(`Asset '${asset}' created.`);
      setAddingAsset(null);
      load();
    } catch (e) { toastE(e.message); }
  };

  const handleDeleteAsset = async (type, asset) => {
    const r = await confirm({
      title: `Delete asset '${asset}'?`,
      body: `Removes ${type}/${asset} from the project.`,
    });
    if (!r.confirmed) return;
    try {
      await client.deleteAsset(folder, type, asset, r.deleteFiles);
      toast(`Asset '${asset}' deleted.`);
      load();
    } catch (e) { toastE(e.message); }
  };

  const types = Object.entries(assets);

  return (
    <div className="pm-panel">
      {confirmNode}
      <div className="pm-section-head">
        <span className="pm-section-title">Asset Types &amp; Assets</span>
        <span className="pm-section-rule"/>
        {!addingType && (
          <button className="pm-btn pm-btn-ghost" onClick={() => setAddingType(true)}>
            <PMIcon name="plus" size={11}/> Type
          </button>
        )}
      </div>

      {addingType && (
        <InlineForm placeholder="Asset type (e.g. character, prop, environment)"
                    onSubmit={handleAddType} onCancel={() => setAddingType(false)}/>
      )}

      {types.length === 0 && !addingType && (
        <div className="pm-empty">
          <PMIcon name="asset" size={28}/>
          <div className="pm-empty-title">No asset types yet</div>
          <div className="pm-empty-sub">Add one like <span className="mono">character</span> or <span className="mono">prop</span>.</div>
        </div>
      )}

      {types.map(([type, list]) => {
        const isAddingHere = addingAsset === type;
        return (
          <div key={type} className="pm-asset-type">
            <div className="pm-asset-type-head">
              <span className="pm-asset-type-label">{type}</span>
              <span className="pm-asset-type-rule"/>
              <button className="pm-icon-btn" title="Add asset" onClick={() => setAddingAsset(type)}>
                <PMIcon name="plus" size={11}/>
              </button>
              <button className="pm-asset-type-del" onClick={() => handleDeleteType(type)}>
                Delete type
              </button>
            </div>
            {isAddingHere && (
              <InlineForm placeholder="Asset name (e.g. hero, harbor)"
                          onSubmit={(v) => handleAddAsset(type, v)}
                          onCancel={() => setAddingAsset(null)}/>
            )}
            <div className="pm-asset-grid">
              {list.map(asset => (
                <div key={asset} className="pm-asset">
                  <div className="pm-asset-name">{asset}</div>
                  <div className="pm-asset-meta">{type}/{asset}</div>
                  <button className="pm-asset-del" onClick={() => handleDeleteAsset(type, asset)}>
                    Remove
                  </button>
                </div>
              ))}
              {!isAddingHere && (
                <button className="pm-add-card" onClick={() => setAddingAsset(type)}>
                  <PMIcon name="plus" size={12}/> Asset
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ───────────────────────── topbar with nav + conn ──────────────────────────
function PMTopbar({ mode, apiBase, onReconnect }) {
  const dotColor = mode === 'live' ? 'oklch(72% 0.16 145)' : 'oklch(72% 0.14 60)';
  return (
    <header className="topbar" style={{ gridTemplateColumns: 'auto 1fr auto' }}>
      <div className="brand" style={{ gap: 10 }}>
        <div className="brand-mark">
          <svg width="18" height="18" viewBox="0 0 18 18">
            <path d="M3 3 L15 3 L9 9 L15 15 L3 15 Z" fill="none" stroke="currentColor"
                  strokeWidth="1.4" strokeLinejoin="round"/>
          </svg>
        </div>
        <div className="brand-text">
          <div className="brand-name">FX Pipeline</div>
          <div className="brand-sub">Pipeline Manager</div>
        </div>
      </div>

      <nav className="pm-nav">
        <a className="pm-nav-link" href="Publish Gallery.html">
          <PMIcon name="gallery" size={12} style={{ marginRight: 6 }}/>
          <span style={{ marginLeft: 4 }}>Gallery</span>
        </a>
        <a className="pm-nav-link active" href="Pipeline Manager.html">
          <PMIcon name="settings" size={12} style={{ marginRight: 6 }}/>
          <span style={{ marginLeft: 4 }}>Manager</span>
        </a>
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button className="pm-btn pm-btn-icon" onClick={onReconnect} title="Reconnect / refresh">
          <PMIcon name="refresh" size={12}/>
        </button>
        <div className={`conn conn-${mode}`}
             title={mode === 'live' ? `Connected to ${apiBase}` : `Demo data — server at ${apiBase} not reachable`}>
          <span className="conn-dot" style={{ background: dotColor }}/>
          <div className="conn-text">
            <span className="conn-label">{mode === 'live' ? 'Live' : 'Demo'}</span>
            <span className="conn-sub mono small">
              {mode === 'live' ? apiBase.replace(/^https?:\/\//, '') : 'no server'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}

// ───────────────────────── app ──────────────────────────
const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'shots',    label: 'Shots'    },
  { id: 'assets',   label: 'Assets'   },
];

function App() {
  const [mode, setMode] = useState('connecting');  // 'connecting' | 'live' | 'mock'
  const [apiBase] = useState(resolveApiBase);
  const [projects, setProjects] = useState([]);
  const [activeFolder, setActiveFolder] = useState(() => localStorage.getItem('pm-active') || null);
  const [tab, setTab] = useState('overview');
  const [newProj, setNewProj] = useState(false);
  const [error, setError] = useState(null);
  const [confirm, confirmNode] = useConfirm();
  const [seqCount, setSeqCount] = useState(0);
  const [assetCount, setAssetCount] = useState(0);

  // Probe server, then build a client matching the mode we landed in.
  const probe = useCallback(async () => {
    if (isMockForced()) {
      setMode('mock');
      setError('Forced demo mode (?mock=1). Set up the server and remove the flag to go live.');
      return;
    }
    setMode('connecting');
    setError(null);
    try {
      const r = await fetchTimeout(`${apiBase}/projects`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await r.json();
      setMode('live');
    } catch (e) {
      const msg = e?.name === 'AbortError' ? 'timed out' : (e?.message || String(e));
      console.warn('Pipeline server unreachable:', msg);
      setMode('mock');
      setError(
        `Pipeline server unreachable at ${apiBase} — running on demo data. ` +
        `Start the Pipeline Manager shelf tool, or run \`python server.py\`, then click reconnect.`
      );
    }
  }, [apiBase]);

  useEffect(() => { probe(); }, [probe]);

  const client = useMemo(
    () => mode === 'connecting' ? null : makeClient(mode, apiBase),
    [mode, apiBase]
  );

  const loadProjects = useCallback(async () => {
    if (!client) return;
    try {
      const data = await client.listProjects();
      setProjects(data);
      // pick a default selection
      if (data.length === 0) {
        setActiveFolder(null);
      } else if (!activeFolder || !data.some(p => p.folder === activeFolder)) {
        setActiveFolder(data[0].folder);
      }
    } catch (e) { toastE(e.message); }
  }, [client, activeFolder]);

  useEffect(() => { loadProjects(); }, [client]); // eslint-disable-line

  useEffect(() => {
    if (activeFolder) localStorage.setItem('pm-active', activeFolder);
  }, [activeFolder]);

  const activeProject = projects.find(p => p.folder === activeFolder) || null;

  const handleCreateProject = async (body) => {
    try {
      const result = await client.createProject(body);
      toast(`Project '${body.name}' created.`);
      setNewProj(false);
      await loadProjects();
      setActiveFolder(result?.folder || body.folder);
      setTab('overview');
    } catch (e) { toastE(e.message); }
  };

  const handleDeleteProject = async (proj) => {
    const r = await confirm({
      title: `Delete '${proj.name}'?`,
      body: `Removes '${proj.folder}' from the project list. All sequences, shots, and assets registered to it are unregistered.`,
    });
    if (!r.confirmed) return;
    try {
      await client.deleteProject(proj.folder, r.deleteFiles);
      toast(`Project '${proj.name}' deleted.`);
      if (activeFolder === proj.folder) setActiveFolder(null);
      loadProjects();
    } catch (e) { toastE(e.message); }
  };

  return (
    <div className="app">
      {confirmNode}
      {newProj && (
        <NewProjectDialog onSubmit={handleCreateProject} onCancel={() => setNewProj(false)}/>
      )}

      <PMTopbar mode={mode === 'connecting' ? 'mock' : mode}
                apiBase={apiBase}
                onReconnect={probe}/>

      {error && (
        <div className="banner-warn" style={{ position: 'relative', zIndex: 1 }}>
          <svg width="12" height="12" viewBox="0 0 16 16" style={{ flexShrink: 0 }}>
            <path d="M8 2l6.5 11h-13z" fill="none" stroke="currentColor" strokeWidth="1.6"
                  strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M8 6v3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
            <circle cx="8" cy="11" r="0.6" fill="currentColor"/>
          </svg>
          <span>{error}</span>
        </div>
      )}

      <div className="main" style={{ gridTemplateColumns: 'var(--sidebar-w) 1fr' }}>
        <ProjectsSidebar
          projects={projects}
          activeFolder={activeFolder}
          onSelect={(f) => { setActiveFolder(f); setTab('overview'); }}
          onNew={() => setNewProj(true)}
          onDelete={handleDeleteProject}
        />

        <div className="pm-content">
          {!activeProject ? (
            <div className="pm-empty fill">
              <PMIcon name="folder" size={32}/>
              <div className="pm-empty-title">No project selected</div>
              <div className="pm-empty-sub">
                {projects.length === 0
                  ? 'Create one to get started.'
                  : 'Pick a project from the sidebar.'}
              </div>
            </div>
          ) : (
            <>
              <div className="pm-tabs">
                {TABS.map(t => (
                  <button key={t.id}
                          className={`pm-tab ${tab === t.id ? 'active' : ''}`}
                          onClick={() => setTab(t.id)}>
                    {t.label}
                    {t.id === 'shots'  && tab !== 'shots'  && seqCount   > 0 && <span className="pm-tab-count">{seqCount}</span>}
                    {t.id === 'assets' && tab !== 'assets' && assetCount > 0 && <span className="pm-tab-count">{assetCount}</span>}
                  </button>
                ))}
              </div>
              {tab === 'overview' && <OverviewTab client={client} project={activeProject}/>}
              {tab === 'shots'    && <ShotsTab    client={client} folder={activeProject.folder} onCountChange={setSeqCount}/>}
              {tab === 'assets'   && <AssetsTab   client={client} folder={activeProject.folder} onCountChange={setAssetCount}/>}
            </>
          )}
        </div>
      </div>

      <Toaster/>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
