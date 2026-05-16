import { Canvas, useFrame } from '@react-three/fiber'
import {
  OrbitControls,
  useGLTF,
  useAnimations,
  Environment,
  ContactShadows,
  Html,
  Bounds,
  useBounds,
} from '@react-three/drei'
import { Suspense, useRef, useEffect, useState, useCallback } from 'react'
import * as THREE from 'three'

// Set Draco decoder path globally once
useGLTF.setDecoderPath('/draco/')

// ----- Camera auto-fit (runs inside Bounds context) -----
function AutoFit() {
  const bounds = useBounds()
  useEffect(() => { bounds.refresh().fit() }, [bounds])
  return null
}

// ----- Loading fallback inside Canvas -----
function Spinner() {
  return (
    <Html center>
      <div className="viewer-spinner">
        <div className="viewer-spinner-ring" />
        <span>Loading model…</span>
      </div>
    </Html>
  )
}

// ----- The actual 3D scene rendered inside Canvas -----
function Scene({ url, animRef, onReady }) {
  const group = useRef()
  const { scene, animations } = useGLTF(url)
  const { actions, mixer, names } = useAnimations(animations, group)

  // Enable shadows + store refs for external control
  useEffect(() => {
    scene.traverse(node => {
      if (node.isMesh) {
        node.castShadow = true
        node.receiveShadow = true
      }
    })
    animRef.current.actions = actions
    animRef.current.mixer = mixer
    animRef.current.names = names
    onReady(names)
  }, [scene, actions, mixer, names])

  // Update scrubber position ref every frame
  useFrame(() => {
    if (mixer) animRef.current._mixerTime = mixer.time
  })

  return (
    <group ref={group}>
      <primitive object={scene} />
    </group>
  )
}

// ----- Error boundary for graceful failure -----
import { Component } from 'react'
class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }
  static getDerivedStateFromError(e) { return { error: e.message } }
  render() {
    if (this.state.error) {
      return (
        <div className="viewer-error">
          <span>Failed to load model</span>
          <small>{this.state.error}</small>
        </div>
      )
    }
    return this.props.children
  }
}

// ----- Main exported component -----
export default function ModelViewer({ url, className = '' }) {
  const controlsRef = useRef()
  const boundsRef = useRef()
  const animRef = useRef({ actions: {}, mixer: null, names: [], _mixerTime: 0 })

  const [clips, setClips] = useState([])
  const [current, setCurrent] = useState('')
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(0)
  const [duration, setDuration] = useState(1)

  // Scrubber polling — 12fps is smooth enough for a timeline UI
  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => {
      const t = animRef.current._mixerTime
      const dur = duration || 1
      setTime(t % dur)
    }, 83)
    return () => clearInterval(id)
  }, [playing, duration])

  // Called once when GLTF + animations are loaded
  const handleReady = useCallback((names) => {
    setClips(names)
    if (names.length > 0) activateClip(names[0])
  }, [])

  function activateClip(name) {
    const { actions } = animRef.current
    Object.values(actions).forEach(a => a.fadeOut(0.2))
    const action = actions[name]
    if (!action) return
    const dur = action._clip.duration
    action.reset().fadeIn(0.2).play()
    setCurrent(name)
    setPlaying(true)
    setDuration(dur)
    setTime(0)
    // Reset mixer time so scrubber starts at 0
    if (animRef.current.mixer) animRef.current.mixer.setTime(0)
  }

  function togglePlay() {
    if (!current && clips.length > 0) { activateClip(clips[0]); return }
    const action = animRef.current.actions[current]
    if (!action) return
    action.paused = !action.paused
    setPlaying(!action.paused)
  }

  function stopAnim() {
    const action = animRef.current.actions[current]
    if (action) { action.stop(); action.reset() }
    setPlaying(false)
    setTime(0)
  }

  function resetAnim() {
    const action = animRef.current.actions[current]
    if (!action) return
    action.reset().play()
    if (animRef.current.mixer) animRef.current.mixer.setTime(0)
    setPlaying(true)
    setTime(0)
  }

  function seek(val) {
    const t = parseFloat(val)
    const action = animRef.current.actions[current]
    if (action) {
      action.time = t
      if (!playing) {
        // Advance the mixer a tiny bit to render the new pose
        animRef.current.mixer?.update(0)
        action.paused = true
      }
    }
    setTime(t)
  }

  function focusModel() {
    boundsRef.current?.refresh().fit()
  }

  function resetCamera() {
    controlsRef.current?.reset()
  }

  return (
    <div className={`model-viewer-wrap ${className}`}>
      <div
        className="model-viewer-canvas"
        onDoubleClick={focusModel}
      >
        <ErrorBoundary>
          <Canvas
            shadows
            camera={{ position: [4, 2, 6], fov: 42 }}
            gl={{
              toneMapping: THREE.ACESFilmicToneMapping,
              toneMappingExposure: 1.0,
              antialias: true,
            }}
            onCreated={({ gl }) => {
              gl.shadowMap.enabled = true
              gl.shadowMap.type = THREE.PCFSoftShadowMap
            }}
          >
            <Suspense fallback={<Spinner />}>
              <Bounds
                ref={boundsRef}
                fit
                clip
                observe
                margin={1.2}
              >
                <AutoFit />
                <Scene url={url} animRef={animRef} onReady={handleReady} />
              </Bounds>
              <Environment preset="warehouse" />
              <ContactShadows
                position={[0, -0.001, 0]}
                opacity={0.6}
                scale={20}
                blur={3}
                far={20}
              />
            </Suspense>

            <OrbitControls
              ref={controlsRef}
              enableDamping
              dampingFactor={0.06}
              makeDefault
            />
          </Canvas>
        </ErrorBoundary>

        <div className="viewer-top-controls">
          <button
            className="viewer-icon-btn"
            onClick={focusModel}
            title="Focus model (or double-click)"
          >
            ⊙
          </button>
          <button
            className="viewer-icon-btn"
            onClick={resetCamera}
            title="Reset camera"
          >
            ⟲
          </button>
        </div>
      </div>

      {clips.length > 0 && (
        <div className="viewer-anim-bar">
          <select
            className="viewer-clip-select"
            value={current}
            onChange={e => activateClip(e.target.value)}
          >
            {clips.map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>

          <button
            className="viewer-icon-btn"
            onClick={resetAnim}
            title="Reset to start"
          >⏮</button>
          <button
            className="viewer-icon-btn"
            onClick={togglePlay}
            title={playing ? 'Pause' : 'Play'}
          >
            {playing ? '⏸' : '▶'}
          </button>
          <button
            className="viewer-icon-btn"
            onClick={stopAnim}
            title="Stop"
          >⏹</button>

          <input
            type="range"
            className="viewer-scrubber"
            min={0}
            max={duration}
            step={0.01}
            value={time}
            onChange={e => seek(e.target.value)}
          />

          <span className="viewer-time">
            {time.toFixed(1)}s / {duration.toFixed(1)}s
          </span>
        </div>
      )}
    </div>
  )
}

// Preload hint — call this from asset cards to warm the GLTF cache
ModelViewer.preload = (url) => useGLTF.preload(url)
