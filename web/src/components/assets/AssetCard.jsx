import React from 'react'

function fmt(n) {
  if (!n) return '—'
  return n >= 1_000_000
    ? (n / 1_000_000).toFixed(1) + 'M'
    : n >= 1_000
    ? (n / 1_000).toFixed(1) + 'K'
    : String(n)
}

export default function AssetCard({ asset, selected, onSelect }) {
  const animCount = asset.animations?.length ?? 0
  const tags = asset.tags ?? []

  return (
    <div
      className={`asset-card ${selected ? 'selected' : ''}`}
      onClick={() => onSelect(asset)}
    >
      <div className="asset-card-thumb">
        {asset.thumbnail_url ? (
          <img src={asset.thumbnail_url} alt={asset.name} />
        ) : (
          <div className="asset-card-thumb-placeholder">
            <span className="asset-thumb-icon">⬡</span>
            <span className="asset-thumb-type">3D</span>
          </div>
        )}
        {animCount > 0 && (
          <span className="asset-card-badge">{animCount} anim{animCount !== 1 ? 's' : ''}</span>
        )}
      </div>

      <div className="asset-card-body">
        <div className="asset-card-name" title={asset.name}>{asset.name}</div>
        <div className="asset-card-meta">
          <span>{asset.project}</span>
          {asset.polycount > 0 && <span>{fmt(asset.polycount)} poly</span>}
        </div>
        {tags.length > 0 && (
          <div className="asset-card-tags">
            {tags.slice(0, 3).map(t => (
              <span key={t} className="asset-tag">{t}</span>
            ))}
            {tags.length > 3 && <span className="asset-tag-more">+{tags.length - 3}</span>}
          </div>
        )}
      </div>
    </div>
  )
}
