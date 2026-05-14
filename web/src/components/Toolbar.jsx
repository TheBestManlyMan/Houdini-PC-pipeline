import React from 'react'

export default function Toolbar({ viewMode, onViewMode, filters, onFilter, onClear, onRefresh, total }) {
  return (
    <div className="toolbar">
      <input
        className="toolbar-search"
        placeholder="Search entity, task…"
        value={filters.search}
        onChange={e => onFilter('search', e.target.value)}
      />
      <select
        className="toolbar-select"
        value={filters.publishType}
        onChange={e => onFilter('publishType', e.target.value)}
      >
        <option value="">All types</option>
        {['cache', 'flipbook', 'render', 'usd', 'hip'].map(t => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>
      <button className="toolbar-btn" onClick={onClear}>Clear</button>
      <span className="toolbar-count">{total} publish{total !== 1 ? 'es' : ''}</span>
      <div className="toolbar-views">
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
      </div>
      <button className="toolbar-btn" onClick={onRefresh} title="Refresh index">↺</button>
    </div>
  )
}
