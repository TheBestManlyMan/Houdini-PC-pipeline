import React from 'react'
import { versionLabel, formatDate, publishTypeColor } from '../utils/format.js'

export default function PublishCard({ publish: p, selected, compact, onSelect }) {
  const thumbnail = p.outputs?.thumbnail
  const typeColor = publishTypeColor(p.publish_type)

  if (compact) {
    return (
      <div
        className={`publish-list-item ${selected ? 'selected' : ''}`}
        onClick={() => onSelect(p.uuid)}
      >
        {thumbnail && <img className="list-thumb" src={thumbnail} alt="" />}
        <div className="list-body">
          <span className="list-entity">{p.entity}</span>
          <span className="list-task">{p.task}</span>
          <span className="type-chip" style={{ background: typeColor }}>{p.publish_type}</span>
          <span className="list-ver">{versionLabel(p.version)}</span>
        </div>
        <div className="list-meta">{formatDate(p.created_at)}</div>
      </div>
    )
  }

  return (
    <div
      className={`publish-card ${selected ? 'selected' : ''}`}
      onClick={() => onSelect(p.uuid)}
    >
      <div className="card-thumb-wrap">
        {thumbnail
          ? <img className="card-thumb" src={thumbnail} alt="" />
          : <div className="card-thumb-placeholder" />
        }
        <span className="card-type-chip" style={{ background: typeColor }}>
          {p.publish_type}
        </span>
        {p._warnings?.length > 0 && (
          <span className="card-warn" title={p._warnings.join(', ')}>⚠</span>
        )}
      </div>
      <div className="card-body">
        <div className="card-entity">{p.entity}</div>
        <div className="card-task">{p.task} · {versionLabel(p.version)}</div>
        <div className="card-date">{formatDate(p.created_at)}</div>
      </div>
    </div>
  )
}
