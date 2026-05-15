export function versionLabel(v) {
  return `v${String(v).padStart(3, '0')}`
}

export function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatRelative(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function formatMb(mb) {
  if (mb == null) return '—'
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`
}

export function publishTypeColor(type) {
  return {
    cache: 'oklch(72% 0.14 160)',
    flipbook: 'oklch(78% 0.13 84)',
    render: 'oklch(70% 0.14 245)',
    usd: 'oklch(72% 0.13 315)',
    hip: 'oklch(72% 0.13 38)',
  }[type] ?? 'oklch(68% 0.02 250)'
}

export function contextLabel(ctx) {
  if (!ctx) return ''
  if (ctx.type === 'shot') return `${ctx.sequence}/${ctx.shot}`
  if (ctx.type === 'asset') return `${ctx.asset_type}/${ctx.asset}`
  return ''
}

export function statusLabel(status) {
  return {
    approved: 'Approved',
    changes: 'Changes',
    flagged: 'Flagged',
    review: 'Review',
    viewed: 'Viewed',
  }[status] ?? 'Review'
}

export function isViewable(pub) {
  return Boolean(pub?.real_glb || pub?.outputs?.mp4 || pub?.outputs?.thumbnail || pub?.outputs?.frames || pub?.outputs?.usd)
}

/**
 * Normalise a publish record so components work with both the old schema
 * (schema_version 2, fields: publish_type / created_at / outputs.thumbnail)
 * and the new canonical schema v1 (product_type / audit.published_at / preview.thumbnail).
 */
export function normalizePublish(p) {
  if (!p || p._normalized) return p

  // Type
  const publish_type = p.product_type ?? p.publish_type ?? 'unknown'

  // Timing / author
  const created_at = p.audit?.published_at ?? p.created_at ?? null
  const created_by = p.audit?.published_by ?? p.created_by ?? null

  // Media — prefer new schema preview block, fall back to old outputs block
  const thumbnail = p.preview?.thumbnail ?? p.outputs?.thumbnail ?? null
  const mp4       = p.preview?.mp4       ?? p.outputs?.mp4       ?? null

  // Stable unique key — new schema has no uuid, use _index_path as fallback
  const uuid = p.uuid ?? p._index_path ?? null

  // Frame range — new schema stores per-representation, old schema stores in stats
  let frame_start = p.stats?.frame_start ?? null
  let frame_end   = p.stats?.frame_end   ?? null
  if (frame_start == null && Array.isArray(p.representations)) {
    const seqRep = p.representations.find(r => r.frame_start != null)
    if (seqRep) { frame_start = seqRep.frame_start; frame_end = seqRep.frame_end }
  }

  // Size — new schema uses size_bytes, old uses disk_mb
  const disk_mb = p.stats?.disk_mb
    ?? (p.stats?.size_bytes != null ? Math.round(p.stats.size_bytes / 1048576 * 100) / 100 : null)

  return {
    ...p,
    _normalized: true,
    uuid,
    publish_type,
    created_at,
    created_by,
    outputs: {
      ...(p.outputs ?? {}),
      thumbnail,
      mp4,
    },
    stats: {
      ...(p.stats ?? {}),
      frame_start,
      frame_end,
      disk_mb,
    },
  }
}
