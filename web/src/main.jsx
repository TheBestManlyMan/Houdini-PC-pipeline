import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './styles/global.css'

const STORAGE_KEY = 'pipeline-view-override'

// Coarse-pointer + small-viewport check — no UA sniffing needed.
function checkMobileViewport() {
  return (
    window.matchMedia('(max-width: 720px)').matches ||
    window.matchMedia('(pointer: coarse) and (max-width: 900px)').matches
  )
}

// Read ?view= param once at startup; persist it to localStorage.
function resolveViewOverride() {
  const param = new URLSearchParams(window.location.search).get('view')
  if (param === 'mobile' || param === 'desktop') {
    localStorage.setItem(STORAGE_KEY, param)
    return param
  }
  return localStorage.getItem(STORAGE_KEY) // 'mobile' | 'desktop' | null
}

const MobileBoardApp = React.lazy(() => import('./mobile/BoardApp.jsx'))

function Root() {
  const [isMobile, setIsMobile] = useState(() => {
    const override = resolveViewOverride()
    if (override === 'mobile')  return true
    if (override === 'desktop') return false
    return checkMobileViewport()
  })

  useEffect(() => {
    // Only listen to resize events when no manual override is in effect.
    if (resolveViewOverride()) return

    const mq1 = window.matchMedia('(max-width: 720px)')
    const mq2 = window.matchMedia('(pointer: coarse) and (max-width: 900px)')
    const update = () => setIsMobile(checkMobileViewport())

    mq1.addEventListener('change', update)
    mq2.addEventListener('change', update)
    return () => {
      mq1.removeEventListener('change', update)
      mq2.removeEventListener('change', update)
    }
  }, [])

  if (isMobile) {
    return (
      <React.Suspense fallback={null}>
        <MobileBoardApp/>
      </React.Suspense>
    )
  }

  return <App/>
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root/>
  </React.StrictMode>
)
