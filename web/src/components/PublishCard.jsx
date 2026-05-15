import React from 'react'
import { versionLabel, formatRelative, publishTypeColor, statusLabel, contextLabel } from '../utils/format.js'

function CardPreview({ publish: p }) {
  const thumbnail = p.outputs?.thumbnail
  if (thumbnail) return <img className="card-thumb" src={thumbnail} alt="" />
  return (
    <div className={`card-thumb-placeholder type-${p.publish_type}`}>
      <span>{p.real_glb ? '3D' : p.publish_type}</span>
      <b>{p.entity}</b>
    </div>
  )
}

export default function PublishCard({ publish: p, selected, compact, onSelect }) {
  const typeColor = publishTypeColor(p.publish_type)

  if (compact) {
    return (
      <div
        className={`publish-list-item ${selected ? 'selected' : ''}`}
        onClick={() => onSelect(p.uuid)}
      >
        <div className="list-thumb"><CardPreview publish={p} /></div>
        <div className="list-body">
          <span className="list-entity">{p.entity}</span>
          <span className="list-task">{p.task} · {contextLabel(p.context)}</span>
          <span className="type-chip" style={{ background: typeColor }}>{p.publish_type}</span>
          <span className="list-ver">{versionLabel(p.version)}</span>
        </div>
        <div className={`status-pill status-${p.status ?? 'review'}`}>{statusLabel(p.status)}</div>
        <div className="list-meta">{formatRelative(p.created_at)}</div>
      </div>
    )
  }

  return (
    <div
      className={`publish-card ${selected ? 'selected' : ''}`}
      onClick={() => onSelect(p.uuid)}
    >
      <div className="card-thumb-wrap">
        <CardPreview publish={p} />
        <span className="card-type-chip" style={{ background: typeColor }}>
          {p.real_glb ? '3D' : p.publish_type}
        </span>
        {p._warnings?.length > 0 && (
          <span className="card-warn" title={p._warnings.join(', ')}>⚠</span>
        )}
      </div>
      <div className="card-body">
        <div className="card-row">
          <div className="card-entity">{p.entity}</div>
          <span className={`status-pill status-${p.status ?? 'review'}`}>{statusLabel(p.status)}</span>
        </div>
        <div className="card-task">{p.task} · {versionLabel(p.version)}</div>
        <div className="card-date">{contextLabel(p.context)} · {formatRelative(p.created_at)}</div>
      </div>
    </div>
  )
}
