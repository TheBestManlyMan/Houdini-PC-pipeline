import React from 'react'

export default function Sidebar({ projects, publishes, activeProject, activeSurface, onSelectProject, onSurface }) {
  const flagged = publishes.filter(p => p._warnings?.length || p._orphaned).length

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-mark">FX</div>
        <div>
          <span className="brand-name">Houdini Pipeline</span>
          <span className="sidebar-title">Publish workbench</span>
        </div>
      </div>
      <nav className="surface-nav">
        {[
          ['gallery', 'Gallery'],
          ['assets', '3D Assets'],
          ['manager', 'Manager'],
          ['mobile', 'Mobile Review'],
        ].map(([id, label]) => (
          <button
            key={id}
            className={activeSurface === id ? 'active' : ''}
            onClick={() => onSurface(id)}
          >
            {label}
          </button>
        ))}
      </nav>
      <ul className="sidebar-list">
        <li
          className={`sidebar-item ${activeProject === null ? 'active' : ''}`}
          onClick={() => onSelectProject(null)}
        >
          All Projects
        </li>
        {flagged > 0 && <li className="sidebar-item flagged">Flagged outputs <span>{flagged}</span></li>}
        {(projects ?? []).map(p => (
          <li
            key={p.folder ?? p.name}
            className={`sidebar-item ${activeProject === p.folder ? 'active' : ''}`}
            onClick={() => onSelectProject(p.folder)}
          >
            <span>{p.name}</span>
          </li>
        ))}
      </ul>
    </aside>
  )
}
