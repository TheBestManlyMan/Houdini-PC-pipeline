/* global React */
/* ─────────────────────────────────────────────────────────────────────────
   Shared mobile primitives for the review companion app.

   - MOBILE_DATA: synthesizes review status / notes / queue from MOCK_INDEX
   - <MIcon>: small mobile icon set
   - <TypeChip>, <StatusPill>: shared chips
   - <Sheet>, <NoteSheet>, <FilterSheet>: bottom-sheet primitives
   - <Detail>: full-screen publish detail (used by all three variants)
   - <Viewer3D>: rotatable mock 3D asset viewer
   - useReviewState: shared review-status state hook across variants
   ───────────────────────────────────────────────────────────────────────── */

const { useState, useEffect, useRef, useMemo, useCallback } = React;

// ───────────────────────── reviewer / persona ─────────────────────────
const REVIEWER = { id: 'maxborg', name: 'Max Borg', role: 'FX Supervisor', initials: 'MB' };

// ───────────────────────── data layer ─────────────────────────
// Deterministic hash so review state is stable across mounts.
const hash = (s) => {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return Math.abs(h);
};

// Synthesize a review state for each publish from the mock index.
//   pending  → newest version of an entity/task, unreviewed
//   changes  → someone requested changes
//   flagged  → reviewer flagged for later
//   approved → already signed off
//   viewed   → seen but no decision
const buildReviewQueue = () => {
  const pubs = (window.MOCK_INDEX && window.MOCK_INDEX.publishes) || [];

  // Group by entity+task to find newest version per stream.
  const newestKey = new Map();
  pubs.forEach(p => {
    const k = `${p.project}/${p.entity}/${p.task}`;
    const cur = newestKey.get(k);
    if (!cur || cur.version < p.version) newestKey.set(k, p);
  });

  const sample = (seed, pool) => pool[seed % pool.length];

  const reviewPool = [
    'Looks great — approved for screening.',
    'Beautiful. Please carry this look forward.',
    'Approved. Final master locked.',
    'Lovely sim. Cleared for comp.',
  ];
  const changesPool = [
    'Voxel size too coarse around the silhouette — please bump to 0.06.',
    'Timing feels off vs. layout v005. Re-cache against layout v007?',
    'Splash secondary is reading too white. Push it warmer.',
    'Constraints popping on frame 1038–1042. Lock the breakage there.',
    'Mograph is fine but the foreground particles need more density.',
  ];
  const noteAuthors = ['jchen', 'lwakefield', 'aparker', 'rsato'];

  const items = pubs.map((p, idx) => {
    const key = `${p.project}/${p.entity}/${p.task}`;
    const isNewest = newestKey.get(key) === p;
    const seed = hash(p.uuid);

    let status = 'viewed';
    if (isNewest) {
      const roll = seed % 100;
      if (roll < 58)      status = 'pending';
      else if (roll < 72) status = 'changes';
      else if (roll < 82) status = 'flagged';
      else                status = 'approved';
    } else if ((seed % 100) < 45) {
      status = 'approved';
    } else if ((seed % 100) < 55) {
      status = 'changes';
    }

    // Activity / comments threaded onto the publish.
    const activity = [];
    if (status === 'changes') {
      activity.push({
        kind: 'changes',
        author: sample(seed, noteAuthors),
        body: sample(seed >> 2, changesPool),
        when: relTime(p.created_at, 2 + (seed % 6)),
      });
    } else if (status === 'approved') {
      activity.push({
        kind: 'approved',
        author: sample(seed, ['maxborg', 'sleigh']),
        body: sample(seed >> 2, reviewPool),
        when: relTime(p.created_at, 1 + (seed % 4)),
      });
    } else if (status === 'flagged') {
      activity.push({
        kind: 'flag',
        author: 'maxborg',
        body: 'Flagged to revisit after the layout review on Thursday.',
        when: relTime(p.created_at, 3 + (seed % 5)),
      });
    }
    // Carry over notes from the publish itself.
    (p.notes || []).forEach(n => activity.push({
      kind: 'note', author: p.created_by, body: n,
      when: relTime(p.created_at, 0),
    }));

    const isMentioned = !!(isNewest && seed % 7 === 0);

    return {
      ...p,
      _status: status,
      _activity: activity.reverse(),
      _isNewest: isNewest,
      _seed: seed,
      _mentioned: isMentioned,
      _ts: new Date(p.created_at).getTime(),
    };
  });

  // Newest first.
  items.sort((a, b) => b._ts - a._ts);
  return items;
};

