import React, { useState } from 'react'
import ModelViewer from '../viewer/ModelViewer.jsx'

function fmt(n) {
  if (!n) return '—'
  return n >= 1_000_000
    ? (n / 1_000_000).toFixed(2) + 'M'
    : n >= 1_000
    ? (n / 1_000).toFixed(1) + 'K'
    : String(n)
}

function fmtDate(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleDateString() } catch { return iso }
}

export default function AssetDetail({ asset, onClose }) {
  const [tab, setTab] = useState('info')

  return (
    <div className="asset-detail-overlay">
      <div className="asset-detail">
        <div className="asset-detail-header">
          <div className="asset-detail-title">
            <span className="asset-detail-name">{asset.name}</span>
            <span className="asset-detail-project">{asset.project} / {asset.asset_name}</span>
          </div>
          <div className="asset-detail-header-actions">
            <a
              className="viewer-icon-btn"
              href={asset.glb_url}
              download
              title="Download GLB"
            >
              ↓
            </a>
            <button className="viewer-icon-btn" onClick={onClose} title="Close">✕</button>
          </div>
        </div>

        <div className="asset-detail-body">
          <div className="asset-detail-viewer">
            <ModelViewer url={asset.glb_url} />
          </div>

          <aside className="asset-detail-panel">
            <div className="asset-detail-tabs">
              <button
                className={`asset-tab-btn ${tab === 'info' ? 'active' : ''}`}
                onClick={() => setTab('info')}
              >Info</button>
              <button
                className={`asset-tab-btn ${tab === 'raw' ? 'active' : ''}`}
                onClick={() => setTab('raw')}
              >Raw</button>
            </div>

            {tab === 'info' && (
              <div className="asset-meta-body">
                {asset.description && (
                  <p className="asset-description">{asset.description}</p>
                )}

                <dl className="asset-dl">
                  <dt>Author</dt><dd>{asset.author || '—'}</dd>
                  <dt>Created</dt><dd>{fmtDate(asset.created)}</dd>
                  <dt>Project</dt><dd>{asset.project}</dd>
                  <dt>Polycount</dt><dd>{fmt(asset.polycount)}</dd>
                  <dt>Houdini</dt><dd>{asset.houdini_version || '—'}</dd>
                  <dt>Frames</dt>
                  <dd>
                    {asset.frame_range
                      ? `${asset.frame_range[0]} – ${asset.frame_range[1]}`
                      : '—'}
                  </dd>
                  <dt>Animations</dt>
                  <dd>{asset.animations?.length ? asset.animations.join(', ') : 'None'}</dd>
                </dl>

                {asset.tags?.length > 0 && (
                  <div className="asset-tags-section">
                    <div className="asset-section-label">Tags</div>
                    <div className="asset-tag-list">
                      {asset.tags.map(t => (
                        <span key={t} className="asset-tag">{t}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {tab === 'raw' && (
              <pre className="asset-raw-json">
                {JSON.stringify(asset, null, 2)}
              </pre>
            )}
          </aside>
        </div>
      </div>
    </div>
  )
}
