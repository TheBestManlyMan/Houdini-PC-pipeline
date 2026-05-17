import React, { useMemo, useState, lazy, Suspense } from 'react'
import Sidebar from './components/Sidebar.jsx'
import PublishGrid from './components/PublishGrid.jsx'
import DetailPanel from './components/DetailPanel.jsx'
import Toolbar from './components/Toolbar.jsx'

// Lazy-load heavy 3D components so Three.js doesn't ship in the initial bundle
const AssetBrowser = lazy(() => import('./components/assets/AssetBrowser.jsx'))
const AssetDetail  = lazy(() => import('./components/assets/AssetDetail.jsx'))

import { usePublishes } from './hooks/usePublishes.js'
import { useAssets }   from './hooks/useAssets.js'
import { useFilters }  from './hooks/useFilters.js'
import { contextLabel, statusLabel } from './utils/format.js'

export default function App() {
  const [surface, setSurface] = useState('gallery')
  const [selectedId, setSelectedId] = useState(null)
  const [viewMode, setViewMode] = useState('grid') // 'grid' | 'list' | 'table'
  const [sidebarProject, setSidebarProject] = useState(null)
  const [reviewStatus, setReviewStatus] = useState({})
  const [reviewNotes,  setReviewNotes]  = useState({})

  const { publishes, projects, index, mode, source, warning, loading, error, refresh } = usePublishes(sidebarProject)
  const { assets } = useAssets()

  // Normalise 3D assets into publish-like records so they appear in the gallery
  const assetPublishes = useMemo(() => assets.map(a => ({
    uuid: `asset:${a.project}:${a.asset_name}`,
    publish_type: 'asset',
    entity: a.name || a.asset_name,
    task: a.asset_name,
    version: 1,
    status: 'approved',
    context: { type: 'asset' },
    created_at: a.created || null,
    created_by: a.author || '',
    project: a.project,
    notes: [],
    outputs: { thumbnail: a.thumbnail_url || null, mp4: null },
    _normalized: true,
    _asset: a,
  })), [assets])

  const enhancedPublishes = useMemo(() => [
    ...publishes.map(p => ({
      ...p,
      status: reviewStatus[p.uuid] ?? p.status ?? 'review',
      notes: [...(p.notes ?? []), ...(reviewNotes[p.uuid] ?? [])],
    })),
    ...assetPublishes,
  ], [publishes, assetPublishes, reviewNotes, reviewStatus])

  const { filtered, filters, setFilter, clearFilters } = useFilters(enhancedPublishes)
  const enhancedFiltered = useMemo(() => filtered.map(p => ({
    ...p,
    status: p._asset ? p.status : (reviewStatus[p.uuid] ?? p.status ?? 'review'),
    notes: p._asset ? p.notes : [...(p.notes ?? []), ...(reviewNotes[p.uuid] ?? [])],
  })), [filtered, reviewNotes, reviewStatus])

  const selected = enhancedPublishes.find(p => p.uuid === selectedId) ?? null
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

  // Asset selections show a full overlay — don't open the third-column detail panel
  const shellClass = `app-shell ${selected && surface === 'gallery' && !selected._asset ? 'has-detail' : ''}`

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
        {surface === 'assets' && (
          <Suspense fallback={<div className="status-msg">Loading 3D viewer…</div>}>
            <AssetBrowser />
          </Suspense>
        )}
        {/* Asset detail overlay — shown when an asset card is clicked in the gallery */}
        {selected?._asset && surface === 'gallery' && (
          <Suspense fallback={null}>
            <AssetDetail asset={selected._asset} onClose={() => setSelectedId(null)} />
          </Suspense>
        )}
        {!loading && surface === 'manager' && (
          <PipelineManager projects={activeProjects} publishes={enhancedPublishes} />
        )}

      </div>
      {selected && surface === 'gallery' && !selected._asset && (
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