const relTime = (iso, hoursOffset = 0) => {
  const then = new Date(iso).getTime() - hoursOffset * 3600 * 1000;
  const now = new Date('2026-05-13T00:21:00Z').getTime();
  const diffMin = Math.floor((now - then) / 60000);
  if (diffMin < 60)   return `${Math.max(1, diffMin)}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24)     return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7)      return `${diffD}d ago`;
  return `${Math.floor(diffD / 7)}w ago`;
};

const fmtFrames = (s, e) => (s == null || e == null || s === e) ? '—' : `${s}–${e} (${e - s + 1}f)`;

// ───────────────────────── icons ─────────────────────────
const I = ({ name, size = 18 }) => {
  const s = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round' };
  const p = {
    back:    <path d="M14 4l-7 7 7 7" {...s}/>,
    check:   <path d="M4 10l4 4 9-10" {...s}/>,
    close:   <path d="M5 5l12 12M17 5L5 17" {...s}/>,
    chevD:   <path d="M5 8l5 5 5-5" {...s}/>,
    chevR:   <path d="M7 4l6 6-6 6" {...s}/>,
    flag:    <><path d="M5 3v16" {...s}/><path d="M5 4h10l-2 3 2 3H5" {...s}/></>,
    chat:    <path d="M4 4h12a1 1 0 011 1v8a1 1 0 01-1 1H8l-4 3V5a1 1 0 011-1z" {...s}/>,
    filter:  <><path d="M3 5h14M6 10h8M9 15h2" {...s}/></>,
    search:  <><circle cx="9" cy="9" r="5" {...s}/><path d="M13 13l4 4" {...s}/></>,
    bell:    <><path d="M5 14V9a5 5 0 0110 0v5l1 2H4z" {...s}/><path d="M8 17a2 2 0 004 0" {...s}/></>,
    more:    <><circle cx="5" cy="10" r="1.2" fill="currentColor"/><circle cx="10" cy="10" r="1.2" fill="currentColor"/><circle cx="15" cy="10" r="1.2" fill="currentColor"/></>,
    play:    <path d="M6 4l10 6-10 6V4z" fill="currentColor" stroke="none"/>,
    shot:    <><rect x="2" y="5" width="11" height="10" {...s}/><path d="M13 7l5-2v10l-5-2z" {...s}/></>,
    asset:   <><path d="M10 2l7 4v8l-7 4-7-4V6z" {...s}/><path d="M3 6l7 4 7-4M10 10v8" {...s}/></>,
    download:<><path d="M10 3v10M5 9l5 4 5-4" {...s}/><path d="M3 17h14" {...s}/></>,
    link:    <><path d="M9 11l2-2m-3 5l-2 2a3 3 0 01-4-4l3-3a3 3 0 014 0" {...s}/><path d="M11 9l2-2a3 3 0 014 4l-3 3a3 3 0 01-4 0" {...s}/></>,
    cube:    <><path d="M10 2l7 4v8l-7 4-7-4V6z" {...s}/><path d="M3 6l7 4 7-4M10 10v8" {...s}/></>,
    user:    <><circle cx="10" cy="7" r="3" {...s}/><path d="M4 17a6 6 0 0112 0" {...s}/></>,
    refresh: <><path d="M16 10a6 6 0 11-2-4l2 2" {...s}/><path d="M16 3v4h-4" {...s}/></>,
    plus:    <path d="M10 4v12M4 10h12" {...s}/>,
    sort:    <><path d="M5 6h10M5 10h7M5 14h4" {...s}/></>,
    flame:   <path d="M10 3c1 3 4 4 4 8a4 4 0 01-8 0c0-2 1-3 2-3-1-2 1-4 2-5z" {...s}/>,
    expand:  <><path d="M3 8V3h5" {...s}/><path d="M17 8V3h-5" {...s}/><path d="M3 12v5h5" {...s}/><path d="M17 12v5h-5" {...s}/></>,
    minimize:<><path d="M8 3v5H3" {...s}/><path d="M12 3v5h5" {...s}/><path d="M8 17v-5H3" {...s}/><path d="M12 17v-5h5" {...s}/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 20 20" style={{ display: 'block', flexShrink: 0 }}>{p[name]}</svg>;
};

// ───────────────────────── shared chips ─────────────────────────
const TypeChip = ({ type }) => <span className="m-type" data-t={type}>{type}</span>;

// ──────────────────────── fullscreen helper ────────────────────────
// Native Fullscreen API toggle for any element holding a viewable.
const toggleFullscreen = (el) => {
  if (!el) return;
  if (!document.fullscreenElement) {
    (el.requestFullscreen?.() ?? el.webkitRequestFullscreen?.());
  } else {
    (document.exitFullscreen?.() ?? document.webkitExitFullscreen?.());
  }
};

const useFullscreen = () => {
  const ref = React.useRef(null);
  const [isFs, setIsFs] = React.useState(false);
  React.useEffect(() => {
    const onChange = () => setIsFs(document.fullscreenElement === ref.current);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);
  return { ref, isFs, toggle: () => toggleFullscreen(ref.current) };
};

const FsButton = ({ isFs, onClick, style }) => (
  <button className="m-fs-btn"
          onClick={(e) => { e.stopPropagation(); onClick(); }}
          title={isFs ? 'Exit fullscreen' : 'Fullscreen'}
          style={style}>
    <I name={isFs ? 'minimize' : 'expand'} size={14}/>
  </button>
);

const StatusPill = ({ status, compact }) => {
  const labels = { pending: 'Pending', approved: 'Approved', changes: 'Changes', flagged: 'Flagged', viewed: 'Viewed' };
  return (
    <span className="m-status" data-s={status}>
      <span className="m-dot"/>
      {compact ? null : labels[status]}
    </span>
  );
};

// ───────────────────────── review state hook ─────────────────────────
// Shared across all three variants so demo changes feel "real".
const useReviewState = (items) => {
  const [overrides, setOverrides] = useState({}); // uuid → { status, notes:[] }

  const apply = (item) => {
    const o = overrides[item.uuid];
    if (!o) return item;
    return {
      ...item,
      _status: o.status ?? item._status,
      _activity: o.notes ? [...o.notes, ...item._activity] : item._activity,
    };
  };

  const setStatus = (uuid, status, note) => {
    setOverrides(p => {
      const prev = p[uuid] || {};
      const notes = note
        ? [{ kind: status === 'approved' ? 'approved' : status === 'changes' ? 'changes' : status === 'flagged' ? 'flag' : 'note',
             author: REVIEWER.id, body: note, when: 'Just now', _mine: true }, ...(prev.notes || [])]
        : prev.notes;
      return { ...p, [uuid]: { ...prev, status, notes } };
    });
  };

  const addNote = (uuid, note) => {
    setOverrides(p => {
      const prev = p[uuid] || {};
      return { ...p, [uuid]: { ...prev, notes: [
        { kind: 'note', author: REVIEWER.id, body: note, when: 'Just now', _mine: true },
        ...(prev.notes || [])
      ] } };
    });
  };

  return { items: items.map(apply), setStatus, addNote };
};

// ───────────────────────── bottom sheet ─────────────────────────
const Sheet = ({ open, onClose, title, children }) => {
  if (!open) return null;
  return (
    <>
      <div className="m-sheet-backdrop" onClick={onClose}/>
      <div className="m-sheet">
        <div className="m-sheet-grab"/>
        {title && <div className="m-sheet-title">{title}</div>}
        {children}
      </div>
    </>
  );
};

// Sheet for entering a note before approving / requesting changes / etc.
const NoteSheet = ({ open, onClose, onSubmit, mode }) => {
  const [text, setText] = useState('');
  useEffect(() => { if (open) setText(''); }, [open]);
  const titles = {
    approve: 'Approve publish',
    changes: 'Request changes',
    flag:    'Flag for later',
    note:    'Add a note',
  };
  const placeholders = {
    approve: 'Optional note for the team…',
    changes: 'What needs to change?',
    flag:    'Why are you flagging this?',
    note:    'Leave a note…',
  };
  const ctaLabel = {
    approve: 'Approve',
    changes: 'Send changes',
    flag:    'Flag',
    note:    'Post note',
  };
  const ctaVariant = {
    approve: 'approve', changes: 'changes', flag: 'flag', note: '',
  };
  return (
    <Sheet open={open} onClose={onClose} title={titles[mode]}>
      <textarea
        className="m-sheet-textarea"
        placeholder={placeholders[mode]}
        value={text}
        onChange={(e) => setText(e.target.value)}
        autoFocus
      />
      <div className="m-sheet-actions">
        <button className="m-btn" data-variant="ghost" style={{ flex: 1 }} onClick={onClose}>Cancel</button>
        <button className="m-btn" data-variant={ctaVariant[mode]} style={{ flex: 2 }}
                onClick={() => { onSubmit(text.trim()); onClose(); }}
                disabled={mode === 'changes' && !text.trim()}>
          {ctaLabel[mode]}
        </button>
      </div>
    </Sheet>
  );
};

// ───────────────────────── filter sheet ─────────────────────────
const FilterSheet = ({ open, onClose, value, onChange, projects, types }) => {
  const toggle = (group, v) => {
    const cur = value[group] || [];
    const next = cur.includes(v) ? cur.filter(x => x !== v) : [...cur, v];
    onChange({ ...value, [group]: next });
  };
  const STATUSES = [
    ['pending', 'Pending'], ['changes', 'Changes'], ['flagged', 'Flagged'],
    ['approved', 'Approved'], ['viewed', 'Viewed'],
  ];
  return (
    <Sheet open={open} onClose={onClose} title="Filters">
      <div style={{ overflowY: 'auto', flex: 1, paddingBottom: 8 }}>
        <FilterGroup label="Status">
          {STATUSES.map(([k, label]) => (
            <FilterChip key={k} active={(value.status || []).includes(k)} onClick={() => toggle('status', k)}>
              <StatusPill status={k} compact/>
              <span style={{ marginLeft: 4 }}>{label}</span>
            </FilterChip>
          ))}
        </FilterGroup>
        <FilterGroup label="Project">
          {projects.map(p => (
            <FilterChip key={p} active={(value.project || []).includes(p)} onClick={() => toggle('project', p)}>
              {p}
            </FilterChip>
          ))}
        </FilterGroup>
        <FilterGroup label="Publish type">
          {types.map(t => (
            <FilterChip key={t} active={(value.type || []).includes(t)} onClick={() => toggle('type', t)}>
              <TypeChip type={t}/>
            </FilterChip>
          ))}
        </FilterGroup>
      </div>
      <div className="m-sheet-actions" style={{ marginTop: 8 }}>
        <button className="m-btn" data-variant="ghost" style={{ flex: 1 }}
                onClick={() => onChange({ status: [], project: [], type: [] })}>
          Clear all
        </button>
        <button className="m-btn" data-variant="approve" style={{ flex: 2 }} onClick={onClose}>
          Apply
        </button>
      </div>
    </Sheet>
  );
};
const FilterGroup = ({ label, children }) => (
  <div style={{ marginBottom: 16 }}>
    <div className="m-kv-label" style={{ marginBottom: 8 }}>{label}</div>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>{children}</div>
  </div>
);
const FilterChip = ({ active, onClick, children }) => (
  <button className="m-chip" data-active={active} onClick={onClick} style={{ minHeight: 32 }}>
    {children}
  </button>
);

// ───────────────────────── 3D viewer (mock) ─────────────────────────
// CSS-3D rotating wireframe object. Drag to spin. Looks like a placeholder
// for a real WebGL viewer.
const Viewer3D = ({ entity = 'asset', hue = 35 }) => {
  const [rx, setRx] = useState(-20);
  const [ry, setRy] = useState(35);
  const [autoSpin, setAutoSpin] = useState(true);
  const dragging = useRef(false);
  const last = useRef({ x: 0, y: 0 });

  useEffect(() => {
    if (!autoSpin) return;
    let raf, prev = performance.now();
    const tick = (t) => {
      const dt = (t - prev) / 1000; prev = t;
      setRy(r => r + dt * 24);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [autoSpin]);

  const onDown = (e) => {
    dragging.current = true; setAutoSpin(false);
    const pt = e.touches ? e.touches[0] : e;
    last.current = { x: pt.clientX, y: pt.clientY };
  };
  const onMove = (e) => {
    if (!dragging.current) return;
    const pt = e.touches ? e.touches[0] : e;
    setRy(v => v + (pt.clientX - last.current.x) * 0.5);
    setRx(v => Math.max(-80, Math.min(80, v - (pt.clientY - last.current.y) * 0.5)));
    last.current = { x: pt.clientX, y: pt.clientY };
  };
  const onUp = () => { dragging.current = false; };

  // Build 12 edges of a cube as div lines plus an inner octahedron for variety.
  const lineColor = `oklch(72% 0.14 ${hue})`;
  const accent    = `oklch(85% 0.16 ${hue})`;
  const size = 110;

  const edges = [
    // bottom square
    { x:0, y:size/2,  z:0,   rx:0, ry:0, len: size, axis: 'x' },
    { x:0, y:size/2,  z:size/2, rx:0, ry:90, len: size, axis: 'x' },
    { x:0, y:size/2,  z:-size/2,rx:0, ry:90, len: size, axis: 'x' },
    { x:size/2, y:size/2,  z:0, rx:0, ry:0, len: size, axis: 'z' },
    { x:-size/2,y:size/2,  z:0, rx:0, ry:0, len: size, axis: 'z' },
    // top square
    { x:0, y:-size/2, z:0,   rx:0, ry:0, len: size, axis: 'x' },
    { x:0, y:-size/2, z:size/2, rx:0, ry:90, len: size, axis: 'x' },
    { x:0, y:-size/2, z:-size/2,rx:0, ry:90, len: size, axis: 'x' },
    { x:size/2, y:-size/2, z:0, rx:0, ry:0, len: size, axis: 'z' },
    { x:-size/2,y:-size/2, z:0, rx:0, ry:0, len: size, axis: 'z' },
    // verticals
    { x:size/2,  y:0, z:size/2,  rx:90, ry:0, len: size, axis: 'y' },
    { x:size/2,  y:0, z:-size/2, rx:90, ry:0, len: size, axis: 'y' },
    { x:-size/2, y:0, z:size/2,  rx:90, ry:0, len: size, axis: 'y' },
    { x:-size/2, y:0, z:-size/2, rx:90, ry:0, len: size, axis: 'y' },
  ];

  const edgeStyle = (e) => {
    let rot = '';
    if (e.axis === 'x') rot = `rotateY(${e.ry}deg)`;
    if (e.axis === 'y') rot = `rotateZ(90deg)`;
    if (e.axis === 'z') rot = `rotateY(90deg) rotateZ(90deg)`;
    return {
      position: 'absolute',
      left: '50%', top: '50%',
      width: e.len, height: 1,
      background: lineColor,
      boxShadow: `0 0 8px ${lineColor}`,
      transform: `translate3d(${e.x - e.len/2}px, ${e.y}px, ${e.z}px) ${rot}`,
      transformOrigin: 'center',
    };
  };

  return (
    <div className="m-3d"
         onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}
         onTouchStart={onDown} onTouchMove={onMove} onTouchEnd={onUp}>
      <div className="m-3d-grid"/>
      <div className="m-3d-toolbar">
        <span className="pill mono">{entity}.usd</span>
        <span className="pill mono">{Math.round(ry % 360)}° / {Math.round(rx)}°</span>
      </div>
      <div className="m-3d-stage" style={{ transform: `rotateX(${rx}deg) rotateY(${ry}deg)` }}>
        {edges.map((e, i) => <div key={i} style={edgeStyle(e)}/>)}
        {/* center point */}
        <div style={{
          position: 'absolute', left: '50%', top: '50%',
          width: 6, height: 6, marginLeft: -3, marginTop: -3,
          background: accent, borderRadius: '50%',
          boxShadow: `0 0 10px ${accent}`,
        }}/>
        {/* axis pip */}
        <div style={{
          position: 'absolute', left: '50%', top: '50%',
          width: 30, height: 1, background: accent,
          transform: 'translateX(0)',
        }}/>
      </div>
      <div className="m-3d-hint">drag to rotate · proxy mesh</div>
    </div>
  );
};

// ───────────────────────── detail view (shared) ─────────────────────────
// Full-screen drilldown reused by all three variants.
const Detail = ({ pub, onBack, onAction, onNote }) => {
  const hasGlb   = !!pub.real_glb;
  const has3D    = pub.publish_type === 'usd' || hasGlb;
  // Default to the 3D tab when we have a real GLB — the whole point of the
  // drilldown for those publishes is the live model preview.
  const [tab, setTab] = useState(hasGlb ? '3d' : 'preview');
  const [scrub, setScrub] = useState(null);
  const [sheet, setSheet] = useState(null); // 'approve' | 'changes' | 'flag' | 'note' | null

  const hasVideo = !!pub.outputs?.mp4;
  const fs = pub.stats?.frame_start;
  const fe = pub.stats?.frame_end;
  const frames = (fs && fe) ? (fe - fs + 1) : 0;

  const onScrub = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const pt = e.touches ? e.touches[0] : e;
    const pct = Math.max(0, Math.min(1, (pt.clientX - r.left) / r.width));
    setScrub(Math.floor(pct * Math.max(1, frames - 1)));
  };

  // entity / context label
  const ctxLabel = pub.context.type === 'shot'
    ? `${pub.context.sequence} · ${pub.context.shot}`
    : `${pub.context.asset_type} · ${pub.context.asset}`;

  return (
    <div className="m-detail">
      <div className="m-detail-header">
        <button className="m-icon-btn" onClick={onBack}><I name="back"/></button>
        <div className="m-detail-title">
          <div className="m-detail-title-name">{pub.entity} · {pub.task}</div>
          <div className="m-detail-title-sub">{pub.project} · v{String(pub.version).padStart(3,'0')}</div>
        </div>
        <button className="m-icon-btn"><I name="link"/></button>
        <button className="m-icon-btn"><I name="more"/></button>
      </div>

      {tab === 'preview' && (
        <FsHero pub={pub} scrub={scrub} onScrub={frames ? onScrub : undefined} fs={fs} fe={fe} frames={frames}/>
      )}
      {tab === '3d' && has3D && (
        <FsThreeD pub={pub} hasGlb={hasGlb}/>
      )}

      <div className="m-detail-tabs">
        <button className="m-detail-tab" data-active={tab === 'preview'} onClick={() => setTab('preview')}>Preview</button>
        {has3D && <button className="m-detail-tab" data-active={tab === '3d'} onClick={() => setTab('3d')}>3D</button>}
        <button className="m-detail-tab" data-active={tab === 'info'} onClick={() => setTab('info')}>Info</button>
        <button className="m-detail-tab" data-active={tab === 'notes'} onClick={() => setTab('notes')}>
          Notes {pub._activity?.length ? <span className="muted" style={{ color: 'var(--text-4)' }}>· {pub._activity.length}</span> : null}
        </button>
      </div>

      <div className="m-detail-body">
        {tab === 'preview' && <PreviewTab pub={pub} ctxLabel={ctxLabel}/>}
        {tab === '3d'      && <ThreeDTab  pub={pub}/>}
        {tab === 'info'    && <InfoTab    pub={pub} ctxLabel={ctxLabel}/>}
        {tab === 'notes'   && <NotesTab   pub={pub} onCompose={() => setSheet('note')}/>}
      </div>

      <div className="m-detail-actions">
        <button className="m-btn" data-variant="approve" onClick={() => setSheet('approve')}>
          <I name="check" size={16}/> Approve
        </button>
        <button className="m-btn" data-variant="changes" onClick={() => setSheet('changes')}>
          <I name="chat" size={16}/> Changes
        </button>
        <button className="m-btn" data-variant="flag" data-size="icon" onClick={() => setSheet('flag')}>
          <I name="flag" size={16}/>
        </button>
      </div>

      <NoteSheet
        open={!!sheet}
        mode={sheet}
        onClose={() => setSheet(null)}
        onSubmit={(text) => {
          if (sheet === 'approve') onAction('approved', text || null);
          if (sheet === 'changes') onAction('changes',  text || null);
          if (sheet === 'flag')    onAction('flagged',  text || null);
          if (sheet === 'note')    onNote(text);
        }}
      />
    </div>
  );
};

// ─── FS wrappers used inside <Detail> for hero + 3D ───
const FsHero = ({ pub, scrub, onScrub, fs, fe, frames }) => {
  const { ref, isFs, toggle } = useFullscreen();
  return (
    <div className="m-detail-hero" ref={ref}
         onTouchStart={onScrub ? (e) => onScrub(e) : undefined}
         onTouchMove={onScrub ? (e) => onScrub(e) : undefined}>
      <img src={pub.outputs.thumbnail} alt=""/>
      <div className="m-detail-hero-overlay">
        <span><TypeChip type={pub.publish_type}/></span>
        <span>F {scrub != null ? (fs + scrub) : fs} / {fe} · {frames} frames</span>
      </div>
      <FsButton isFs={isFs} onClick={toggle}/>
    </div>
  );
};

const FsThreeD = ({ pub, hasGlb }) => {
  const { ref, isFs, toggle } = useFullscreen();
  return (
    <div className="m-3d-fs-wrap" ref={ref}>
      {hasGlb
        ? <GlbViewer src={pub.real_glb} entity={pub.entity}/>
        : <div style={{ padding: 12, background: '#000' }}>
            <Viewer3D entity={pub.entity} hue={35 + (pub._seed % 60)}/>
          </div>}
      <FsButton isFs={isFs} onClick={toggle}/>
    </div>
  );
};

const PreviewTab = ({ pub, ctxLabel }) => {
  const fs = pub.stats?.frame_start, fe = pub.stats?.frame_end;
  return (
    <>
      <div className="m-kv-block">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <StatusPill status={pub._status}/>
          <TypeChip type={pub.publish_type}/>
          {pub._mentioned && (
            <span className="m-chip" data-accent="true" style={{ padding: '2px 8px', fontSize: 11 }}>
              @you
            </span>
          )}
        </div>
        <div style={{ fontSize: 17, fontWeight: 600, marginBottom: 4 }}>
          {pub.entity} <span style={{ color: 'var(--text-4)' }}>·</span> {pub.task}
        </div>
        <div className="mono" style={{ fontSize: 12.5, color: 'var(--text-3)' }}>
          {pub.project} · {ctxLabel} · v{String(pub.version).padStart(3,'0')}
        </div>
      </div>

      {pub.notes?.length > 0 && (
        <div className="m-kv-block">
          <div className="m-kv-label">Latest publisher note</div>
          <div className="m-note-card">
            <div className="m-note-head"><span>{pub.created_by}</span><span>{relTime(pub.created_at)}</span></div>
            <div className="m-note-body">{pub.notes[0]}</div>
          </div>
        </div>
      )}

      <div className="m-kv-block">
        <div className="m-kv-label">Quick info</div>
        <div className="m-kv-row"><span className="k">frames</span><span className="v">{fmtFrames(fs, fe)}</span></div>
        <div className="m-kv-row"><span className="k">size</span><span className="v">{pub.stats?.disk_mb} MB</span></div>
        <div className="m-kv-row"><span className="k">published</span><span className="v">{pub.created_by} · {relTime(pub.created_at)}</span></div>
        {pub.wedge && <div className="m-kv-row"><span className="k">wedge</span><span className="v">{pub.wedge.parameter} = {pub.wedge.value}</span></div>}
      </div>

      {pub.dependencies?.length > 0 && (
        <div className="m-kv-block">
          <div className="m-kv-label">Dependencies</div>
          {pub.dependencies.map((d, i) => (
            <div key={i} className="m-kv-row">
              <span className="k">{d.type}</span>
              <span className="v">{d.publish_uuid.slice(0, 12)}…</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
};

const ThreeDTab = ({ pub }) => {
  const hasGlb = !!pub.real_glb;
  return (
    <>
      <div className="m-kv-block">
        <div className="m-kv-label">{hasGlb ? 'GLB preview' : 'USD payload'}</div>
        <div className="m-kv-row"><span className="k">prim</span><span className="v">/world/{pub.entity}</span></div>
        <div className="m-kv-row">
          <span className="k">file</span>
          <span className="v">
            {hasGlb
              ? pub.outputs.glb.split('/').pop()
              : (pub.outputs?.usd ? pub.outputs.usd.split('/').pop() : '—')}
          </span>
        </div>
        <div className="m-kv-row"><span className="k">size</span><span className="v">{pub.stats?.disk_mb} MB</span></div>
        {hasGlb && (
          <div className="m-kv-row">
            <span className="k">source</span>
            <span className="v">live preview · raw.githubusercontent.com</span>
          </div>
        )}
      </div>
      <div className="m-kv-block">
        <div className="m-kv-label">Variants</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {['proxy', 'hero', 'render'].map(v => (
            <span key={v} className="m-chip" data-active={v === 'proxy'} style={{ fontSize: 12 }}>{v}</span>
          ))}
        </div>
      </div>
    </>
  );
};

// ─────────────── real GLB viewer (via <model-viewer>) ───────────────
const GlbViewer = ({ src, entity }) => {
  const ref = React.useRef(null);
  const [progress, setProgress] = React.useState(0);
  const [ready, setReady] = React.useState(false);
  const [err, setErr] = React.useState(null);

  React.useEffect(() => {
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
    <div className="m-glb-wrap">
      <model-viewer
        ref={ref}
        src={src}
        camera-controls
        touch-action="pan-y"
        interaction-prompt="none"
        shadow-intensity="1.1"
        exposure="0.95"
        environment-image="neutral"
        camera-orbit="35deg 75deg auto"
        field-of-view="32deg"
        style={{
          width: '100%', height: '100%',
          background: 'radial-gradient(ellipse at center, oklch(22% 0.01 250), oklch(10% 0.004 250))',
          '--poster-color': 'transparent',
        }}
      />
      <div className="m-glb-toolbar">
        <span className="pill mono">{entity}.glb</span>
        <span className="pill mono">{ready ? 'loaded' : (err ? 'error' : `${progress}%`)}</span>
      </div>
      {!ready && !err && (
        <div className="m-glb-loading">
          <div className="m-glb-spinner"/>
          <div className="mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>
            Streaming GLB · {progress}%
          </div>
        </div>
      )}
      {err && (
        <div className="m-glb-error">
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Couldn’t load model</div>
          <div className="mono" style={{ fontSize: 11, color: 'var(--text-4)' }}>{err}</div>
        </div>
      )}
      <div className="m-3d-hint">pinch to zoom · drag to orbit · two-finger to pan</div>
    </div>
  );
};

const InfoTab = ({ pub, ctxLabel }) => (
  <>
    <div className="m-kv-block">
      <div className="m-kv-label">Identity</div>
      <div className="m-kv-row"><span className="k">project</span><span className="v">{pub.project}</span></div>
      <div className="m-kv-row"><span className="k">context</span><span className="v">{ctxLabel}</span></div>
      <div className="m-kv-row"><span className="k">entity</span><span className="v">{pub.entity}</span></div>
      <div className="m-kv-row"><span className="k">task</span><span className="v">{pub.task}</span></div>
      <div className="m-kv-row"><span className="k">type</span><span className="v">{pub.publish_type}</span></div>
      <div className="m-kv-row"><span className="k">version</span><span className="v">v{String(pub.version).padStart(3,'0')}</span></div>
      <div className="m-kv-row"><span className="k">uuid</span><span className="v">{pub.uuid}</span></div>
    </div>
    <div className="m-kv-block">
      <div className="m-kv-label">Outputs</div>
      {pub.outputs?.mp4    && <div className="m-kv-row"><span className="k">mp4</span><span className="v">preview.mp4</span></div>}
      {pub.outputs?.frames && <div className="m-kv-row"><span className="k">frames</span><span className="v">{pub.outputs.frames.split('/').pop()}</span></div>}
      {pub.outputs?.cache  && <div className="m-kv-row"><span className="k">cache</span><span className="v">{pub.outputs.cache.split('/').pop()}</span></div>}
      {pub.outputs?.usd    && <div className="m-kv-row"><span className="k">usd</span><span className="v">{pub.outputs.usd.split('/').pop()}</span></div>}
    </div>
    <div className="m-kv-block">
      <div className="m-kv-label">Source</div>
      <div className="m-kv-row"><span className="k">hip</span><span className="v">{pub.source?.hip?.split('/').pop()}</span></div>
      {pub.source?.rop && <div className="m-kv-row"><span className="k">rop</span><span className="v">{pub.source.rop}</span></div>}
      <div className="m-kv-row"><span className="k">houdini</span><span className="v">{pub.source?.houdini_version}</span></div>
      <div className="m-kv-row"><span className="k">commit</span><span className="v">{pub.source?.git_commit}</span></div>
    </div>
    {pub.tags?.length > 0 && (
      <div className="m-kv-block">
        <div className="m-kv-label">Tags</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {pub.tags.map(t => <span key={t} className="m-chip" style={{ fontSize: 11 }}>{t}</span>)}
        </div>
      </div>
    )}
    {pub._warnings?.length > 0 && (
      <div className="m-kv-block">
        <div className="m-kv-label">Warnings</div>
        {pub._warnings.map((w, i) => (
          <div key={i} style={{
            fontSize: 12.5, color: 'var(--warn)',
            padding: '6px 0', display: 'flex', gap: 6, alignItems: 'center',
          }}>
            <I name="flag" size={14}/> {w}
          </div>
        ))}
      </div>
    )}
  </>
);

const NotesTab = ({ pub, onCompose }) => (
  <>
    <button className="m-btn" data-variant="ghost"
            style={{ width: '100%', marginBottom: 14, height: 40 }}
            onClick={onCompose}>
      <I name="chat" size={14}/> Add a note
    </button>
    {(pub._activity || []).length === 0 && (
      <div style={{ color: 'var(--text-4)', fontSize: 13, textAlign: 'center', padding: '20px 0' }}>
        No activity yet.
      </div>
    )}
    {(pub._activity || []).map((a, i) => (
      <div key={i} className={`m-note-card ${a._mine ? 'm-note-mine' : ''}`}>
        <div className="m-note-head">
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              width: 18, height: 18, borderRadius: '50%',
              background: a.kind === 'approved' ? 'color-mix(in oklch, var(--ok) 30%, var(--bg-3))'
                       : a.kind === 'changes'  ? 'color-mix(in oklch, var(--danger) 30%, var(--bg-3))'
                       : a.kind === 'flag'     ? 'color-mix(in oklch, var(--warn) 30%, var(--bg-3))'
                       : 'var(--bg-3)',
              color: a.kind === 'approved' ? 'var(--ok)'
                   : a.kind === 'changes'  ? 'oklch(78% 0.16 25)'
                   : a.kind === 'flag'     ? 'var(--warn)'
                   : 'var(--text-3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <I name={a.kind === 'approved' ? 'check'
                     : a.kind === 'changes'  ? 'chat'
                     : a.kind === 'flag'     ? 'flag'
                     : 'chat'} size={10}/>
            </span>
            {a.author}
          </span>
          <span>{a.when}</span>
        </div>
        <div className="m-note-body">{a.body}</div>
      </div>
    ))}
  </>
);

Object.assign(window, {
  // primitives
  MIcon: I, TypeChip, StatusPill,
  Sheet, NoteSheet, FilterSheet, FilterGroup, FilterChip,
  Viewer3D, GlbViewer, Detail, REVIEWER,
  FsButton, useFullscreen, toggleFullscreen,
  // hooks / data
  buildReviewQueue, useReviewState, relTime, fmtFrames,
});
