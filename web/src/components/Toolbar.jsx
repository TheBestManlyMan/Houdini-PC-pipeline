import React from 'react'

export default function Toolbar({ surface, onSurface, viewMode, onViewMode, filters, onFilter, onClear, onRefresh, total, mode, source }) {
  return (
    <div className="toolbar">
      <div className="toolbar-title">
        <strong>
          {surface === 'gallery' ? 'Publish Gallery'
            : surface === 'assets'  ? '3D Assets'
            : surface === 'manager' ? 'Pipeline Manager'
            : 'Mobile Review'}
        </strong>
        <span className={`conn conn-${mode}`}><i />{mode === 'live' ? 'Live' : mode === 'static' ? 'Static index' : 'Demo'}</span>
      </div>
      <input
        className="toolbar-search"
        placeholder="Search entity, task, artist, note..."
        value={filters.search}
        onChange={e => onFilter('search', e.target.value)}
      />
      <select
        className="toolbar-select"
        value={filters.status}
        onChange={e => onFilter('status', e.target.value)}
      >
        <option value="">All status</option>
        <option value="review">Review</option>
        <option value="changes">Changes</option>
        <option value="flagged">Flagged</option>
        <option value="approved">Approved</option>
      </select>
      <select
        className="toolbar-select"
        value={filters.publishType}
        onChange={e => onFilter('publishType', e.target.value)}
      >
        <option value="">All types</option>
        {['cache', 'flipbook', 'render', 'usd', 'hip', 'asset'].map(t => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>
      <button className="toolbar-btn" onClick={onClear}>Clear</button>
      <span className="toolbar-count">{total} publish{total !== 1 ? 'es' : ''}</span>
      {surface === 'gallery' && <div className="toolbar-views">
        {['grid', 'list', 'table'].map(v => (
          <button
            key={v}
            className={`toolbar-view-btn ${viewMode === v ? 'active' : ''}`}
            onClick={() => onViewMode(v)}
            title={v}
          >
            {v === 'grid' ? '⊞' : v === 'list' ? '☰' : '⊟'}
          </button>
        ))}
      </div>}
      <button className="toolbar-btn" onClick={onRefresh} title="Refresh index">↺</button>
      <button className="toolbar-btn ghost" onClick={() => onSurface(surface === 'mobile' ? 'gallery' : 'mobile')}>
        {surface === 'mobile' ? 'Desktop' : 'Phone'}
      </button>
      <span className="toolbar-source" title={source}>{source}</span>
    </div>
  )
}
