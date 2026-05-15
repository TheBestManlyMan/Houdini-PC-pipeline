/* global React, MIcon, TypeChip, StatusPill, FilterSheet, Detail, REVIEWER,
   buildReviewQueue, useReviewState, relTime */

/* ─────────────────────────────────────────────────────────────────────────
   Variation A — "Inbox"

   Classic mobile-first newest-first list of publishes awaiting review.
   - Sticky header: avatar + "Review queue" + filter button
   - Scrollable status filter chips
   - Each row: thumb + entity/task + status pill + timeago
   - Tap row → full <Detail> drilldown for review actions
   ───────────────────────────────────────────────────────────────────────── */

const InboxApp = () => {
  const [filter, setFilter] = React.useState({
    status: ['pending', 'changes', 'flagged'], // default = needs my attention
    project: [],
    type: [],
  });
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [openUuid, setOpenUuid] = React.useState(null);
  const [quickStatus, setQuickStatus] = React.useState('all');

  const all = React.useMemo(() => buildReviewQueue(), []);
  const { items, setStatus, addNote } = useReviewState(all);

  const projects = React.useMemo(() => [...new Set(all.map(p => p.project))], [all]);
  const types    = React.useMemo(() => [...new Set(all.map(p => p.publish_type))], [all]);

  const filtered = React.useMemo(() => items.filter(p => {
    if (quickStatus === 'pending' && p._status !== 'pending') return false;
    if (quickStatus === 'flagged' && p._status !== 'flagged') return false;
    if (quickStatus === 'mine'    && !p._mentioned) return false;
    if (filter.status.length && !filter.status.includes(p._status)) return false;
    if (filter.project.length && !filter.project.includes(p.project)) return false;
    if (filter.type.length    && !filter.type.includes(p.publish_type)) return false;
    return true;
  }), [items, filter, quickStatus]);

  const pendingCount = items.filter(p => p._status === 'pending').length;

  const opened = items.find(p => p.uuid === openUuid);

  return (
    <div className="m-app">
      {/* ─────────────── header ─────────────── */}
      <div className="m-header">
        <div className="m-header-row">
          <div className="m-avatar">{REVIEWER.initials}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 16, fontWeight: 600 }}>Review queue</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-4)' }}>
              {pendingCount} awaiting · {REVIEWER.role}
            </div>
          </div>
          <button className="m-icon-btn" onClick={() => setFilterOpen(true)}>
            <MIcon name="filter"/>
          </button>
          <button className="m-icon-btn">
            <MIcon name="search"/>
          </button>
        </div>

        <div className="m-chips">
          <QuickChip active={quickStatus === 'all'}     onClick={() => setQuickStatus('all')}>All</QuickChip>
          <QuickChip active={quickStatus === 'pending'} onClick={() => setQuickStatus('pending')} accent>
            Pending <span className="mono" style={{ opacity: 0.7 }}>{pendingCount}</span>
          </QuickChip>
          <QuickChip active={quickStatus === 'flagged'} onClick={() => setQuickStatus('flagged')}>
            Flagged
          </QuickChip>
          <QuickChip active={quickStatus === 'mine'}    onClick={() => setQuickStatus('mine')}>
            @you
          </QuickChip>
          {(filter.status.length + filter.project.length + filter.type.length) > 0 && (
            <QuickChip active onClick={() => setFilterOpen(true)}>
              <MIcon name="filter" size={12}/>
              {filter.status.length + filter.project.length + filter.type.length}
            </QuickChip>
          )}
        </div>
      </div>

      {/* ─────────────── list ─────────────── */}
      <div className="m-scroll">
        <div className="m-list">
          {filtered.length === 0 && (
            <div style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--text-4)' }}>
              No publishes match this filter.
            </div>
          )}
          {filtered.map(p => (
            <InboxRow key={p.uuid} pub={p} onOpen={() => setOpenUuid(p.uuid)}/>
          ))}
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

const QuickChip = ({ active, accent, onClick, children }) => (
  <button className="m-chip" data-active={active} data-accent={accent && active} onClick={onClick}>
    {children}
  </button>
);

const InboxRow = ({ pub, onOpen }) => {
  const hasVideo = !!pub.outputs?.mp4;
  const hasGlb   = !!pub.real_glb;
  const ctxLabel = pub.context.type === 'shot'
    ? pub.context.shot
    : pub.context.asset;
  return (
    <button className="m-item" onClick={onOpen}>
      <div className="m-item-thumb">
        <img src={pub.outputs.thumbnail} alt=""/>
        {hasVideo && (
          <span className="m-play"><MIcon name="play" size={9}/></span>
        )}
        {hasGlb && (
          <span className="m-play" style={{
            background: 'var(--accent)', color: '#1a1410',
            width: 'auto', padding: '2px 6px', borderRadius: 4,
            fontSize: 9, fontWeight: 700, fontFamily: 'var(--mono)',
            letterSpacing: '0.05em',
          }}>
            3D
          </span>
        )}
      </div>
      <div className="m-item-body">
        <div className="m-item-line1">
          <span style={{ color: 'var(--text-2)' }}>{pub.project}</span>
          <span style={{ color: 'var(--text-5)' }}>/</span>
          <span>{ctxLabel}</span>
          <span style={{ marginLeft: 'auto' }}>
            <StatusPill status={pub._status} compact/>
          </span>
        </div>
        <div className="m-item-title">
          {pub.task}
          {pub._mentioned && (
            <span style={{
              marginLeft: 6, color: 'var(--accent)',
              fontSize: 11, fontWeight: 600,
            }}>@you</span>
          )}
        </div>
        <div className="m-item-meta">
          <TypeChip type={pub.publish_type}/>
          <span className="mono">v{String(pub.version).padStart(3,'0')}</span>
          <span className="m-sep">·</span>
          <span>{pub.created_by}</span>
          <span className="m-sep">·</span>
          <span>{relTime(pub.created_at)}</span>
        </div>
      </div>
    </button>
  );
};

window.InboxApp = InboxApp;
