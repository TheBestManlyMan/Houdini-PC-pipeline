/**
 * FrameSequenceViewer — plays a per-frame GLB sequence for topology-changing sims
 * (FLIP, pyro mesh, vellum tearing).
 *
 * Preloads all frames into memory and swaps the Three.js scene graph each frame
 * without React re-renders (mutations happen inside useFrame).
 *
 * Props:
 *   frameSequenceUrl  — URL to frame_sequence.json
 *   frameUrlTemplate  — URL template: "…/frames/frame_{frame}.glb"
 *                       {frame} is replaced with the zero-padded frame number.
 */

import { Canvas, useFrame } from '@react-three/fiber'
import {
  OrbitControls,
  Environment,
  ContactShadows,
  Html,
  Bounds,
  useBounds,
} from '@react-three/drei'
import { Suspense, useRef, useEffect, useState, useCallback, Component } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

// ---------------------------------------------------------------------------
// AutoFit helper
// ---------------------------------------------------------------------------

function AutoFit() {
  const bounds = useBounds()
  useEffect(() => { bounds.refresh().fit() }, [bounds])
  return null
}

// ---------------------------------------------------------------------------
// Inner scene — preloads all frames then swaps geometry each frame
// ---------------------------------------------------------------------------

function FrameScene({ seqMeta, frameUrlTemplate, animRef, onReady }) {
  const { frame_start, frame_end, frame_count } = seqMeta
  const groupRef = useRef()
  const cacheRef = useRef({})          // frame# → THREE.Object3D (cloned scene)
  const currentFrameRef = useRef(-1)
  const [loadProgress, setLoadProgress] = useState(0)
  const [allLoaded, setAllLoaded] = useState(false)

  useEffect(() => {
    const loader = new GLTFLoader()
    let loadedCount = 0
    let cancelled = false

    for (let f = frame_start; f <= frame_end; f++) {
      const frame = f
      const frameStr = String(frame).padStart(4, '0')
      const url = frameUrlTemplate.replace('{frame}', frameStr)

      loader.load(url, (gltf) => {
        if (cancelled) return
        const scene = gltf.scene.clone(true)
        scene.traverse(node => { if (node.isMesh) node.castShadow = true })
        cacheRef.current[frame] = scene
        loadedCount++
        setLoadProgress(loadedCount)
        if (loadedCount === frame_count) {
          setAllLoaded(true)
          onReady()
        }
      }, undefined, (err) => {
        console.warn(`FrameSequence: failed to load frame ${frame}:`, err)
        loadedCount++
        if (loadedCount === frame_count) {
          setAllLoaded(true)
          onReady()
        }
      })
    }

    return () => {
      cancelled = true
      Object.values(cacheRef.current).forEach(obj => {
        obj.traverse(n => { n.geometry?.dispose(); n.material?.dispose() })
      })
      cacheRef.current = {}
    }
  }, [frameUrlTemplate, frame_start, frame_end, frame_count])

  useFrame((state) => {
    if (!allLoaded || !groupRef.current) return
    const { playing, speed } = animRef.current
    if (!playing) return

    const fps = (seqMeta.fps ?? 24) * (speed || 1)
    const elapsed = state.clock.getElapsedTime()
    const targetFrame = frame_start + (Math.floor(elapsed * fps) % frame_count)

    if (targetFrame === currentFrameRef.current) return
    currentFrameRef.current = targetFrame
    animRef.current._currentFrame = targetFrame

    // Swap scene graph — no React setState, so no re-render overhead
    while (groupRef.current.children.length > 0) {
      groupRef.current.remove(groupRef.current.children[0])
    }
    const next = cacheRef.current[targetFrame]
    if (next) groupRef.current.add(next)
  })

  // Show loading progress inside the canvas while frames stream in
  if (!allLoaded) {
    return (
      <Html center>
        <div className="viewer-spinner">
          <div className="viewer-spinner-ring" />
          <span>Loading frames {loadProgress} / {frame_count}…</span>
        </div>
      </Html>
    )
  }

  return <group ref={groupRef} />
}

// ---------------------------------------------------------------------------
// Error boundary
// ---------------------------------------------------------------------------

