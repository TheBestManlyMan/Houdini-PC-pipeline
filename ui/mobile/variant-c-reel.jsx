/* global React, MIcon, TypeChip, StatusPill, NoteSheet, Detail, REVIEWER,
   buildReviewQueue, useReviewState, relTime, fmtFrames */

/* ─────────────────────────────────────────────────────────────────────────
   Variation C — "Reel"

   Detail-first, full-bleed, scroll-snap pager. Each pending publish is its
   own page: big media on top, metadata + latest note in the middle, action
   bar pinned to the bottom. Designed for a supervisor blowing through
   today's pendings on the train.

   Tapping the page does nothing (the actions are explicit). Scrolling
   vertically snaps to the next item.
   ───────────────────────────────────────────────────────────────────────── */

const ReelApp = () => {
  const all = React.useMemo(() => buildReviewQueue(), []);
  const { items, setStatus, addNote } = useReviewState(all);

  // Queue = anything still awaiting attention. After acting on an item we
  // keep it visible (status pill updates) so the user can see what they did.
  const queue = React.useMemo(
    () => items.filter(p => ['pending', 'changes', 'flagged', 'approved'].includes(p._status)
                          && p._isNewest),
    [items]
  );

  const [idx, setIdx] = React.useState(0);
  const [sheet, setSheet] = React.useState(null);
  const [openDetail, setOpenDetail] = React.useState(false);
  const scrollerRef = React.useRef(null);

  const cur = queue[idx];

  const onScroll = (e) => {
    const i = Math.round(e.target.scrollTop / e.target.clientHeight);
    if (i !== idx) setIdx(i);
  };

  return (
    <div className="m-app">
      {/* ─────────────── reel pager ─────────────── */}
      <div className="m-reel" ref={scrollerRef} onScroll={onScroll}>
        {queue.map((p, i) => (
          <ReelPage
            key={p.uuid}
            pub={p}
            idx={i}
            total={queue.length}
            onOpenSheet={(m) => setSheet({ mode: m, uuid: p.uuid })}
            onOpenDetail={() => setOpenDetail(true)}
          />
        ))}
      </div>

      <NoteSheet
        open={!!sheet}
        mode={sheet?.mode}
        onClose={() => setSheet(null)}
        onSubmit={(text) => {
          if (!sheet) return;
          if (sheet.mode === 'approve') setStatus(sheet.uuid, 'approved', text || null);
          if (sheet.mode === 'changes') setStatus(sheet.uuid, 'changes',  text || null);
          if (sheet.mode === 'flag')    setStatus(sheet.uuid, 'flagged',  text || null);
          if (sheet.mode === 'note')    addNote(sheet.uuid, text);
        }}
      />

      {openDetail && cur && (
        <Detail
          pub={cur}
          onBack={() => setOpenDetail(false)}
          onAction={(status, note) => setStatus(cur.uuid, status, note)}
          onNote={(text) => addNote(cur.uuid, text)}
        />
      )}
    </div>
  );
};

