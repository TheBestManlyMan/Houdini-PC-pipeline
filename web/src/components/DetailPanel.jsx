import React from 'react'
import { versionLabel, formatDate, formatMb, publishTypeColor, contextLabel, isViewable, statusLabel } from '../utils/format.js'

function openFullscreen(el) {
  if (!el) return
  if (!document.fullscreenElement) {
    el.requestFullscreen?.()
  } else {
    document.exitFullscreen?.()
  }
}

function ViewablePreview({ publish: p }) {
  if (p.real_glb) {
    return (
      <model-viewer
        src={p.real_glb}
        camera-controls
        interaction-prompt="none"
        environment-image="neutral"
        shadow-intensity="1.1"
        exposure="0.95"
      />
    )
  }
  if (p.outputs?.mp4) return <video src={p.outputs.mp4} controls loop muted />
  if (p.outputs?.thumbnail) return <img src={p.outputs.thumbnail} alt="" />
  return (
    <div className={`detail-procedural type-${p.publish_type}`}>
      <span>{p.publish_type}</span>
      <strong>{p.entity}</strong>
      <small>{p.task}</small>
    </div>
  )
}

export default function DetailPanel({ publish: p, onClose, onReview }) {
  const typeColor = publishTypeColor(p.publish_type)
  const previewRef = React.useRef(null)
  const [note, setNote] = React.useState('')

  function review(status) {
    onReview?.(p.uuid, status, note)
    setNote('')
  }

  return (
    <aside className="detail-panel">
      <div className="detail-header">
        <span className="detail-title">{p.entity}</span>
        <button className="icon-btn" onClick={onClose} title="Close">x</button>
      </div>

      <div className="detail-section">
        <span className="type-chip" style={{ background: typeColor }}>{p.publish_type}</span>
        <span className="detail-ver">{versionLabel(p.version)}</span>
        <span className={`status-pill status-${p.status ?? 'review'}`}>{statusLabel(p.status)}</span>
      </div>

      <div className="detail-preview-shell" ref={previewRef}>
        <ViewablePreview publish={p} />
        {isViewable(p) && (
          <button className="fullscreen-btn" onClick={() => openFullscreen(previewRef.current)}>
            Fullscreen
          </button>
        )}
      </div>

      <div className="review-box">
        <textarea
          value={note}
          onChange={e => setNote(e.target.value)}
          placeholder="Add review note..."
        />
        <div className="review-actions">
          <button className="btn primary" onClick={() => review('approved')}>Approve</button>
          <button className="btn" onClick={() => review('changes')}>Changes</button>
          <button className="btn" onClick={() => review('flagged')}>Flag</button>
        </div>
      </div>

      <dl className="detail-dl">
        <dt>Task</dt><dd>{p.task}</dd>
        <dt>Project</dt><dd>{p.project}</dd>
        <dt>Context</dt><dd>{contextLabel(p.context) || '—'}</dd>
        <dt>Published by</dt><dd>{p.created_by}</dd>
        <dt>Date</dt><dd>{formatDate(p.created_at)}</dd>
        <dt>Frames</dt>
        <dd>{p.stats?.frame_start ?? '—'} – {p.stats?.frame_end ?? '—'}</dd>
        <dt>Size</dt><dd>{formatMb(p.stats?.disk_mb)}</dd>
        <dt>Houdini</dt><dd>{p.source?.houdini_version || '—'}</dd>
        <dt>Git commit</dt><dd>{p.source?.git_commit || '—'}</dd>
        <dt>ROP</dt><dd>{p.source?.rop || '—'}</dd>
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
