export function versionLabel(v) {
  return `v${String(v).padStart(3, '0')}`
}

export function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export function formatMb(mb) {
  if (!mb) return '—'
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`
}

export function publishTypeColor(type) {
  return {
    cache: '#4ae2a0',
    flipbook: '#e2c24a',
    render: '#4a90e2',
    usd: '#a04ae2',
    hip: '#e2a04a',
  }[type] ?? '#888'
}
