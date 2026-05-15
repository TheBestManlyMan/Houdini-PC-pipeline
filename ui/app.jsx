/* global React, ReactDOM, TweaksPanel, useTweaks, TweakSection, TweakRadio, TweakColor, TweakToggle, TweakSlider, TweakText */
const { useState, useMemo, useEffect, useRef, useCallback } = React;

// ───────────────────────── fullscreen helper ──────────────────────────
const toggleFullscreen = (el) => {
  if (!el) return;
  if (!document.fullscreenElement) {
    (el.requestFullscreen?.() ?? el.webkitRequestFullscreen?.());
  } else {
    (document.exitFullscreen?.() ?? document.webkitExitFullscreen?.());
  }
};

// ───────────────────────── format helpers ──────────────────────────
const versionLabel = (v) => `v${String(v).padStart(3, '0')}`;
const fmtRelative = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const now = new Date('2026-05-13T00:21:00Z');
  const diff = (now - d) / 1000;
  if (diff < 60)        return 'just now';
  if (diff < 3600)      return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400)     return `${Math.floor(diff/3600)}h ago`;
  if (diff < 86400*7)   return `${Math.floor(diff/86400)}d ago`;
  return d.toLocaleDateString(undefined, { month:'short', day:'numeric' });
};
const fmtDateLong = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString(undefined,
    { month:'short', day:'numeric', year:'numeric', hour:'2-digit', minute:'2-digit' });
};
const fmtMb = (mb) => {
  if (mb == null) return '—';
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
};
const fmtFrames = (s, e) => {
  if (s == null || e == null) return '—';
  if (s === e) return `${s}`;
  return `${s}–${e}  ·  ${e - s + 1}f`;
};

// Context display helpers
const contextLabel = (ctx) => {
  if (!ctx) return '';
  if (ctx.type === 'shot')  return `${ctx.sequence}/${ctx.shot}`;
  if (ctx.type === 'asset') return `${ctx.asset_type}/${ctx.asset}`;
  return '';
};
const contextPathBits = (ctx) => {
  if (!ctx) return [];
  if (ctx.type === 'shot')  return [ctx.sequence, ctx.shot];
  if (ctx.type === 'asset') return [ctx.asset_type, ctx.asset];
  return [];
};

const initials = (name) => (name || '?').slice(0,2).toUpperCase();
const userColor = (name) => {
  if (!name) return 'oklch(40% 0.02 250)';
  let h = 0; for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
  return `oklch(58% 0.10 ${h})`;
};

// ───────────────────────── icons ──────────────────────────
const Icon = ({ name, size = 14 }) => {
  const s = size;
  const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' };
  const paths = {
    search:   <><circle cx="7" cy="7" r="5" {...stroke}/><path d="M11 11l4 4" {...stroke}/></>,
    grid:     <><rect x="2" y="2" width="5" height="5" {...stroke}/><rect x="9" y="2" width="5" height="5" {...stroke}/><rect x="2" y="9" width="5" height="5" {...stroke}/><rect x="9" y="9" width="5" height="5" {...stroke}/></>,
    list:     <><path d="M2 4h12M2 8h12M2 12h12" {...stroke}/></>,
    table:    <><rect x="2" y="2" width="12" height="12" {...stroke}/><path d="M2 6h12M2 10h12M6 2v12" {...stroke}/></>,
    play:     <path d="M5 3l8 5-8 5z" fill="currentColor"/>,
    folder:   <path d="M2 5a1 1 0 011-1h3l2 2h5a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1z" {...stroke}/>,
    shot:     <><rect x="2" y="4" width="9" height="8" {...stroke}/><path d="M11 6l3-2v8l-3-2z" {...stroke}/></>,
    asset:    <><path d="M8 2l5 3v6l-5 3-5-3V5z" {...stroke}/><path d="M3 5l5 3 5-3M8 8v6" {...stroke}/></>,
    chevron:  <path d="M5 3l5 5-5 5" {...stroke}/>,
    chevronD: <path d="M3 5l5 5 5-5" {...stroke}/>,
    download: <><path d="M8 2v9M4 7l4 4 4-4M2 13h12" {...stroke}/></>,
    copy:     <><rect x="3" y="3" width="8" height="8" rx="1" {...stroke}/><path d="M6 13h6a1 1 0 001-1V6" {...stroke}/></>,
    close:    <path d="M3 3l10 10M13 3L3 13" {...stroke}/>,
    open:     <><path d="M6 2H3a1 1 0 00-1 1v10a1 1 0 001 1h10a1 1 0 001-1v-3" {...stroke}/><path d="M10 2h4v4M14 2L8 8" {...stroke}/></>,
    check:    <path d="M3 8l3 3 7-7" {...stroke}/>,
    refresh:  <><path d="M13 8a5 5 0 11-1.5-3.5L13 6" {...stroke}/><path d="M13 3v3h-3" {...stroke}/></>,
    sort:     <><path d="M4 3v10M4 13l-2-2M4 13l2-2" {...stroke}/><path d="M12 13V3M12 3l-2 2M12 3l2 2" {...stroke}/></>,
    warn:     <><path d="M8 2l6.5 11h-13z" {...stroke}/><path d="M8 6v3" {...stroke}/><circle cx="8" cy="11" r="0.6" fill="currentColor"/></>,
    link:     <><path d="M6.5 9.5a3 3 0 010-4.2l2-2a3 3 0 014.2 4.2l-1 1" {...stroke}/><path d="M9.5 6.5a3 3 0 010 4.2l-2 2a3 3 0 01-4.2-4.2l1-1" {...stroke}/></>,
    branch:   <><circle cx="4" cy="3.5" r="1.5" {...stroke}/><circle cx="4" cy="12.5" r="1.5" {...stroke}/><circle cx="12" cy="8" r="1.5" {...stroke}/><path d="M4 5v6M5.5 8H10.5" {...stroke}/></>,
    tag:      <><path d="M2 7V3a1 1 0 011-1h4l7 7-5 5z" {...stroke}/><circle cx="5" cy="5" r="0.6" fill="currentColor"/></>,
    rop:      <><rect x="2" y="6" width="4" height="4" rx="0.5" {...stroke}/><rect x="10" y="6" width="4" height="4" rx="0.5" {...stroke}/><path d="M6 8h4" {...stroke}/></>,
    info:     <><circle cx="8" cy="8" r="6" {...stroke}/><path d="M8 7v4M8 5v0.5" {...stroke}/></>,
    expand:   <><path d="M3 7V3h4" {...stroke}/><path d="M13 3h-4M13 3v4" {...stroke}/><path d="M3 9v4h4" {...stroke}/><path d="M13 13h-4M13 13v-4" {...stroke}/></>,
    cube:     <><path d="M8 2l5 3v6l-5 3-5-3V5z" {...stroke}/><path d="M8 2v12M3 5l5 3 5-3" {...stroke}/></>,
    rotate:   <><path d="M13 8a5 5 0 11-1.5-3.5" {...stroke}/><path d="M11 3l2 2-2 2" {...stroke}/></>,
    image:    <><rect x="2" y="3" width="12" height="10" rx="1" {...stroke}/><path d="M2 9l3-3 3 3 3-4 3 4" {...stroke}/></>,
  };
  return <svg width={s} height={s} viewBox="0 0 16 16" style={{ display: 'block' }}>{paths[name]}</svg>;
};

