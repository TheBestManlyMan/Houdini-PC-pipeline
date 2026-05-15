import { useState, useMemo } from 'react'

const DEFAULTS = {
  search: '',
  publishType: '',
  status: '',
  task: '',
  entity: '',
  project: '',
}

function matchesFilters(pub, filters) {
  const q = filters.search.toLowerCase()
  if (q && !`${pub.entity} ${pub.task} ${pub.publish_type} ${pub.project} ${pub.created_by} ${pub.notes?.join(' ')}`.toLowerCase().includes(q))
    return false
  if (filters.publishType && pub.publish_type !== filters.publishType) return false
  if (filters.status && (pub.status ?? 'review') !== filters.status) return false
  if (filters.task && pub.task !== filters.task) return false
  if (filters.entity && pub.entity !== filters.entity) return false
  if (filters.project && pub.project !== filters.project) return false
  return true
}

export function useFilters(publishes) {
  const [filters, setFilters] = useState(DEFAULTS)

  const filtered = useMemo(
    () => publishes.filter(p => matchesFilters(p, filters)),
    [publishes, filters]
  )

  function setFilter(key, value) {
    setFilters(f => ({ ...f, [key]: value }))
  }

  function clearFilters() {
    setFilters(DEFAULTS)
  }

  return { filtered, filters, setFilter, clearFilters }
}
