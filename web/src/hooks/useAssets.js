import { useState, useEffect, useCallback } from 'react'

const API_BASE = (() => {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL
  // Same host, port 8765
  const { protocol, hostname } = window.location
  return `${protocol}//${hostname}:8765`
})()

export function useAssets() {
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/assets`)
      if (!res.ok) throw new Error(`Server ${res.status}`)
      const data = await res.json()
      setAssets(data)
    } catch (e) {
      setError(e.message)
      setAssets([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return { assets, loading, error, refresh: load }
}
