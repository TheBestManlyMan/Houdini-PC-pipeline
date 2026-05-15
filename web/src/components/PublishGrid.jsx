import React from 'react'
import PublishCard from './PublishCard.jsx'
import { versionLabel, formatDate, publishTypeColor, statusLabel, contextLabel } from '../utils/format.js'

export default function PublishGrid({ publishes, selectedId, viewMode, onSelect }) {
  if (publishes.length === 0) {
    return <div className="empty-msg">No publishes match the current filters.</div>
  }

  if (viewMode === 'table') {
    return (
      <div className="table-wrap">
        <table className="publish-table">
          <thead>
            <tr>
              <th>Entity</th><th>Task</th><th>Type</th><th>Ver</th>
              <th>Project</th><th>Context</th><th>Status</th><th>By</th><th>Date</th>
            </tr>
          </thead>
          <tbody>
            {publishes.map(p => (
              <tr
                key={p.uuid ?? p._index_path}
                className={selectedId === p.uuid ? 'selected' : ''}
                onClick={() => onSelect(p.uuid)}
              >
                <td>{p.entity}</td>
                <td>{p.task}</td>
                <td>
                  <span className="type-chip" style={{ background: publishTypeColor(p.publish_type) }}>
                    {p.publish_type}
                  </span>
                </td>
                <td>{versionLabel(p.version)}</td>
                <td>{p.project}</td>
                <td>{contextLabel(p.context)}</td>
                <td><span className={`status-pill status-${p.status ?? 'review'}`}>{statusLabel(p.status)}</span></td>
                <td>{p.created_by}</td>
                <td>{formatDate(p.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className={viewMode === 'list' ? 'publish-list' : 'publish-grid'}>
      {publishes.map(p => (
        <PublishCard
          key={p.uuid ?? p._index_path}
          publish={p}
          selected={selectedId === p.uuid}
          compact={viewMode === 'list'}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}
