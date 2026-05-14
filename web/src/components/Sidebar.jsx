import React from 'react'

export default function Sidebar({ projects, activeProject, onSelectProject }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">Projects</span>
      </div>
      <ul className="sidebar-list">
        <li
          className={`sidebar-item ${activeProject === null ? 'active' : ''}`}
          onClick={() => onSelectProject(null)}
        >
          All Projects
        </li>
        {(projects ?? []).map(p => (
          <li
            key={p.folder ?? p.name}
            className={`sidebar-item ${activeProject === p.folder ? 'active' : ''}`}
            onClick={() => onSelectProject(p.folder)}
          >
            {p.name}
          </li>
        ))}
      </ul>
    </aside>
  )
}