class ErrBound extends Component {
  constructor(props) { super(props); this.state = { err: null } }
  static getDerivedStateFromError(e) { return { err: e.message } }
  render() {
    if (this.state.err) {
      return (
        <div className="viewer-error">
          <span>Frame sequence load failed</span>
          <small>{this.state.err}</small>
        </div>
      )
    }
    return this.props.children
  }
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export default function FrameSequenceViewer({ frameSequenceUrl, frameUrlTemplate, className = '' }) {
  const controlsRef = useRef()
  const boundsRef = useRef()
  const animRef = useRef({ playing: true, speed: 1, _currentFrame: 0 })

  const [seqMeta, setSeqMeta] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(1)
  const [frame, setFrame] = useState(0)

  // Fetch sequence manifest
  useEffect(() => {
    fetch(frameSequenceUrl)
      .then(r => r.json())
      .then(setSeqMeta)
      .catch(e => setLoadError(e.message))
  }, [frameSequenceUrl])

  // Poll display frame at 12fps for UI
  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => setFrame(animRef.current._currentFrame ?? 0), 83)
    return () => clearInterval(id)
  }, [playing])

  function togglePlay() {
    animRef.current.playing = !animRef.current.playing
    setPlaying(p => !p)
  }

  function changeSpeed(v) {
    animRef.current.speed = v
    setSpeed(v)
  }

  const handleReady = useCallback(() => {}, [])

  function focusModel() { boundsRef.current?.refresh().fit() }
  function resetCamera() { controlsRef.current?.reset() }

  if (loadError) {
    return (
      <div className={`model-viewer-wrap ${className}`}>
        <div className="viewer-error">
          <span>Failed to load sequence manifest</span>
          <small>{loadError}</small>
        </div>
      </div>
    )
  }

  if (!seqMeta) {
    return (
      <div className={`model-viewer-wrap ${className}`}>
        <div className="viewer-error">
          <div className="viewer-spinner-ring" style={{ margin: '0 auto 8px' }} />
          <span style={{ color: 'var(--text-3)', fontSize: 12 }}>Loading sequence…</span>
        </div>
      </div>
    )
  }

  const totalFrames = seqMeta.frame_count ?? (seqMeta.frame_end - seqMeta.frame_start + 1)

  return (
    <div className={`model-viewer-wrap ${className}`}>
      <div className="model-viewer-canvas" onDoubleClick={focusModel}>
        <ErrBound>
          <Canvas
            shadows
            camera={{ position: [4, 2, 6], fov: 42 }}
            gl={{
              toneMapping: THREE.ACESFilmicToneMapping,
              toneMappingExposure: 1.0,
              antialias: true,
            }}
          >
            <Suspense fallback={
              <Html center>
                <div className="viewer-spinner">
                  <div className="viewer-spinner-ring" />
                  <span>Initialising…</span>
                </div>
              </Html>
            }>
              <Bounds ref={boundsRef} fit clip observe margin={1.2}>
                <AutoFit />
                <FrameScene
                  seqMeta={seqMeta}
                  frameUrlTemplate={frameUrlTemplate}
                  animRef={animRef}
                  onReady={handleReady}
                />
              </Bounds>
              <Environment preset="warehouse" />
              <ContactShadows position={[0, -0.001, 0]} opacity={0.5} scale={20} blur={3} far={20} />
            </Suspense>
            <OrbitControls ref={controlsRef} enableDamping dampingFactor={0.06} makeDefault />
          </Canvas>
        </ErrBound>

        <div className="viewer-top-controls">
          <button className="viewer-icon-btn" onClick={focusModel} title="Focus">⊙</button>
          <button className="viewer-icon-btn" onClick={resetCamera} title="Reset camera">⟲</button>
        </div>

        <div className="viewer-format-badge frame-seq">Frame Sequence</div>
      </div>

      <div className="viewer-anim-bar">
        <button className="viewer-icon-btn" onClick={togglePlay} title={playing ? 'Pause' : 'Play'}>
          {playing ? '⏸' : '▶'}
        </button>

        <span className="viewer-time">
          {frame} / {totalFrames - 1}
        </span>

        <input
          type="range"
          className="viewer-scrubber"
          min={seqMeta.frame_start}
          max={seqMeta.frame_end}
          step={1}
          value={frame}
          readOnly
        />

        <select
          className="viewer-clip-select"
          value={speed}
          onChange={e => changeSpeed(parseFloat(e.target.value))}
          title="Playback speed"
        >
          <option value={0.25}>0.25×</option>
          <option value={0.5}>0.5×</option>
          <option value={1}>1×</option>
          <option value={2}>2×</option>
        </select>

        <span className="viewer-time" style={{ color: 'var(--text-4)' }}>
          {totalFrames} frames
        </span>
      </div>
    </div>
  )
}
