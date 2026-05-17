import React, { useState } from 'react'
import AssetViewer from '../viewer/AssetViewer.jsx'

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

const FORMAT_LABELS = {
  gltf_static:    { label: 'GLTF Static',      cls: 'gltf' },
  gltf_animated:  { label: 'GLTF Animation',    cls: 'gltf' },
  vat:            { label: 'VAT Simulation',    cls: 'vat' },
  frame_sequence: { label: 'Frame Sequence',    cls: 'frame-seq' },
}

export default function AssetDetail({ asset, onClose }) {
  const [tab, setTab] = useState('info')

  const fmt_info = FORMAT_LABELS[asset.format_type] ?? { label: asset.format_type ?? 'GLTF', cls: 'gltf' }

  return (
    <div className="asset-detail-overlay">
      <div className="asset-detail">
        <div className="asset-detail-header">
          <div className="asset-detail-title">
            <span className="asset-detail-name">{asset.name}</span>
            <span className="asset-detail-project">{asset.project} / {asset.asset_name}</span>
          </div>
          <div className="asset-detail-header-actions">
            {asset.glb_url && (
              <a className="viewer-icon-btn" href={asset.glb_url} download title="Download GLB">↓</a>
            )}
            {asset.mesh_url && (
              <a className="viewer-icon-btn" href={asset.mesh_url} download title="Download mesh GLB">↓</a>
            )}
            <button className="viewer-icon-btn" onClick={onClose} title="Close">✕</button>
          </div>
        </div>

        <div className="asset-detail-body">
          <div className="asset-detail-viewer">
            <AssetViewer asset={asset} />
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

                <div className={`asset-format-badge ${fmt_info.cls}`}>{fmt_info.label}</div>

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

                  {asset.format_type === 'vat' && asset.vat && (<>
                    <dt>VAT verts</dt><dd>{fmt(asset.vat.vertex_count)}</dd>
                    <dt>VAT frames</dt><dd>{asset.vat.frame_count}</dd>
                    <dt>VAT fps</dt><dd>{asset.vat.fps}</dd>
                  </>)}

                  {asset.format_type === 'frame_sequence' && asset.frame_sequence && (<>
                    <dt>Seq frames</dt><dd>{asset.frame_sequence.frame_count}</dd>
                  </>)}

                  {asset.format_type === 'gltf_animated' && (
                    <>
                      <dt>Animations</dt>
                      <dd>{asset.animations?.length ? asset.animations.join(', ') : 'None'}</dd>
                    </>
                  )}
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
