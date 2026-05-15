import React, { useMemo, useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import PublishGrid from './components/PublishGrid.jsx'
import DetailPanel from './components/DetailPanel.jsx'
import Toolbar from './components/Toolbar.jsx'
import { usePublishes } from './hooks/usePublishes.js'
import { useFilters } from './hooks/useFilters.js'
import { contextLabel, formatRelative, publishTypeColor, statusLabel, versionLabel } from './utils/format.js'

export default function App() {
  const [surface, setSurface] = useState('gallery')
  const [selectedId, setSelectedId] = useState(null)
  const [viewMode, setViewMode] = useState('grid') // 'grid' | 'list' | 'table'
  const [sidebarProject, setSidebarProject] = useState(null)
  const [reviewStatus, setReviewStatus] = useState({})
  const [reviewNotes, setReviewNotes] = useState({})

  const { publishes, projects, index, mode, source, warning, loading, error, refresh } = usePublishes(sidebarProject)
  const enhancedPublishes = useMemo(() => publishes.map(p => ({
    ...p,
    status: reviewStatus[p.uuid] ?? p.status ?? 'review',
    notes: [...(p.notes ?? []), ...(reviewNotes[p.uuid] ?? [])],
  })), [publishes, reviewNotes, reviewStatus])
  const { filtered, filters, setFilter, clearFilters } = useFilters(enhancedPublishes)
  const enhancedFiltered = useMemo(() => filtered.map(p => ({
    ...p,
    status: reviewStatus[p.uuid] ?? p.status ?? 'review',
    notes: [...(p.notes ?? []), ...(reviewNotes[p.uuid] ?? [])],
  })), [filtered, reviewNotes, reviewStatus])

  const selected = enhancedPublishes.find(p => p.uuid === selectedId) ?? enhancedFiltered[0] ?? null
  const activeProjects = projects?.length ? projects : index?.projects ?? []

  function updateReview(uuid, status, note) {
    setReviewStatus(s => ({ ...s, [uuid]: status }))
    if (note?.trim()) {
      setReviewNotes(n => ({
        ...n,
        [uuid]: [...(n[uuid] ?? []), `${statusLabel(status)} by maxborg: ${note.trim()}`],
      }))
    }
  }

  const shellClass = `app-shell ${selected && surface === 'gallery' ? 'has-detail' : ''}`

  return (
    <div className={shellClass}>
      <Sidebar
        projects={activeProjects}
        publishes={enhancedPublishes}
        activeProject={sidebarProject}
        activeSurface={surface}
        onSelectProject={(folder) => {
          setSidebarProject(folder)
          setFilter('project', activeProjects.find(p => p.folder === folder)?.name ?? '')
        }}
        onSurface={setSurface}
      />
      <div className="main-area">
        <Toolbar
          surface={surface}
          onSurface={setSurface}
          viewMode={viewMode}
          onViewMode={setViewMode}
          filters={filters}
          onFilter={setFilter}
          onClear={clearFilters}
          onRefresh={refresh}
          total={enhancedFiltered.length}
          mode={mode}
          source={source}
          warning={warning}
        />
        {warning && <div className="banner">{warning}</div>}
        {loading && <div className="status-msg">Loading pipeline data...</div>}
        {error && <div className="status-msg error">{error}</div>}
        {!loading && surface === 'gallery' && (
          <PublishGrid
            publishes={enhancedFiltered}
            selectedId={selectedId}
            viewMode={viewMode}
            onSelect={setSelectedId}
          />
        )}
        {!loading && surface === 'manager' && (
          <PipelineManager projects={activeProjects} publishes={enhancedPublishes} />
        )}
        {!loading && surface === 'mobile' && (
          <MobileReview
            publishes={enhancedPublishes}
            selected={selected}
            onSelect={setSelectedId}
            onReview={updateReview}
          />
        )}
      </div>
      {selected && surface === 'gallery' && (
        <DetailPanel
          publish={selected}
          onClose={() => setSelectedId(null)}
          onReview={updateReview}
        />
      )}
    </div>
  )
}

function PipelineManager({ projects, publishes }) {
  const rows = projects.map(project => {
    const projectPublishes = publishes.filter(p => p.project === project.name || p.project === project.folder)
    const shotCount = new Set(projectPublishes.filter(p => p.context?.type === 'shot').map(p => contextLabel(p.context))).size
    const assetCount = Object.values(project.assets ?? {}).reduce((sum, arr) => sum + arr.length, 0)
    return { project, projectPublishes, shotCount, assetCount }
  })

  return (
    <section className="manager-view">
      <div className="section-head">
        <div>
          <h1>Pipeline Manager</h1>
          <p>Projects, sequences, assets, and publish health in one operational view.</p>
        </div>
        <button className="btn primary">New project</button>
      </div>
      <div className="manager-grid">
        {rows.map(({ project, projectPublishes, shotCount, assetCount }) => (
          <article className="project-card" key={project.folder ?? project.name}>
            <div className="project-card-head">
              <div>
                <h2>{project.name}</h2>
                <p>{project.folder} · {project.fps ?? 24} fps · {project.resolution ?? '1920x1080'}</p>
              </div>
              <span>{projectPublishes.length} publishes</span>
            </div>
            <div className="metric-row">
              <div><b>{project.sequences?.length ?? 0}</b><span>Sequences</span></div>
              <div><b>{shotCount}</b><span>Shots</span></div>
              <div><b>{assetCount}</b><span>Assets</span></div>
            </div>
            <div className="manager-list">
              {(project.sequences ?? []).slice(0, 4).map(seq => <span key={seq}>Shot sequence · {seq}</span>)}
              {Object.entries(project.assets ?? {}).flatMap(([type, names]) =>
                names.map(name => <span key={`${type}-${name}`}>Asset · {type}/{name}</span>)
              ).slice(0, 5)}
              {!project.sequences?.length && !assetCount && <span>No entities registered yet.</span>}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

function MobileReview({ publishes, selected, onSelect, onReview }) {
  const queue = publishes
    .filter(p => (p.status ?? 'review') !== 'approved')
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  const active = selected && queue.some(p => p.uuid === selected.uuid) ? selected : queue[0]
  const [note, setNote] = useState('')

  function review(status) {
    if (!active) return
    onReview(active.uuid, status, note)
    setNote('')
  }

  return (
    <section className="mobile-canvas">
      <div className="phone-frame">
        <div className="phone-app">
          <header className="phone-top">
            <div>
              <strong>Review Queue</strong>
              <span>maxborg · FX Supervisor</span>
            </div>
            <span className="phone-count">{queue.length}</span>
          </header>
          <div className="phone-filters">
            {['review', 'changes', 'flagged'].map(status => <span key={status}>{statusLabel(status)}</span>)}
          </div>
          <div className="phone-list">
            {queue.map(pub => (
              <button
                key={pub.uuid}
                className={`phone-row ${active?.uuid === pub.uuid ? 'active' : ''}`}
                onClick={() => onSelect(pub.uuid)}
              >
                <Preview pub={pub} tiny />
                <span>
                  <b>{pub.entity}</b>
                  <small>{pub.task} · {versionLabel(pub.version)} · {formatRelative(pub.created_at)}</small>
                </span>
                <i>{pub.real_glb ? '3D' : pub.publish_type}</i>
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="mobile-detail">
        {active ? (
          <>
            <div className="mobile-hero"><Preview pub={active} /></div>
            <div className="mobile-copy">
              <span className="type-chip" style={{ background: publishTypeColor(active.publish_type) }}>{active.publish_type}</span>
              <h2>{active.entity} · {active.task}</h2>
              <p>{contextLabel(active.context)} · {versionLabel(active.version)} · {active.created_by}</p>
              <textarea
                value={note}
                onChange={e => setNote(e.target.value)}
                placeholder="Leave a supervisor note..."
              />
              <div className="review-actions">
                <button className="btn primary" onClick={() => review('approved')}>Approve</button>
                <button className="btn" onClick={() => review('changes')}>Request changes</button>
                <button className="btn" onClick={() => review('flagged')}>Flag later</button>
              </div>
            </div>
          </>
        ) : <div className="empty-msg">No publishes awaiting review.</div>}
      </div>
    </section>
  )
}

function Preview({ pub, tiny = false }) {
  if (pub.real_glb && !tiny) {
    return <model-viewer src={pub.real_glb} camera-controls interaction-prompt="none" environment-image="neutral" shadow-intensity="1" />
  }
  return (
    <div className={`procedural-preview type-${pub.publish_type}`}>
      <span>{pub.real_glb ? '3D' : pub.publish_type}</span>
      <b>{pub.entity}</b>
    </div>
  )
}
