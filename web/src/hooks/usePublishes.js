import { useState, useEffect, useCallback } from 'react'
import { demoIndex } from '../data/demoIndex.js'
import { normalizePublish } from '../utils/format.js'

const INDEX_BASE = import.meta.env.VITE_INDEX_BASE ?? ''
const DEFAULT_API = import.meta.env.VITE_API_BASE ?? `http://${window.location.hostname}:8765/api`

function timeoutSignal(ms) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), ms)
  return { signal: ctrl.signal, clear: () => clearTimeout(timer) }
}

async function fetchJson(url, timeout = 2500) {
  const t = timeoutSignal(timeout)
  try {
    const res = await fetch(url, { signal: t.signal })
    if (!res.ok) throw new Error(`HTTP ${res.status} — ${url}`)
    return res.json()
  } finally {
    t.clear()
  }
}

function params() {
  return new URLSearchParams(window.location.search)
}

async function fetchIndex(projectFolder) {
  const search = params()
  if (search.get('mock') === '1') {
    return { data: demoIndex, mode: 'mock', source: 'Demo data' }
  }

  const explicitIndex = search.get('index')
  if (explicitIndex) {
    return { data: await fetchJson(explicitIndex, 5000), mode: 'static', source: explicitIndex }
  }

  const apiBase = (search.get('api') || localStorage.getItem('pipeline-api-base') || DEFAULT_API).replace(/\/+$/, '')
  try {
    const [publishes, projects] = await Promise.all([
      fetchJson(`${apiBase}/publishes`, 2600),
      fetchJson(`${apiBase}/projects`, 2600).catch(() => []),
    ])
    return {
      data: {
        project: 'Live',
        folder: 'live',
        indexed_at: new Date().toISOString(),
        publish_count: publishes.length,
        publishes,
        projects,
      },
      mode: 'live',
      source: apiBase,
    }
  } catch (liveError) {
    if (INDEX_BASE) {
      const url = projectFolder
        ? `${INDEX_BASE}/${projectFolder}/.pipeline/publishes.json`
        : `${INDEX_BASE}/publishes.json`
      try {
        return { data: await fetchJson(url, 5000), mode: 'static', source: url }
      } catch {
        // Fall through to demo data with the live error; it is more actionable.
      }
    }
    return {
      data: demoIndex,
      mode: 'mock',
      source: 'Demo data',
      warning: `Pipeline server unreachable at ${apiBase}; showing demo data.`,
      error: liveError.message,
    }
  }
}

export function usePublishes(projectFolder) {
  const [state, setState] = useState({
    publishes: [],
    projects: [],
    index: null,
    mode: 'mock',
    source: '',
    warning: '',
    loading: true,
    error: null,
  })

  const load = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: null }))
    try {
      const result = await fetchIndex(projectFolder)
      const data = result.data
      setState({
        publishes: (data.publishes ?? []).map(normalizePublish),
        projects: data.projects ?? [],
        index: data,
        mode: result.mode,
        source: result.source,
        warning: result.warning ?? '',
        loading: false,
        error: null,
      })
    } catch (e) {
      setState({
        publishes: (demoIndex.publishes ?? []).map(normalizePublish),
        projects: demoIndex.projects,
        index: demoIndex,
        mode: 'mock',
        source: 'Demo data',
        warning: '',
        loading: false,
        error: e.message,
      })
    }
  }, [projectFolder])

  useEffect(() => { load() }, [load])

  return { ...state, refresh: load }
}
