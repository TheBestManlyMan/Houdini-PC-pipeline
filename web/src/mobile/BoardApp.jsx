import React from 'react'
import '../styles/mobile.css'
import { usePublishes } from '../hooks/usePublishes.js'
import {
  MIcon, TypeChip, StatusPill, FilterSheet, Detail, REVIEWER,
  buildReviewQueue, useReviewState, relTime,
  pubProductType, pubDate, pubThumbnail,
} from './shared.jsx'

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function headerDate() {
  const d = new Date()
  return `${DAY_NAMES[d.getDay()]} · ${d.getDate()} ${MONTH_NAMES[d.getMonth()]}`
}

function greeting() {
  const h = new Date().getHours()
  const salutation = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
  return `${salutation}, ${REVIEWER.name.split(' ')[0]}`
}

export default function BoardApp() {
  const { publishes, loading } = usePublishes(null)

  const [filter, setFilter]     = React.useState({ status: [], project: [], type: [] })
  const [filterOpen, setFilterOpen] = React.useState(false)
  const [openUuid, setOpenUuid] = React.useState(null)
  const [collapsed, setCollapsed] = React.useState({})

  // All hooks called before conditional return.
  const all = React.useMemo(() => buildReviewQueue(publishes), [publishes])
  const { items, setStatus, addNote } = useReviewState(all)

  const projects = React.useMemo(() => [...new Set(all.map(p => p.project))], [all])
  const types    = React.useMemo(() => [...new Set(all.map(p => pubProductType(p)))], [all])

  const filtered = React.useMemo(() => items.filter(p => {
    if (filter.status.length  && !filter.status.includes(p._status))        return false
    if (filter.project.length && !filter.project.includes(p.project))        return false
    if (filter.type.length    && !filter.type.includes(pubProductType(p)))   return false
    return true
  }), [items, filter])

  // Group: project → sequence or asset_type.
  const groups = React.useMemo(() => {
    const byProj = new Map()
    filtered.forEach(p => {
      const subKey = p.context?.type === 'shot'
        ? (p.context.sequence || 'unknown')
        : `${p.context?.asset_type || 'assets'}s`
      if (!byProj.has(p.project)) byProj.set(p.project, new Map())
      const subs = byProj.get(p.project)
      if (!subs.has(subKey)) subs.set(subKey, [])
      subs.get(subKey).push(p)
    })
    return byProj
  }, [filtered])

  const stats = React.useMemo(() => ({
    pending: items.filter(p => p._status === 'pending').length,
    flagged: items.filter(p => p._status === 'flagged').length,
    today:   items.filter(p => (Date.now() - p._ts) / 3_600_000 < 24).length,
  }), [items])

  const opened = items.find(p => p.uuid === openUuid)

  if (loading) {
    return (
      <div className="m-app" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: 'var(--text-4)', fontFamily: 'var(--mono)', fontSize: 13 }}>Loading…</span>
      </div>
    )
  }

  const totalFilters = filter.status.length + filter.project.length + filter.type.length

  return (
    <div className="m-app">
      <div className="m-header">
        <div className="m-header-row">
          <div className="m-avatar">{REVIEWER.initials}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {headerDate()}
            </div>
            <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>{greeting()}</div>
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

      <div className="m-scroll">
        <div className="m-summary" style={{ marginTop: 14 }}>
          <Stat num={stats.pending} label="Pending" tone="accent"/>
          <Stat num={stats.flagged} label="Flagged"  tone="warn"/>
          <Stat num={stats.today}   label="Today"    tone="ok"/>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px 8px' }}>
          <div style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>By project</div>
          <button className="m-btn" data-variant="ghost" data-size="sm"
                  onClick={() => setFilterOpen(true)}>
            <MIcon name="filter" size={13}/> Filters
            {totalFilters > 0 && (
              <span className="mono" style={{
                background: 'var(--accent)', color: '#1a1410',
                padding: '0 5px', borderRadius: 99, marginLeft: 4, fontSize: 10,
              }}>
                {totalFilters}
              </span>
            )}
          </button>
        </div>

        <div className="m-board">
          {[...groups.entries()].map(([proj, subs]) => {
            const allInProj   = [...subs.values()].flat()
            const projPending = allInProj.filter(p => p._status === 'pending').length
            const projKey     = `__proj__/${proj}`
            const projCollapsed = !!collapsed[projKey]
            return (
              <div key={proj} className="m-board-group">
                <button
                  className="m-board-group-head"
                  onClick={() => setCollapsed(c => ({ ...c, [projKey]: !c[projKey] }))}
                  aria-expanded={!projCollapsed}
                >
                  <MIcon name={projCollapsed ? 'chevR' : 'chevD'} size={13}/>
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
                </button>
                {!projCollapsed && [...subs.entries()].map(([sub, list]) => (
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
            )
          })}
          {filtered.length === 0 && (
            <div style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--text-4)' }}>
              {all.length === 0 ? 'No publishes found.' : 'No publishes match this filter.'}
            </div>
          )}
        </div>
      </div>

      <FilterSheet
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        value={filter}
        onChange={setFilter}
        projects={projects}
        types={types}
      />

      {opened && (
        <Detail
          pub={opened}
          onBack={() => setOpenUuid(null)}
          onAction={(status, note) => setStatus(opened.uuid, status, note)}
          onNote={(text) => addNote(opened.uuid, text)}
        />
      )}
    </div>
  )
}

const Stat = ({ num, label, tone }) => (
  <div className="m-stat">
    <div className="m-stat-num" data-tone={tone}>{num}</div>
    <div className="m-stat-label">{label}</div>
  </div>
)

const SubGroup = ({ name, items, collapsed, onToggle, onOpen }) => {
  const pendingHere = items.filter(p => p._status === 'pending').length
  return (
    <div>
      <button onClick={onToggle} style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 16px', textAlign: 'left',
        color: 'var(--text-3)', fontSize: 11.5,
        fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: '0.05em',
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
  )
}

const BoardCard = ({ pub, onOpen }) => {
  const ctxLabel = pub.context?.type === 'shot' ? pub.context.shot : pub.context?.asset
  const thumb = pubThumbnail(pub)
  return (
    <button className="m-card" onClick={onOpen}>
      <div className="m-card-thumb">
        {thumb
          ? <img src={thumb} alt=""/>
          : <div style={{ width: '100%', height: '100%', background: 'var(--bg-2)' }}/>}
      </div>
      <div className="m-card-body">
        <div className="m-card-title">
          {ctxLabel} <span style={{ color: 'var(--text-4)', fontWeight: 400 }}>· {pub.task}</span>
        </div>
        <div className="m-card-sub" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <TypeChip type={pubProductType(pub)}/>
          <span>v{String(pub.version).padStart(3, '0')}</span>
          <span style={{ color: 'var(--text-5)' }}>·</span>
          <span>{relTime(pubDate(pub))}</span>
        </div>
      </div>
      <div className="m-card-right">
        <StatusPill status={pub._status} compact/>
      </div>
    </button>
  )
}
