/* global React, MIcon, TypeChip, StatusPill, FilterSheet, Detail, REVIEWER,
   buildReviewQueue, useReviewState, relTime */

/* ─────────────────────────────────────────────────────────────────────────
   Variation B — "Project Board"

   Supervisor's command center. Top stats summarize the day; below that,
   publishes are grouped by project → sequence/asset-type. Within a group,
   rows show entity + task + status + version. Tap → <Detail> drilldown.

   Better for a supervisor overseeing multiple projects who wants triage
   by-project rather than a single flat queue.
   ───────────────────────────────────────────────────────────────────────── */

const BoardApp = () => {
  const [filter, setFilter] = React.useState({ status: [], project: [], type: [] });
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [openUuid, setOpenUuid] = React.useState(null);
  const [collapsed, setCollapsed] = React.useState({});

  const all = React.useMemo(() => buildReviewQueue(), []);
  const { items, setStatus, addNote } = useReviewState(all);

  const projects = React.useMemo(() => [...new Set(all.map(p => p.project))], [all]);
  const types    = React.useMemo(() => [...new Set(all.map(p => p.publish_type))], [all]);

  const filtered = React.useMemo(() => items.filter(p => {
    if (filter.status.length  && !filter.status.includes(p._status)) return false;
    if (filter.project.length && !filter.project.includes(p.project)) return false;
    if (filter.type.length    && !filter.type.includes(p.publish_type)) return false;
    return true;
  }), [items, filter]);

  // Group: project → context group (sequence or asset_type).
  const groups = React.useMemo(() => {
    const byProj = new Map();
    filtered.forEach(p => {
      const subKey = p.context.type === 'shot' ? p.context.sequence : `${p.context.asset_type}s`;
      if (!byProj.has(p.project)) byProj.set(p.project, new Map());
      const subs = byProj.get(p.project);
      if (!subs.has(subKey)) subs.set(subKey, []);
      subs.get(subKey).push(p);
    });
    return byProj;
  }, [filtered]);

  const stats = React.useMemo(() => ({
    pending:  items.filter(p => p._status === 'pending').length,
    flagged:  items.filter(p => p._status === 'flagged').length,
    today:    items.filter(p => {
      const h = (Date.now() - p._ts) / 3600000;
      return h < 24;
    }).length,
  }), [items]);

  const opened = items.find(p => p.uuid === openUuid);

  return (
    <div className="m-app">
      {/* ─────────────── header ─────────────── */}
      <div className="m-header">
        <div className="m-header-row">
          <div className="m-avatar">{REVIEWER.initials}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Tuesday · 13 May
            </div>
            <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>Good morning, Max</div>
          </div>
          <button className="m-icon-btn" style={{ position: 'relative' }}>
            <MIcon name="bell"/>
            {stats.pending > 0 && (
              <span style={{
                position: 'absolute', top: 4, right: 4,
                width: 8, height: 8, borderRadius: '50%',
                background: 'var(--accent)',
              }}/>
            )}
          </button>
        </div>
      </div>

      {/* ─────────────── body ─────────────── */}
      <div className="m-scroll">
        {/* stats row */}
        <div className="m-summary" style={{ marginTop: 14 }}>
          <Stat num={stats.pending} label="Pending" tone="accent"/>
          <Stat num={stats.flagged} label="Flagged" tone="warn"/>
          <Stat num={stats.today}   label="Today"   tone="ok"/>
        </div>

        {/* filter button bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px 8px' }}>
          <div style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>By project</div>
          <button className="m-btn" data-variant="ghost" data-size="sm"
                  onClick={() => setFilterOpen(true)}>
            <MIcon name="filter" size={13}/> Filters
            {(filter.status.length + filter.project.length + filter.type.length) > 0 && (
              <span className="mono" style={{
                background: 'var(--accent)', color: '#1a1410',
                padding: '0 5px', borderRadius: 99, marginLeft: 4, fontSize: 10,
              }}>
                {filter.status.length + filter.project.length + filter.type.length}
              </span>
            )}
          </button>
        </div>

        <div className="m-board">
          {[...groups.entries()].map(([proj, subs]) => {
            const projPending = [...subs.values()].flat().filter(p => p._status === 'pending').length;
            const allInProj = [...subs.values()].flat();
            return (
              <div key={proj} className="m-board-group">
                <div className="m-board-group-head">
                  <span className="m-board-group-name">{proj}</span>
                  <span className="m-board-group-count">
                    {allInProj.length} {allInProj.length === 1 ? 'publish' : 'publishes'}
                  </span>
                  {projPending > 0 && (
                    <span className="m-status" data-s="pending" style={{ fontSize: 10.5 }}>
                      <span className="m-dot"/>{projPending}
                    </span>
                  )}
                  <span className="m-board-group-bar"/>
                </div>
                {[...subs.entries()].map(([sub, list]) => (
                  <SubGroup
                    key={sub}
                    name={sub}
                    items={list}
                    collapsed={!!collapsed[`${proj}/${sub}`]}
                    onToggle={() => setCollapsed(c => ({ ...c, [`${proj}/${sub}`]: !c[`${proj}/${sub}`] }))}
                    onOpen={(uuid) => setOpenUuid(uuid)}
                  />
                ))}
              </div>
            );
          })}
          {filtered.length === 0 && (
            <div style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--text-4)' }}>
              No publishes match this filter.
            </div>
          )}
        </div>
      </div>

      <FilterSheet open={filterOpen} onClose={() => setFilterOpen(false)}
                   value={filter} onChange={setFilter}
                   projects={projects} types={types}/>

      {opened && (
        <Detail
          pub={opened}
          onBack={() => setOpenUuid(null)}
          onAction={(status, note) => setStatus(opened.uuid, status, note)}
          onNote={(text) => addNote(opened.uuid, text)}
        />
      )}
    </div>
  );
};

const Stat = ({ num, label, tone }) => (
  <div className="m-stat">
    <div className="m-stat-num" data-tone={tone}>{num}</div>
    <div className="m-stat-label">{label}</div>
  </div>
);

const SubGroup = ({ name, items, collapsed, onToggle, onOpen }) => {
  const pendingHere = items.filter(p => p._status === 'pending').length;
  return (
    <div>
      <button onClick={onToggle} style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 16px',
        textAlign: 'left',
        color: 'var(--text-3)',
        fontSize: 11.5,
        fontFamily: 'var(--mono)',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        background: 'var(--bg-1)',
        borderTop: '1px solid var(--border)',
        borderBottom: '1px solid var(--border)',
      }}>
        <MIcon name={collapsed ? 'chevR' : 'chevD'} size={12}/>
        <span>{name}</span>
        <span style={{ color: 'var(--text-5)' }}>· {items.length}</span>
        {pendingHere > 0 && (
          <span style={{ marginLeft: 'auto', color: 'var(--accent)' }}>
            {pendingHere} pending
          </span>
        )}
      </button>
      {!collapsed && items.map(p => (
        <BoardCard key={p.uuid} pub={p} onOpen={() => onOpen(p.uuid)}/>
      ))}
    </div>
  );
};

const BoardCard = ({ pub, onOpen }) => {
  const ctxLabel = pub.context.type === 'shot' ? pub.context.shot : pub.context.asset;
  return (
    <button className="m-card" onClick={onOpen}>
      <div className="m-card-thumb">
        <img src={pub.outputs.thumbnail} alt=""/>
      </div>
      <div className="m-card-body">
        <div className="m-card-title">
          {ctxLabel} <span style={{ color: 'var(--text-4)', fontWeight: 400 }}>· {pub.task}</span>
        </div>
        <div className="m-card-sub" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <TypeChip type={pub.publish_type}/>
          <span>v{String(pub.version).padStart(3,'0')}</span>
          <span style={{ color: 'var(--text-5)' }}>·</span>
          <span>{relTime(pub.created_at)}</span>
        </div>
      </div>
      <div className="m-card-right">
        <StatusPill status={pub._status} compact/>
      </div>
    </button>
  );
};

window.BoardApp = BoardApp;
