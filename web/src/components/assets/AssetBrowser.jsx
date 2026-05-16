import React, { useState, useMemo } from 'react'
import { useAssets } from '../../hooks/useAssets.js'
import AssetCard from './AssetCard.jsx'
import AssetDetail from './AssetDetail.jsx'

export default function AssetBrowser() {
  const { assets, loading, error, refresh } = useAssets()
  const [selected, setSelected] = useState(null)
  const [search, setSearch] = useState('')
  const [tagFilter, setTagFilter] = useState('')
  const [projectFilter, setProjectFilter] = useState('')

  // Collect unique tags and projects for filter dropdowns
  const allTags = useMemo(() => {
    const s = new Set()
    assets.forEach(a => a.tags?.forEach(t => s.add(t)))
    return [...s].sort()
  }, [assets])

  const allProjects = useMemo(() => {
    const s = new Set(assets.map(a => a.project).filter(Boolean))
    return [...s].sort()
  }, [assets])

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return assets.filter(a => {
      if (q && !a.name.toLowerCase().includes(q) && !a.asset_name?.toLowerCase().includes(q)) return false
      if (tagFilter && !a.tags?.includes(tagFilter)) return false
      if (projectFilter && a.project !== projectFilter) return false
      return true
    })
  }, [assets, search, tagFilter, projectFilter])

  function clearFilters() {
    setSearch('')
    setTagFilter('')
    setProjectFilter('')
  }

  return (
    <section className="asset-browser">
      <div className="asset-browser-toolbar">
        <div className="asset-browser-title">
          <strong>3D Assets</strong>
          <span className="asset-browser-count">{filtered.length} / {assets.length}</span>
        </div>

        <input
          className="toolbar-search"
          type="search"
          placeholder="Search assets…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />

        {allProjects.length > 1 && (
          <select
            className="toolbar-select"
            value={projectFilter}
            onChange={e => setProjectFilter(e.target.value)}
          >
            <option value="">All projects</option>
            {allProjects.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        )}

        {allTags.length > 0 && (
          <select
            className="toolbar-select"
            value={tagFilter}
            onChange={e => setTagFilter(e.target.value)}
          >
            <option value="">All tags</option>
            {allTags.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        )}

        {(search || tagFilter || projectFilter) && (
          <button className="toolbar-btn ghost" onClick={clearFilters}>Clear</button>
        )}

        <button className="toolbar-btn" onClick={refresh} title="Refresh asset list">↺ Refresh</button>
      </div>

      {loading && <div className="status-msg">Scanning assets…</div>}
      {error && <div className="status-msg error">Error: {error}</div>}

      {!loading && filtered.length === 0 && (
        <div className="status-msg">
          {assets.length === 0
            ? 'No 3D assets found. Publish a GLB from Houdini to get started.'
            : 'No assets match your filters.'}
        </div>
      )}

      {!loading && filtered.length > 0 && (
        <div className="asset-grid">
          {filtered.map(asset => (
            <AssetCard
              key={`${asset.project}/${asset.asset_name}`}
              asset={asset}
              selected={selected?.asset_name === asset.asset_name && selected?.project === asset.project}
              onSelect={setSelected}
            />
          ))}
        </div>
      )}

      {selected && (
        <AssetDetail
          asset={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  )
}
