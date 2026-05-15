import React, { useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import PublishGrid from './components/PublishGrid.jsx'
import DetailPanel from './components/DetailPanel.jsx'
import Toolbar from './components/Toolbar.jsx'
import { usePublishes } from './hooks/usePublishes.js'
import { useFilters } from './hooks/useFilters.js'

export default function App() {
  const [selectedId, setSelectedId] = useState(null)
  const [viewMode, setViewMode] = useState('grid') // 'grid' | 'list' | 'table'
  const [sidebarProject, setSidebarProject] = useState(null)

  const { publishes, projects, loading, error, refresh } = usePublishes(sidebarProject)
  const { filtered, filters, setFilter, clearFilters } = useFilters(publishes)

  const selected = filtered.find(p => p.uuid === selectedId) ?? null

  return (
    <div className="app-shell">
      <Sidebar
        projects={projects}
        activeProject={sidebarProject}
        onSelectProject={setSidebarProject}
      />
      <div className="main-area">
        <Toolbar
          viewMode={viewMode}
          onViewMode={setViewMode}
          filters={filters}
          onFilter={setFilter}
          onClear={clearFilters}
          onRefresh={refresh}
          total={filtered.length}
        />
        {loading && <div className="status-msg">Loading index…</div>}
        {error && <div className="status-msg error">{error}</div>}
        {!loading && !error && (
          <PublishGrid
            publishes={filtered}
            selectedId={selectedId}
            viewMode={viewMode}
            onSelect={setSelectedId}
          />
        )}
      </div>
      {selected && (
        <DetailPanel
          publish={selected}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}