const ReelPage = ({ pub, idx, total, onOpenSheet, onOpenDetail }) => {
  const hasVideo = !!pub.outputs?.mp4;
  const fs = pub.stats?.frame_start, fe = pub.stats?.frame_end;
  const frames = (fs && fe) ? (fe - fs + 1) : 0;
  const ctxLabel = pub.context.type === 'shot'
    ? `${pub.context.sequence} · ${pub.context.shot}`
    : `${pub.context.asset_type} · ${pub.context.asset}`;
  const lastNote = pub._activity?.[0];

  // Synthetic scrub fill for the bottom progress thingy.
  const fillPct = 35 + (pub._seed % 50);

  return (
    <div className="m-reel-page">
      {/* media */}
      <div className="m-reel-media" onClick={onOpenDetail}>
        <img src={pub.outputs.thumbnail} alt=""/>
        <div className="m-reel-media-overlay">
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <div className="m-avatar" style={{ width: 28, height: 28, fontSize: 11 }}>{REVIEWER.initials}</div>
            <div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)', fontFamily: 'var(--mono)' }}>Reviewing as</div>
              <div style={{ fontSize: 12.5, color: '#fff', fontWeight: 500 }}>{REVIEWER.name}</div>
            </div>
          </div>
          <span className="m-reel-page-counter mono">
            {idx + 1}/{total}
          </span>
        </div>
        {hasVideo && frames > 1 && (
          <div className="m-reel-scrubber">
            <span>F {fs}</span>
            <div className="m-reel-scrub-track">
              <div className="m-reel-scrub-fill" style={{ width: `${fillPct}%` }}/>
            </div>
            <span>{fe}</span>
          </div>
        )}
        {!hasVideo && (
          <div className="m-reel-scrubber" style={{ justifyContent: 'flex-end' }}>
            <span style={{ background: 'rgba(0,0,0,0.5)', padding: '3px 8px', borderRadius: 99 }}>
              {pub.publish_type === 'usd' ? 'STILL · USD' : 'STILL'}
            </span>
          </div>
        )}
      </div>

      {/* body */}
      <div className="m-reel-body">
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
          <StatusPill status={pub._status}/>
          <TypeChip type={pub.publish_type}/>
          {pub._mentioned && (
            <span className="m-chip" data-accent="true" style={{ padding: '2px 8px', fontSize: 11 }}>
              @you
            </span>
          )}
        </div>
        <div className="m-reel-title-row">
          <div>
            <div className="m-reel-title">
              {pub.entity}
              <span style={{ color: 'var(--text-4)', fontWeight: 400 }}> · {pub.task}</span>
            </div>
            <div className="m-reel-meta" style={{ marginTop: 4 }}>
              {pub.project} · {ctxLabel} · v{String(pub.version).padStart(3,'0')}
            </div>
          </div>
        </div>

        <div style={{
          display: 'flex', gap: 16, marginTop: 12,
          fontSize: 12, color: 'var(--text-3)',
        }}>
          <div>
            <div style={{ color: 'var(--text-5)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              By
            </div>
            <div style={{ fontFamily: 'var(--mono)' }}>{pub.created_by}</div>
          </div>
          <div>
            <div style={{ color: 'var(--text-5)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              When
            </div>
            <div style={{ fontFamily: 'var(--mono)' }}>{relTime(pub.created_at)}</div>
          </div>
          {frames > 0 && (
            <div>
              <div style={{ color: 'var(--text-5)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Frames
              </div>
              <div style={{ fontFamily: 'var(--mono)' }}>{frames}f</div>
            </div>
          )}
          <div>
            <div style={{ color: 'var(--text-5)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Size
            </div>
            <div style={{ fontFamily: 'var(--mono)' }}>{pub.stats?.disk_mb} MB</div>
          </div>
        </div>

        {lastNote && (
          <div className="m-reel-notes">
            <div className="m-reel-notes-author">
              {lastNote.author === REVIEWER.id ? 'You' : lastNote.author} · {lastNote.when}
            </div>
            <div>{lastNote.body}</div>
          </div>
        )}

        <button className="m-btn" data-variant="ghost"
                style={{ width: '100%', marginTop: 12, height: 38, fontSize: 13 }}
                onClick={onOpenDetail}>
          Open full detail
          <MIcon name="chevR" size={13}/>
        </button>
      </div>

      {/* action bar */}
      <div className="m-reel-actions">
        <button className="m-btn" data-variant="approve" onClick={() => onOpenSheet('approve')}>
          <MIcon name="check" size={16}/> Approve
        </button>
        <button className="m-btn" data-variant="changes" onClick={() => onOpenSheet('changes')}>
          <MIcon name="chat" size={16}/> Changes
        </button>
        <button className="m-btn" data-variant="flag" onClick={() => onOpenSheet('flag')}>
          <MIcon name="flag" size={16}/> Flag
        </button>
      </div>
    </div>
  );
};

window.ReelApp = ReelApp;