// ───────────────────────── publish type meta ──────────────────────────
// Five types from the real pipeline: cache, flipbook, render, usd, hip.
const PUBLISH_TYPES = ['cache', 'flipbook', 'render', 'usd', 'hip'];
const TYPE_HUE = { cache: 150, flipbook: 80, render: 230, usd: 300, hip: 30 };

// ───────────────────────── animated preview ──────────────────────────
const HoverPreview = ({ pub, playing }) => {
  const [t, setT] = useState(0);
  useEffect(() => {
    if (!playing) { setT(0); return; }
    let raf, start;
    const tick = (now) => {
      if (!start) start = now;
      setT(((now - start) / 1000) % 3);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  const seed = (pub.uuid || '').split('').reduce((a,c) => a + c.charCodeAt(0), 0) || 1;
  const cells = [];
  const N = pub.publish_type === 'flipbook' ? 30 : 20;
  for (let i = 0; i < N; i++) {
    const phase = (seed * 0.13 + i * 0.37) % 1;
    const baseX = ((seed * 31 + i * 73) % 100);
    const baseY = ((seed * 17 + i * 41) % 100);
    const driftY = pub.publish_type === 'flipbook'
      ? 40 * Math.sin(t * 2 + phase * 6.28) + (t * 30) % 60 - 30
      : 8 * Math.sin(t * 1.2 + i);
    const r = 0.6 + ((i + seed) % 5) * 0.4;
    const op = 0.18 + ((i + seed) % 4) * 0.14;
    cells.push(
      <circle key={i}
        cx={`${baseX}%`}
        cy={`${(baseY + driftY + 100) % 100}%`}
        r={r}
        fill="oklch(82% 0.10 80)"
        opacity={op} />
    );
  }

  const sweep = pub.publish_type === 'render' ? (
    <rect x={`${(t * 40) % 110 - 10}%`} y="0" width="6%" height="100%"
          fill="oklch(85% 0.08 80)" opacity="0.06" />
  ) : null;

  const frames = pub.stats?.frame_end - pub.stats?.frame_start;
  const frame = pub.stats?.frame_start != null && frames > 0
    ? pub.stats.frame_start + Math.floor(t * 12) % Math.max(1, frames)
    : null;

  return (
    <svg viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice"
         style={{ position:'absolute', inset:0, width:'100%', height:'100%' }}>
      <defs>
        <radialGradient id={`hp${seed}`} cx="50%" cy="50%" r="60%">
          <stop offset="0%" stopColor="oklch(40% 0.08 70)" stopOpacity="0.4"/>
          <stop offset="100%" stopColor="oklch(15% 0.02 60)" stopOpacity="0"/>
        </radialGradient>
      </defs>
      <rect width="320" height="180" fill={`url(#hp${seed})`}/>
      {sweep}
      {cells}
      {frame != null && (
        <g style={{ fontFamily:'var(--mono)', fontSize: 9, fill: 'rgba(255,255,255,0.65)' }}>
          <rect x="8" y="158" width="44" height="14" rx="2" fill="rgba(0,0,0,0.55)"/>
          <text x="12" y="168">F {frame}</text>
        </g>
      )}
    </svg>
  );
};

// ───────────────────────── badges / pills ──────────────────────────
const TypeChip = ({ type, dim }) => (
  <span className={`type-chip type-${type} ${dim ? 'dim' : ''}`}>{type}</span>
);
const TypeDot = ({ type }) => <span className={`type-dot type-${type}`}/>;

const Avatar = ({ user, size = 18 }) => (
  <span className="avatar" style={{
    width: size, height: size, fontSize: Math.round(size * 0.42),
    background: userColor(user)
  }}>{initials(user)}</span>
);

const WarnPill = ({ warnings }) => {
  if (!warnings?.length) return null;
  const label = warnings.length === 1 ? warnings[0].replace(/_/g,' ') : `${warnings.length} warnings`;
  return (
    <span className="warn-pill" title={warnings.join(', ')}>
      <Icon name="warn" size={10}/> {label}
    </span>
  );
};

// ───────────────────────── glb preview (model-viewer) ──────────────────────────
const GlbPreview = ({ src, entity }) => {
  const ref = useRef(null);
  const [progress, setProgress] = useState(0);
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    const el = ref.current; if (!el) return;
    const onProg = (e) => setProgress(Math.round((e.detail.totalProgress || 0) * 100));
    const onLoad = () => setReady(true);
    const onErr  = (e) => setErr(e.detail?.sourceError?.message || 'Failed to load model');
    el.addEventListener('progress', onProg);
    el.addEventListener('load', onLoad);
    el.addEventListener('error', onErr);
    return () => {
      el.removeEventListener('progress', onProg);
      el.removeEventListener('load', onLoad);
      el.removeEventListener('error', onErr);
    };
  }, [src]);

  return (
    <div className="glb-preview">
      <model-viewer
        ref={ref}
        src={src}
        camera-controls
        interaction-prompt="none"
        shadow-intensity="1.1"
        exposure="0.95"
        environment-image="neutral"
        camera-orbit="35deg 75deg auto"
        field-of-view="32deg"
        style={{
          width: '100%', height: '100%', display: 'block',
          background: 'radial-gradient(ellipse at center, oklch(22% 0.01 250), oklch(10% 0.004 250))',
        }}
      />
      <div className="glb-pills">
        <span className="glb-pill mono">{entity}.glb</span>
        <span className="glb-pill mono" data-state={ready ? 'ok' : (err ? 'err' : 'loading')}>
          {ready ? 'loaded' : (err ? 'error' : `${progress}%`)}
        </span>
      </div>
      {!ready && !err && (
        <div className="glb-overlay">
          <div className="glb-spinner"/>
          <div className="mono small muted">Streaming GLB · {progress}%</div>
        </div>
      )}
      {err && (
        <div className="glb-overlay glb-err">
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Couldn't load model</div>
          <div className="mono small">{err}</div>
        </div>
      )}
      <div className="glb-hint">drag to orbit · scroll to zoom · right-drag to pan</div>
    </div>
  );
};

// ───────────────────────── card ──────────────────────────
const Card = ({ pub, selected, onSelect, view }) => {
  const [hover, setHover] = useState(false);
  const hasVideo = !!pub.outputs?.mp4;
  const hasGlb   = !!(pub.real_glb || pub.outputs?.glb);
  const thumb = pub.outputs?.thumbnail;

  if (view === 'list') {
    return (
      <div className={`row ${selected ? 'selected' : ''} ${pub._orphaned ? 'orphan' : ''}`}
           onClick={() => onSelect(pub)}
           onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
        <div className="row-thumb">
          {thumb ? <img src={thumb} alt=""/> : <div className="no-thumb"/>}
          {hasVideo && hover && <HoverPreview pub={pub} playing={hover}/>}
          {hasVideo && <span className="play-pill"><Icon name="play" size={9}/></span>}
          {hasGlb && <span className="play-pill" style={{ left: hasVideo ? 32 : 6 }} title="3D proxy available"><Icon name="cube" size={9}/></span>}
        </div>
        <div className="row-main">
          <div className="row-title">
            <TypeDot type={pub.publish_type}/>
            <span className="title-text">{pub.entity}</span>
            <span className="muted">·</span>
            <span className="task">{pub.task}</span>
            <span className="ver">{versionLabel(pub.version)}</span>
            {pub._warnings?.length > 0 && <Icon name="warn" size={11}/>}
          </div>
          <div className="row-meta">
            <span className="ctx">{pub.project} / {contextLabel(pub.context)}</span>
            <span className="muted">·</span>
            <TypeChip type={pub.publish_type} dim/>
            {pub.stats?.frame_start != null && pub.stats.frame_end !== pub.stats.frame_start && (
              <><span className="muted">·</span><span className="mono">{pub.stats.frame_start}–{pub.stats.frame_end}</span></>
            )}
            {pub.tags?.length > 0 && pub.tags.slice(0,2).map(t => (
              <span key={t} className="tag-mini">{t}</span>
            ))}
          </div>
        </div>
        <div className="row-user"><Avatar user={pub.created_by}/><span>{pub.created_by}</span></div>
        <div className="row-date">{fmtRelative(pub.created_at)}</div>
      </div>
    );
  }

  return (
    <div className={`card ${selected ? 'selected' : ''} ${pub._orphaned ? 'orphan' : ''}`}
         onClick={() => onSelect(pub)}
         onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      <div className="thumb">
        {thumb ? <img src={thumb} alt="" loading="lazy"/> : <div className="no-thumb">no preview</div>}
        {hasVideo && hover && <HoverPreview pub={pub} playing={hover}/>}
        <div className="thumb-overlay">
          <TypeChip type={pub.publish_type}/>
          <div className="thumb-overlay-right">
            {pub._warnings?.length > 0 && (
              <span className="warn-badge" title={pub._warnings.join(', ')}>
                <Icon name="warn" size={11}/>
              </span>
            )}
            {hasGlb && <span className="play-pill" title="3D proxy available"><Icon name="cube" size={9}/></span>}
            {hasVideo && <span className="play-pill"><Icon name="play" size={9}/></span>}
          </div>
        </div>
        <div className="thumb-bottom">
          {pub.stats?.frame_end > pub.stats?.frame_start && (
            <span className="mono small">{pub.stats.frame_end - pub.stats.frame_start + 1}f</span>
          )}
          <span className="mono small" style={{ marginLeft: 'auto' }}>{fmtMb(pub.stats?.disk_mb)}</span>
        </div>
      </div>
      <div className="card-body">
        <div className="card-line1">
          <span className="title-text">{pub.entity}</span>
          <span className="ver">{versionLabel(pub.version)}</span>
        </div>
        <div className="card-line2">
          <span className="task">{pub.task}</span>
        </div>
        <div className="card-line3">
          <span className="ctx-small">{pub.project}  /  {contextLabel(pub.context)}</span>
        </div>
        <div className="card-foot">
          <Avatar user={pub.created_by} size={16}/>
          <span className="foot-user">{pub.created_by}</span>
          <span className="foot-date">{fmtRelative(pub.created_at)}</span>
        </div>
      </div>
    </div>
  );
};

// ───────────────────────── table view ──────────────────────────
const TableView = ({ pubs, selected, onSelect }) => (
  <div className="table">
    <div className="th">
      <div className="th-cell c-thumb"></div>
      <div className="th-cell c-entity">Entity</div>
      <div className="th-cell c-task">Task</div>
      <div className="th-cell c-type">Type</div>
      <div className="th-cell c-ver">Ver</div>
      <div className="th-cell c-frames">Frames</div>
      <div className="th-cell c-size">Size</div>
      <div className="th-cell c-project">Project</div>
      <div className="th-cell c-user">By</div>
      <div className="th-cell c-date">Date</div>
      <div className="th-cell c-flags"></div>
    </div>
    {pubs.map(p => (
      <div key={p.uuid} className={`tr ${selected?.uuid === p.uuid ? 'selected' : ''}`}
           onClick={() => onSelect(p)}>
        <div className="td c-thumb">{p.outputs?.thumbnail ? <img src={p.outputs.thumbnail} alt=""/> : <div className="td-nothumb"/>}</div>
        <div className="td c-entity"><TypeDot type={p.publish_type}/><span>{p.entity}</span></div>
        <div className="td c-task"><span>{p.task}</span></div>
        <div className="td c-type"><TypeChip type={p.publish_type} dim/></div>
        <div className="td c-ver mono">{versionLabel(p.version)}</div>
        <div className="td c-frames mono">{p.stats?.frame_start != null && p.stats.frame_end > p.stats.frame_start ? `${p.stats.frame_start}–${p.stats.frame_end}` : '—'}</div>
        <div className="td c-size mono">{fmtMb(p.stats?.disk_mb)}</div>
        <div className="td c-project"><span>{p.project}</span></div>
        <div className="td c-user"><Avatar user={p.created_by} size={16}/><span>{p.created_by}</span></div>
        <div className="td c-date">{fmtRelative(p.created_at)}</div>
        <div className="td c-flags">{p._warnings?.length > 0 && <span className="warn-badge"><Icon name="warn" size={10}/></span>}</div>
      </div>
    ))}
  </div>
);

// ───────────────────────── sidebar ──────────────────────────
const Sidebar = ({ pubs, projects, filters, setFilters }) => {
  // Tree: project → entity (with type) → task
  const tree = useMemo(() => {
    const t = {};
    pubs.forEach(p => {
      const proj = p.project;
      t[proj] = t[proj] || { count: 0, entities: {} };
      t[proj].count++;
      const ent = t[proj].entities[p.entity] = t[proj].entities[p.entity] || {
        count: 0, type: p.context?.type, context: p.context, tasks: {}
      };
      ent.count++;
      ent.tasks[p.task] = (ent.tasks[p.task] || 0) + 1;
    });
    return t;
  }, [pubs]);

  const [openProj, setOpenProj] = useState(() => new Set(Object.keys(tree).slice(0, 3)));
  const [openEnt, setOpenEnt] = useState(() => new Set());

  const toggleProj = (p) => { const n = new Set(openProj); n.has(p) ? n.delete(p) : n.add(p); setOpenProj(n); };
  const toggleEnt = (e) => { const n = new Set(openEnt); n.has(e) ? n.delete(e) : n.add(e); setOpenEnt(n); };

  const select = (project = null, entity = null, task = null) => {
    setFilters({ ...filters, project, entity, task });
  };

  const typeCounts = useMemo(() => {
    const c = {}; PUBLISH_TYPES.forEach(t => c[t] = 0);
    pubs.forEach(p => { if (c[p.publish_type] !== undefined) c[p.publish_type]++; });
    return c;
  }, [pubs]);

  const users = useMemo(() => {
    const c = {};
    pubs.forEach(p => { if (p.created_by) c[p.created_by] = (c[p.created_by] || 0) + 1; });
    return Object.entries(c).sort((a,b) => b[1] - a[1]);
  }, [pubs]);

  const warnCount = pubs.filter(p => p._warnings?.length > 0).length;

  return (
    <aside className="sidebar">
      <div className="side-section">
        <div className="side-heading">Library</div>
        <div className={`side-item ${!filters.project && !filters.type && !filters.user && !filters.flagged ? 'active' : ''}`}
             onClick={() => setFilters({ project:null, entity:null, task:null, type:null, user:null, flagged:false })}>
          <Icon name="folder" size={13}/>
          <span>All publishes</span>
          <span className="count-pill">{pubs.length}</span>
        </div>
        {warnCount > 0 && (
          <div className={`side-item ${filters.flagged ? 'active' : ''}`}
               onClick={() => setFilters({ ...filters, flagged: !filters.flagged })}>
            <Icon name="warn" size={12}/>
            <span>Flagged</span>
            <span className="count-pill">{warnCount}</span>
          </div>
        )}
      </div>

      <div className="side-section">
        <div className="side-heading">Type</div>
        {PUBLISH_TYPES.map(t => (
          <div key={t}
               className={`side-item ${filters.type === t ? 'active' : ''}`}
               onClick={() => setFilters({ ...filters, type: filters.type === t ? null : t })}>
            <TypeDot type={t}/>
            <span style={{ textTransform: 'lowercase' }}>{t}</span>
            <span className="count-pill">{typeCounts[t]}</span>
          </div>
        ))}
      </div>

      <div className="side-section">
        <div className="side-heading">Projects</div>
        {Object.entries(tree).map(([proj, pdata]) => {
          const open = openProj.has(proj);
          return (
            <div key={proj}>
              <div className={`side-item ${filters.project === proj && !filters.entity ? 'active' : ''}`}>
                <button className="caret" onClick={(e) => { e.stopPropagation(); toggleProj(proj); }}>
                  <Icon name={open ? 'chevronD' : 'chevron'} size={10}/>
                </button>
                <span style={{ flex:1, cursor:'pointer', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}
                      onClick={() => select(proj)}>{proj}</span>
                <span className="count-pill">{pdata.count}</span>
              </div>
              {open && Object.entries(pdata.entities).map(([ent, edata]) => {
                const eopen = openEnt.has(`${proj}/${ent}`);
                return (
                  <div key={ent}>
                    <div className={`side-item indent1 ${filters.entity === ent && !filters.task ? 'active' : ''}`}>
                      <button className="caret" onClick={(e) => { e.stopPropagation(); toggleEnt(`${proj}/${ent}`); }}>
                        <Icon name={eopen ? 'chevronD' : 'chevron'} size={10}/>
                      </button>
                      <Icon name={edata.type === 'shot' ? 'shot' : 'asset'} size={11}/>
                      <span style={{ flex:1, cursor:'pointer', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}
                            onClick={() => select(proj, ent)}>{ent}</span>
                      <span className="count-pill">{edata.count}</span>
                    </div>
                    {eopen && Object.entries(edata.tasks).map(([task, tcount]) => (
                      <div key={task}
                           className={`side-item indent2 ${filters.entity === ent && filters.task === task ? 'active' : ''}`}
                           onClick={() => select(proj, ent, task)}>
                        <span className="task-dash"/>
                        <span style={{ flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{task}</span>
                        <span className="count-pill">{tcount}</span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      <div className="side-section">
        <div className="side-heading">Artists</div>
        {users.slice(0, 8).map(([u, c]) => (
          <div key={u}
               className={`side-item ${filters.user === u ? 'active' : ''}`}
               onClick={() => setFilters({ ...filters, user: filters.user === u ? null : u })}>
            <Avatar user={u} size={16}/>
            <span style={{ flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{u}</span>
            <span className="count-pill">{c}</span>
          </div>
        ))}
      </div>
    </aside>
  );
};

// ───────────────────────── detail panel ──────────────────────────
const DetailPanel = ({ pub, allPubs, onClose, onSelect }) => {
  const [tab, setTab] = useState('overview');
  const [copied, setCopied] = useState(false);
  const [previewFrame, setPreviewFrame] = useState(null);
  const [scrubbing, setScrubbing] = useState(false);
  const previewRef = useRef(null);

  // versions = same entity/task/publish_type
  const versions = useMemo(() => {
    if (!pub) return [];
    return allPubs
      .filter(p => p.entity === pub.entity && p.task === pub.task && p.publish_type === pub.publish_type)
      .sort((a,b) => b.version - a.version);
  }, [pub, allPubs]);

  // upstream (this depends on…) and downstream (depended on by…) lookups
  const upstream = useMemo(() => {
    if (!pub) return [];
    return (pub.dependencies || []).map(d => {
      const target = allPubs.find(p => p.uuid === d.publish_uuid);
      return { dep: d, target };
    });
  }, [pub, allPubs]);

  const downstream = useMemo(() => {
    if (!pub) return [];
    return allPubs.filter(p =>
      (p.dependencies || []).some(d => d.publish_uuid === pub.uuid)
    );
  }, [pub, allPubs]);

  if (!pub) return null;

  const glbSrc = pub.real_glb || pub.outputs?.glb || null;

  const copy = () => {
    const path = pub._index_path || pub.outputs?.usd || pub.outputs?.cache || pub.outputs?.frames || '';
    navigator.clipboard?.writeText(path).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'versions', label: `Versions · ${versions.length}` },
    { id: 'deps',     label: `Deps · ${upstream.length + downstream.length}` },
    { id: 'metadata', label: 'Raw' },
  ];

  const fs = pub.stats?.frame_start, fe = pub.stats?.frame_end;
  const frames = (fs != null && fe != null) ? fe - fs + 1 : 0;
  const onScrub = (e) => {
    if (frames <= 1) return;
    const r = e.currentTarget.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    setPreviewFrame(fs + Math.floor(pct * (frames - 1)));
  };

  return (
    <aside className="detail">
      <div className="detail-head">
        <div className="detail-title">
          <TypeDot type={pub.publish_type}/>
          <span className="title-text">{pub.entity}</span>
          <span className="muted">·</span>
          <span className="task">{pub.task}</span>
          <span className="ver">{versionLabel(pub.version)}</span>
        </div>
        <button className="icon-btn" onClick={onClose} title="Close (Esc)"><Icon name="close" size={12}/></button>
      </div>

      <div className="detail-preview"
           ref={previewRef}
           onMouseDown={glbSrc ? undefined : (e) => { setScrubbing(true); onScrub(e); }}
           onMouseUp={glbSrc ? undefined : () => setScrubbing(false)}
           onMouseLeave={glbSrc ? undefined : () => { setScrubbing(false); setPreviewFrame(null); }}
           onMouseMove={glbSrc ? undefined : (e) => scrubbing && onScrub(e)}>
        {glbSrc ? (
          <GlbPreview src={glbSrc} entity={pub.entity}/>
        ) : (
          <>
            {pub.outputs?.thumbnail
              ? <img src={pub.outputs.thumbnail} alt=""/>
              : <div className="preview-no">no preview</div>}
            {pub.outputs?.mp4 && <HoverPreview pub={pub} playing={true}/>}
          </>
        )}
        {(glbSrc || pub.outputs?.thumbnail || pub.outputs?.mp4) && (
          <button className="preview-fs" title="Fullscreen"
                  onClick={(e) => { e.stopPropagation(); toggleFullscreen(previewRef.current); }}>
            <Icon name="expand" size={12}/>
          </button>
        )}
        {fs != null && frames > 1 && !glbSrc && (
          <div className="scrubber">
            <div className="scrub-track">
              <div className="scrub-fill" style={{
                width: previewFrame != null ? `${((previewFrame - fs) / Math.max(1, frames - 1)) * 100}%` : '0%'
              }}/>
            </div>
            <div className="scrub-info mono">
              <span>F {previewFrame ?? fs}</span>
              <span className="muted">/ {fe}</span>
            </div>
          </div>
        )}
        <TypeChip type={pub.publish_type}/>
      </div>

      {pub._warnings?.length > 0 && (
        <div className="warn-banner">
          <Icon name="warn" size={12}/>
          <span>{pub._warnings.map(w => w.replace(/_/g, ' ')).join(' · ')}</span>
        </div>
      )}
      {pub._orphaned && (
        <div className="warn-banner orphan">
          <Icon name="warn" size={12}/>
          <span>Orphaned — folder contains no output files</span>
        </div>
      )}

      <div className="detail-actions">
        <button className="primary-btn"><Icon name="open" size={12}/>Open in Houdini</button>
        <button className="ghost-btn" onClick={copy}>
          <Icon name={copied ? 'check' : 'copy'} size={12}/>{copied ? 'Copied' : 'Copy path'}
        </button>
        <button className="ghost-btn" title="Reveal in file manager"><Icon name="folder" size={12}/></button>
      </div>

      <div className="detail-tabs">
        {tabs.map(t => (
          <button key={t.id}
                  className={`tab ${tab === t.id ? 'active' : ''}`}
                  onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>

      <div className="detail-body">
        {tab === 'overview' && (
          <>
            <div className="kv-grid">
              <div className="kv-label">Project</div>
              <div className="kv-value">{pub.project}</div>

              <div className="kv-label">{pub.context?.type === 'shot' ? 'Shot' : 'Asset'}</div>
              <div className="kv-value">
                <Icon name={pub.context?.type === 'shot' ? 'shot' : 'asset'} size={11}/>
                <span className="mono small">{contextLabel(pub.context)}</span>
              </div>

              <div className="kv-label">Entity</div>
              <div className="kv-value">{pub.entity}</div>

              <div className="kv-label">Task</div>
              <div className="kv-value">{pub.task}</div>

              <div className="kv-label">Type</div>
              <div className="kv-value"><TypeChip type={pub.publish_type} dim/></div>

              <div className="kv-label">Frames</div>
              <div className="kv-value mono">{fmtFrames(pub.stats?.frame_start, pub.stats?.frame_end)}</div>

              <div className="kv-label">Size</div>
              <div className="kv-value mono">{fmtMb(pub.stats?.disk_mb)}</div>

              <div className="kv-label">Published</div>
              <div className="kv-value">
                <Avatar user={pub.created_by} size={16}/>
                <span>{pub.created_by}</span>
                <span className="muted">·</span>
                <span title={fmtDateLong(pub.created_at)}>{fmtRelative(pub.created_at)}</span>
              </div>

              {pub.source?.houdini_version && (<>
                <div className="kv-label">Houdini</div>
                <div className="kv-value mono small">{pub.source.houdini_version}</div>
              </>)}

              {pub.source?.git_commit && (<>
                <div className="kv-label">Commit</div>
                <div className="kv-value mono small">{pub.source.git_commit}</div>
              </>)}

              {pub.source?.rop && (<>
                <div className="kv-label">ROP</div>
                <div className="kv-value mono small"><Icon name="rop" size={11}/>{pub.source.rop}</div>
              </>)}

              <div className="kv-label">UUID</div>
              <div className="kv-value mono small uuid">{pub.uuid}</div>
            </div>

            {pub.tags?.length > 0 && (
              <div className="tags-row">
                {pub.tags.map(t => <span key={t} className="tag-chip"><Icon name="tag" size={10}/>{t}</span>)}
              </div>
            )}

            {pub.notes?.length > 0 && (
              <div className="block">
                <div className="block-label">Notes</div>
                {pub.notes.map((n, i) => <p key={i} className="note-line">{n}</p>)}
              </div>
            )}

            {pub.wedge && (
              <div className="block">
                <div className="block-label">Wedge</div>
                <div className="wedge-row">
                  <span className="mono wedge-key">{pub.wedge.parameter}</span>
                  <span className="wedge-eq">=</span>
                  <span className="mono wedge-val">{String(pub.wedge.value)}</span>
                </div>
              </div>
            )}

            <div className="block">
              <div className="block-label">Path</div>
              <div className="path-text mono">{pub._index_path}</div>
            </div>

            {(pub.outputs?.mp4 || pub.outputs?.cache || pub.outputs?.usd || pub.outputs?.frames || pub.outputs?.glb) && (
              <div className="block">
                <div className="block-label">Outputs</div>
                <div className="outputs-list">
                  {pub.outputs.mp4    && <div className="output-row"><span className="output-key">mp4</span><span className="mono output-val">preview.mp4</span></div>}
                  {pub.outputs.cache  && <div className="output-row"><span className="output-key">cache</span><span className="mono output-val">{pub.outputs.cache.split('/').pop()}</span></div>}
                  {pub.outputs.usd    && <div className="output-row"><span className="output-key">usd</span><span className="mono output-val">{pub.outputs.usd.split('/').pop()}</span></div>}
                  {pub.outputs.frames && <div className="output-row"><span className="output-key">frames</span><span className="mono output-val">{pub.outputs.frames.split('/').pop()}</span></div>}
                  {pub.outputs.glb    && <div className="output-row"><span className="output-key">proxy glb</span><span className="mono output-val">proxy.glb</span></div>}
                </div>
              </div>
            )}
          </>
        )}

        {tab === 'versions' && (
          <div className="versions">
            {versions.map(v => (
              <div key={v.uuid} className={`version-row ${v.uuid === pub.uuid ? 'current' : ''}`}
                   onClick={() => onSelect(v)}>
                {v.outputs?.thumbnail ? <img src={v.outputs.thumbnail} alt=""/> : <div className="vr-nothumb"/>}
                <div className="vr-main">
                  <div className="vr-top">
                    <span className="ver">{versionLabel(v.version)}</span>
                    {v.uuid === pub.uuid && <span className="muted small">current</span>}
                    {v._warnings?.length > 0 && <Icon name="warn" size={11}/>}
                  </div>
                  <div className="vr-desc">{v.notes?.[0] || <span className="muted">No notes</span>}</div>
                  <div className="vr-meta">
                    <Avatar user={v.created_by} size={14}/>
                    <span>{v.created_by}</span>
                    <span className="muted">·</span>
                    <span>{fmtRelative(v.created_at)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === 'deps' && (
          <div className="deps">
            <div className="block-label">Upstream — depends on</div>
            {upstream.length === 0 ? (
              <div className="muted small" style={{ padding: '4px 0 14px' }}>None</div>
            ) : (
              <div className="dep-list">
                {upstream.map(({ dep, target }) => (
                  <div key={dep.publish_uuid} className={`dep-card ${target ? '' : 'broken'}`}
                       onClick={() => target && onSelect(target)}>
                    <Icon name="branch" size={12}/>
                    <span className="dep-type-pill">{dep.type}</span>
                    {target ? (
                      <>
                        <TypeDot type={target.publish_type}/>
                        <span className="dep-entity">{target.entity}</span>
                        <span className="muted">·</span>
                        <span className="dep-task">{target.task}</span>
                        <span className="ver">{versionLabel(target.version)}</span>
                      </>
                    ) : (
                      <span className="muted small">missing — {dep.publish_uuid}</span>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className="block-label" style={{ marginTop: 18 }}>Downstream — used by</div>
            {downstream.length === 0 ? (
              <div className="muted small" style={{ padding: '4px 0' }}>Nothing depends on this publish</div>
            ) : (
              <div className="dep-list">
                {downstream.map(d => (
                  <div key={d.uuid} className="dep-card" onClick={() => onSelect(d)}>
                    <Icon name="branch" size={12}/>
                    <TypeDot type={d.publish_type}/>
                    <span className="dep-entity">{d.entity}</span>
                    <span className="muted">·</span>
                    <span className="dep-task">{d.task}</span>
                    <span className="ver">{versionLabel(d.version)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'metadata' && (
          <div className="meta-tab">
            <div className="block-label">metadata.json</div>
            <pre className="meta-json mono">{JSON.stringify(pub, (k, v) => {
              if (k === 'thumbnail' && typeof v === 'string' && v.startsWith('data:')) return '<inline data URI>';
              if (k.startsWith('_') && k !== '_warnings' && k !== '_orphaned' && k !== '_index_path') return undefined;
              return v;
            }, 2)}</pre>
          </div>
        )}
      </div>
    </aside>
  );
};

// ───────────────────────── topbar ──────────────────────────
const Topbar = ({ filters, setFilters, view, setView, sort, setSort, count, total, search, setSearch, indexedAt, onRefresh, dataSource, apiBase, rebuilding }) => {
  const chips = [];
  if (filters.project) chips.push({ k:'project', label: filters.project });
  if (filters.entity)  chips.push({ k:'entity',  label: filters.entity });
  if (filters.task)    chips.push({ k:'task',    label: filters.task });
  if (filters.type)    chips.push({ k:'type',    label: filters.type });
  if (filters.user)    chips.push({ k:'user',    label: filters.user });
  if (filters.flagged) chips.push({ k:'flagged', label: 'flagged' });

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">
          <svg width="18" height="18" viewBox="0 0 18 18">
            <path d="M3 3 L15 3 L9 9 L15 15 L3 15 Z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
          </svg>
        </div>
        <div className="brand-text">
          <div className="brand-name">FX Pipeline</div>
          <div className="brand-sub">Publish Gallery</div>
        </div>
        <nav className="top-nav">
          <a className="top-nav-link active" href="gallery.html">Gallery</a>
          <a className="top-nav-link" href="pipeline_manager.html">Manager</a>
          <a className="top-nav-link" href="mobile-review.html">Mobile</a>
        </nav>
      </div>

      <div className="search-wrap">
        <Icon name="search" size={13}/>
        <input
          className="search"
          placeholder="Search entity, task, tag, note…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <kbd className="kbd">⌘K</kbd>
      </div>

      <div className="top-right">
        <div className="seg">
          {['grid','list','table'].map(v => (
            <button key={v} className={`seg-btn ${view === v ? 'active' : ''}`}
                    onClick={() => setView(v)} title={v}>
              <Icon name={v}/>
            </button>
          ))}
        </div>
        <div className="sort">
          <Icon name="sort" size={12}/>
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="date-desc">Newest</option>
            <option value="date-asc">Oldest</option>
            <option value="entity">Entity</option>
            <option value="version-desc">Version</option>
          </select>
        </div>
        <button className={`icon-btn refresh-btn ${rebuilding ? 'spinning' : ''}`} onClick={onRefresh}
                title={dataSource === 'live' ? 'Rebuild & refresh index' : 'Reload'}>
          <Icon name="refresh" size={13}/>
        </button>
        <div className={`conn conn-${dataSource}`}
             title={dataSource === 'live'
               ? `Connected to ${apiBase}`
               : dataSource === 'static'
                 ? 'Loaded from static index file'
                 : `Demo data — server at ${apiBase} not reachable`}>
          <span className="conn-dot"/>
          <div className="conn-text">
            <span className="conn-label">
              {dataSource === 'live' ? 'Live'
                : dataSource === 'static' ? 'Static'
                : 'Demo'}
            </span>
            <span className="conn-sub mono small">
              {dataSource === 'live'
                ? (apiBase || '').replace(/^https?:\/\//, '')
                : dataSource === 'static'
                  ? (indexedAt ? new Date(indexedAt).toLocaleString(undefined, { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }) : '—')
                  : 'no server'}
            </span>
          </div>
        </div>
      </div>

      {chips.length > 0 && (
        <div className="chip-bar">
          <span className="result-count">
            <strong>{count}</strong> <span className="muted">of {total}</span>
          </span>
          {chips.map(c => (
            <button key={c.k} className="chip" onClick={() => setFilters({ ...filters, [c.k]: c.k === 'flagged' ? false : null })}>
              <span className="chip-key">{c.k}</span>
              <span className="chip-val">{c.label}</span>
              <Icon name="close" size={9}/>
            </button>
          ))}
          <button className="chip-clear"
                  onClick={() => setFilters({ project:null, entity:null, task:null, type:null, user:null, flagged:false })}>
            Clear all
          </button>
        </div>
      )}
    </header>
  );
};

// ───────────────────────── app ──────────────────────────
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "view": "grid",
  "density": "comfortable",
  "accent": "#e6a455",
  "showSidebar": true,
  "apiBase": "http://127.0.0.1:8765/api"
}/*EDITMODE-END*/;

// Resolve the FastAPI base URL: ?api=… query param wins, then the tweak default.
const resolveApiBase = (tweakDefault) => {
  const params = new URLSearchParams(location.search);
  const explicit = params.get('api');
  return ((explicit || tweakDefault) || '').replace(/\/+$/, '');
};

// Fetch with a hard timeout so the page doesn't hang when the server is offline.
const fetchTimeout = (url, opts = {}, ms = 2500) => {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  return fetch(url, { ...opts, signal: ctrl.signal })
    .finally(() => clearTimeout(t));
};

function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [filters, setFilters] = useState({
    project: null, entity: null, task: null, type: null, user: null, flagged: false
  });
  const [search, setSearch] = useState('');
  const [view, setView] = useState(tweaks.view);
  const [sort, setSort] = useState('date-desc');
  const [selected, setSelected] = useState(null);
  const [index, setIndex] = useState(null);   // top-level index payload
  const [dataSource, setDataSource] = useState('mock'); // 'live' | 'mock' | 'static'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [rebuilding, setRebuilding] = useState(false);

  const apiBase = resolveApiBase(tweaks.apiBase);

  useEffect(() => setView(tweaks.view), [tweaks.view]);
  useEffect(() => { document.documentElement.style.setProperty('--accent', tweaks.accent); }, [tweaks.accent]);
  useEffect(() => { document.documentElement.dataset.density = tweaks.density; }, [tweaks.density]);

  // Load order:
  //   1. ?index=<url>  — static index JSON (e.g. .pipeline/publishes.json)
  //   2. {apiBase}/publishes — live FastAPI server (server.py)
  //   3. window.MOCK_INDEX — bundled demo data
  const load = useCallback(async () => {
    setLoading(true); setError(null);
    const params = new URLSearchParams(location.search);
    const indexUrl = params.get('index');

    // 1) Static index file
    if (indexUrl) {
      try {
        const r = await fetch(indexUrl);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        setIndex(data);
        setDataSource('static');
        setLoading(false);
        return;
      } catch (e) {
        console.warn('Failed to load static index:', e);
        setError(`Couldn't load ${indexUrl} — trying live server.`);
      }
    }

    // 2) FastAPI server (server.py @ apiBase)
    if (params.get('mock') !== '1' && apiBase) {
      try {
        const [pubsR, projsR] = await Promise.all([
          fetchTimeout(`${apiBase}/publishes`),
          fetchTimeout(`${apiBase}/projects`).catch(() => null),
        ]);
        if (!pubsR.ok) throw new Error(`/publishes → ${pubsR.status}`);
        const publishes = await pubsR.json();
        const projects  = projsR && projsR.ok ? await projsR.json() : [];
        setIndex({
          project: 'All Projects',
          folder: null,
          indexed_at: new Date().toISOString().replace(/\.\d+Z$/, 'Z'),
          publish_count: publishes.length,
          publishes,
          projects,
        });
        setDataSource('live');
        setError(null);
        setLoading(false);
        return;
      } catch (e) {
        const msg = e?.name === 'AbortError' ? 'timed out' : (e?.message || String(e));
        console.warn(`Pipeline server unreachable at ${apiBase} — ${msg}`);
        setError(
          `Pipeline server unreachable at ${apiBase} — showing demo data. ` +
          `Start the Pipeline Manager shelf tool, or run \`python server.py\`.`
        );
      }
    }

    // 3) Mock fallback
    setIndex(window.MOCK_INDEX);
    setDataSource('mock');
    setLoading(false);
  }, [apiBase]);

  useEffect(() => { load(); }, [load]);

  // Refresh: in live mode, ask the server to rebuild the index, then re-fetch.
  const refresh = useCallback(async () => {
    if (dataSource === 'live') {
      setRebuilding(true);
      try {
        await fetchTimeout(`${apiBase}/publishes/rebuild`, { method: 'POST' }, 30000);
      } catch (e) {
        console.warn('Rebuild failed:', e);
      } finally {
        setRebuilding(false);
      }
    }
    load();
  }, [dataSource, apiBase, load]);

  const publishes = index?.publishes || [];
  const projects = index?.projects || [];
  const indexedAt = index?.indexed_at;

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    let out = publishes.filter(p => {
      if (filters.project && p.project !== filters.project) return false;
      if (filters.entity  && p.entity  !== filters.entity)  return false;
      if (filters.task    && p.task    !== filters.task)    return false;
      if (filters.type    && p.publish_type !== filters.type) return false;
      if (filters.user    && p.created_by !== filters.user) return false;
      if (filters.flagged && !(p._warnings?.length > 0)) return false;
      if (q) {
        const hay = [
          p.entity, p.task, p.publish_type, p.project,
          ...(p.tags || []), ...(p.notes || []),
          contextLabel(p.context),
        ].join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    switch (sort) {
      case 'date-asc':     out.sort((a,b) => (a.created_at||'').localeCompare(b.created_at||'')); break;
      case 'entity':       out.sort((a,b) => a.entity.localeCompare(b.entity) || b.version - a.version); break;
      case 'version-desc': out.sort((a,b) => b.version - a.version); break;
      default:             out.sort((a,b) => (b.created_at||'').localeCompare(a.created_at||''));
    }
    return out;
  }, [filters, search, sort, publishes]);

  // keyboard
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') setSelected(null);
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        document.querySelector('.search')?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // group by entity for grid
  const grouped = useMemo(() => {
    if (view !== 'grid') return null;
    const g = new Map();
    filtered.forEach(p => {
      const key = `${p.project} / ${contextLabel(p.context)}`;
      if (!g.has(key)) g.set(key, []);
      g.get(key).push(p);
    });
    return g;
  }, [filtered, view]);

  return (
    <div className="app">
      <Topbar
        filters={filters} setFilters={setFilters}
        view={view} setView={(v) => { setView(v); setTweak('view', v); }}
        sort={sort} setSort={setSort}
        count={filtered.length} total={publishes.length}
        search={search} setSearch={setSearch}
        indexedAt={indexedAt}
        onRefresh={refresh}
        dataSource={dataSource}
        apiBase={apiBase}
        rebuilding={rebuilding}
      />

      <div className="main" data-sidebar={tweaks.showSidebar ? 'on' : 'off'} data-detail={selected ? 'on' : 'off'}>
        {tweaks.showSidebar && <Sidebar pubs={publishes} projects={projects} filters={filters} setFilters={setFilters}/>}

        <main className="content">
          {error && <div className="banner-warn"><Icon name="warn" size={12}/>{error}</div>}

          {loading ? (
            <div className="empty"><div className="empty-title">Loading index…</div></div>
          ) : filtered.length === 0 ? (
            <div className="empty">
              <div className="empty-title">No publishes match</div>
              <div className="empty-sub">Try clearing filters or changing your search.</div>
            </div>
          ) : view === 'grid' ? (
            <div className="grid-scroll">
              {[...grouped.entries()].map(([key, pubs]) => (
                <section className="group" key={key}>
                  <div className="group-head">
                    <span className="group-title">{key}</span>
                    <span className="group-count muted small">{pubs.length}</span>
                    <span className="group-rule"/>
                  </div>
                  <div className="grid">
                    {pubs.map(p => (
                      <Card key={p.uuid} pub={p} selected={selected?.uuid === p.uuid}
                            onSelect={setSelected} view="grid"/>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          ) : view === 'list' ? (
            <div className="list">
              {filtered.map(p => (
                <Card key={p.uuid} pub={p} selected={selected?.uuid === p.uuid}
                      onSelect={setSelected} view="list"/>
              ))}
            </div>
          ) : (
            <TableView pubs={filtered} selected={selected} onSelect={setSelected}/>
          )}
        </main>

        {selected && (
          <DetailPanel
            pub={selected}
            allPubs={publishes}
            onClose={() => setSelected(null)}
            onSelect={setSelected}
          />
        )}
      </div>

      <TweaksPanel title="Tweaks">
        <TweakSection title="Layout">
          <TweakRadio label="View" value={tweaks.view}
                      options={[{value:'grid',label:'Grid'},{value:'list',label:'List'},{value:'table',label:'Table'}]}
                      onChange={(v) => setTweak('view', v)}/>
          <TweakRadio label="Density" value={tweaks.density}
                      options={[{value:'compact',label:'Compact'},{value:'comfortable',label:'Cozy'}]}
                      onChange={(v) => setTweak('density', v)}/>
          <TweakToggle label="Sidebar" value={tweaks.showSidebar}
                       onChange={(v) => setTweak('showSidebar', v)}/>
        </TweakSection>
        <TweakSection title="Theme">
          <TweakColor label="Accent" value={tweaks.accent}
                      options={['#e6a455','#7ab9f7','#9be37a','#d97f7f','#b39ce6']}
                      onChange={(v) => setTweak('accent', v)}/>
        </TweakSection>
        <TweakSection title="Pipeline server">
          <TweakText label="API base" value={tweaks.apiBase}
                     onChange={(v) => setTweak('apiBase', v)}
                     placeholder="http://127.0.0.1:8765/api"/>
          <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5, padding: '4px 2px 0' }}>
            FastAPI server from <span className="mono">server.py</span>.
            Override per-tab with <span className="mono">?api=…</span>;
            force demo data with <span className="mono">?mock=1</span>;
            load a static index JSON with <span className="mono">?index=…</span>.
          </div>
        </TweakSection>
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
