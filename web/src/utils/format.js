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
