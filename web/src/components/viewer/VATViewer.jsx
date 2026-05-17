/**
 * VATViewer — plays back Vertex Animation Texture (VAT) simulations.
 *
 * Expects:
 *   meshUrl    — URL to mesh.glb (rest-pose geometry)
 *   vatPosUrl  — URL to vat_pos.bin (Float32 RGBA, width=vertexCount, height=frameCount)
 *   vatJsonUrl — URL to vat.json   (vertex_count, frame_count, fps, frame_start/end, bounds)
 *
 * The vertex shader reads world-space positions directly from the DataTexture using
 * gl_VertexID (WebGL2 / GLSL 3), so this works best with non-indexed geometry typical
 * of Houdini sim output.  Indexed meshes will still render but vertex sharing may cause
 * seams on UV boundaries.
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
// GLSL — GLSL 3 (WebGL2) with texelFetch for exact vertex lookup
// ---------------------------------------------------------------------------

const VAT_VERT = /* glsl */`
uniform highp sampler2D vatTex;
uniform int vatFrame;
uniform int vatVertexCount;

in vec3 position;
in vec3 normal;
in vec2 uv;

out vec3 vNormal;
out vec2 vUv;

void main() {
  int vi = clamp(gl_VertexID, 0, vatVertexCount - 1);
  vec4 posSample = texelFetch(vatTex, ivec2(vi, vatFrame), 0);
  vNormal = normalize(normalMatrix * normal);
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(posSample.xyz, 1.0);
}
`

const VAT_FRAG = /* glsl */`
in vec3 vNormal;
in vec2 vUv;
out vec4 fragColor;

void main() {
  vec3 light = normalize(vec3(1.0, 2.0, 3.0));
  float diff = clamp(dot(vNormal, light), 0.0, 1.0);
  vec3 col = vec3(0.55, 0.60, 0.65) * (0.2 + 0.8 * diff);
  fragColor = vec4(col, 1.0);
}
`

// ---------------------------------------------------------------------------
// AutoFit helper
// ---------------------------------------------------------------------------

function AutoFit() {
  const bounds = useBounds()
  useEffect(() => { bounds.refresh().fit() }, [bounds])
  return null
}

// ---------------------------------------------------------------------------
// Inner scene — loads GLB + DataTexture, applies VAT shader, animates
// ---------------------------------------------------------------------------

function VATScene({ meshUrl, vatPosUrl, vatJsonUrl, animRef, onReady }) {
  const groupRef = useRef()
  const matRef = useRef()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    let mesh = null
    let tex = null

    async function load() {
      const [gltfData, binBuf, vatJson] = await Promise.all([
        new Promise((res, rej) => {
          new GLTFLoader().load(meshUrl, res, undefined, rej)
        }),
        fetch(vatPosUrl).then(r => r.arrayBuffer()),
        fetch(vatJsonUrl).then(r => r.json()),
      ])
      if (cancelled) return

      const { vertex_count, frame_count } = vatJson
      const floats = new Float32Array(binBuf)

      tex = new THREE.DataTexture(
        floats,
        vertex_count,
        frame_count,
        THREE.RGBAFormat,
        THREE.FloatType,
      )
      tex.needsUpdate = true

      const mat = new THREE.ShaderMaterial({
        glslVersion: THREE.GLSL3,
        uniforms: {
          vatTex: { value: tex },
          vatFrame: { value: 0 },
          vatVertexCount: { value: vertex_count },
        },
        vertexShader: VAT_VERT,
        fragmentShader: VAT_FRAG,
        side: THREE.DoubleSide,
      })
      matRef.current = mat

      mesh = gltfData.scene.clone(true)
      mesh.traverse(node => {
        if (!node.isMesh) return
        node.material = mat
        node.castShadow = true
      })

      if (groupRef.current && !cancelled) {
        groupRef.current.add(mesh)
        animRef.current.meta = vatJson
        animRef.current.playing = true
        onReady(vatJson)
        setReady(true)
      }
    }

    load().catch(err => console.error('VATViewer load error:', err))

    return () => {
      cancelled = true
      tex?.dispose()
      matRef.current?.dispose()
    }
  }, [meshUrl, vatPosUrl, vatJsonUrl])

  useFrame((state) => {
    const { meta, playing, speed } = animRef.current
    if (!matRef.current || !meta || !playing) return
    const fps = (meta.fps || 24) * (speed || 1)
    const t = state.clock.getElapsedTime() * fps
    const frame = Math.floor(t % meta.frame_count)
    matRef.current.uniforms.vatFrame.value = frame
    animRef.current._currentFrame = frame
  })

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
          <span>VAT load failed</span>
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

export default function VATViewer({ meshUrl, vatPosUrl, vatJsonUrl, className = '' }) {
  const controlsRef = useRef()
  const boundsRef = useRef()
  const animRef = useRef({ meta: null, playing: true, speed: 1, _currentFrame: 0 })

  const [meta, setMeta] = useState(null)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(1)
  const [frame, setFrame] = useState(0)

  // Poll display frame at 12fps so the UI scrubber stays smooth
  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => setFrame(animRef.current._currentFrame ?? 0), 83)
    return () => clearInterval(id)
  }, [playing])

  const handleReady = useCallback((vatJson) => { setMeta(vatJson) }, [])

  function togglePlay() {
    animRef.current.playing = !animRef.current.playing
    setPlaying(p => !p)
  }

  function changeSpeed(v) {
    animRef.current.speed = v
    setSpeed(v)
  }

  function focusModel() { boundsRef.current?.refresh().fit() }
  function resetCamera() { controlsRef.current?.reset() }

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
                  <span>Loading VAT…</span>
                </div>
              </Html>
            }>
              <Bounds ref={boundsRef} fit clip observe margin={1.2}>
                <AutoFit />
                <VATScene
                  meshUrl={meshUrl}
                  vatPosUrl={vatPosUrl}
                  vatJsonUrl={vatJsonUrl}
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

        <div className="viewer-format-badge vat">VAT Simulation</div>
      </div>

      {meta && (
        <div className="viewer-anim-bar">
          <button className="viewer-icon-btn" onClick={togglePlay} title={playing ? 'Pause' : 'Play'}>
            {playing ? '⏸' : '▶'}
          </button>

          <span className="viewer-time">
            {frame} / {meta.frame_count - 1}
          </span>

          <input
            type="range"
            className="viewer-scrubber"
            min={0}
            max={meta.frame_count - 1}
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
            {meta.fps}fps · {meta.vertex_count?.toLocaleString()} verts
          </span>
        </div>
      )}
    </div>
  )
}
