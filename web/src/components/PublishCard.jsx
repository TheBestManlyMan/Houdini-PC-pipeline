import React from 'react'
import { versionLabel, formatRelative, publishTypeColor, statusLabel, contextLabel } from '../utils/format.js'

const ASSET_FORMAT_LABELS = {
  gltf_static:    'GLB',
  gltf_animated:  'GLB Anim',
  vat:            'VAT Sim',
  frame_sequence: 'Frame Seq',
}

function CardPreview({ publish: p }) {
  const thumbnail = p.outputs?.thumbnail
  if (thumbnail) return <img className="card-thumb" src={thumbnail} alt="" />
  if (p.publish_type === 'asset') {
    return (
      <div className="card-thumb-placeholder type-asset">
        <span>3D</span>
        <b>{p.entity}</b>
      </div>
    )
  }
  return (
    <div className={`card-thumb-placeholder type-${p.publish_type}`}>
      <span>{p.real_glb ? '3D' : p.publish_type}</span>
      <b>{p.entity}</b>
    </div>
  )
}

export default function PublishCard({ publish: p, selected, compact, onSelect }) {
  const typeColor = publishTypeColor(p.publish_type)
  const isAsset = p.publish_type === 'asset'
  const chipLabel = isAsset
    ? (ASSET_FORMAT_LABELS[p._asset?.format_type] ?? '3D Asset')
    : (p.real_glb ? '3D' : p.publish_type)

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
          <span className="type-chip" style={{ background: typeColor }}>{chipLabel}</span>
          <span className="list-ver">{versionLabel(p.version)}</span>
        </div>
        <div className={`status-pill status-${p.status ?? 'review'}`}>{statusLabel(p.status)}</div>
        <div className="list-meta">{formatRelative(p.created_at)}</div>
      </div>
    )
  }

  return (
    <div
      className={`publish-card ${selected ? 'selected' : ''} ${isAsset ? 'publish-card-asset' : ''}`}
      onClick={() => onSelect(p.uuid)}
    >
      <div className="card-thumb-wrap">
        <CardPreview publish={p} />
        <span className="card-type-chip" style={{ background: typeColor }}>
          {chipLabel}
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
