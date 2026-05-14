import React from 'react'
import { versionLabel, formatDate, formatMb, publishTypeColor } from '../utils/format.js'

export default function DetailPanel({ publish: p, onClose }) {
  const typeColor = publishTypeColor(p.publish_type)

  return (
    <aside className="detail-panel">
      <div className="detail-header">
        <span className="detail-title">{p.entity}</span>
        <button className="detail-close" onClick={onClose}>✕</button>
      </div>

      <div className="detail-section">
        <span className="type-chip" style={{ background: typeColor }}>{p.publish_type}</span>
        <span className="detail-ver">{versionLabel(p.version)}</span>
      </div>

      {p.outputs?.mp4 && (
        <video className="detail-preview" src={p.outputs.mp4} controls loop muted />
      )}
      {!p.outputs?.mp4 && p.outputs?.thumbnail && (
        <img className="detail-thumb" src={p.outputs.thumbnail} alt="" />
      )}

      <dl className="detail-dl">
        <dt>Task</dt><dd>{p.task}</dd>
        <dt>Project</dt><dd>{p.project}</dd>
        <dt>Published by</dt><dd>{p.created_by}</dd>
        <dt>Date</dt><dd>{formatDate(p.created_at)}</dd>
        <dt>Frames</dt>
        <dd>{p.stats?.frame_start ?? '—'} – {p.stats?.frame_end ?? '—'}</dd>
        <dt>Size</dt><dd>{formatMb(p.stats?.disk_mb)}</dd>
        <dt>Houdini</dt><dd>{p.source?.houdini_version || '—'}</dd>
        <dt>Git commit</dt><dd>{p.source?.git_commit || '—'}</dd>
      </dl>

      {p.notes?.length > 0 && (
        <div className="detail-section">
          <div className="detail-section-title">Notes</div>
          {p.notes.map((n, i) => <p key={i} className="detail-note">{n}</p>)}
        </div>
      )}

      {p.tags?.length > 0 && (
        <div className="detail-section detail-tags">
          {p.tags.map(t => <span key={t} className="tag-chip">{t}</span>)}
        </div>
      )}

      {p.dependencies?.length > 0 && (
        <div className="detail-section">
          <div className="detail-section-title">Dependencies</div>
          {p.dependencies.map((d, i) => (
            <div key={i} className="dep-row">
              <span className="dep-type">{d.type}</span>
              <span className="dep-uuid">{d.publish_uuid}</span>
            </div>
          ))}
        </div>
      )}

      {p.wedge && (
        <div className="detail-section">
          <div className="detail-section-title">Wedge</div>
          <dl className="detail-dl">
            <dt>Parameter</dt><dd>{p.wedge.parameter}</dd>
            <dt>Value</dt><dd>{String(p.wedge.value)}</dd>
          </dl>
        </div>
      )}

      {p._warnings?.length > 0 && (
        <div className="detail-section detail-warnings">
          <div className="detail-section-title">⚠ Warnings</div>
          {p._warnings.map(w => <div key={w} className="warn-row">{w}</div>)}
        </div>
      )}
    </aside>
  )
}
