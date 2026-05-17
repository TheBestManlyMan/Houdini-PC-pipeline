/**
 * AssetViewer — dispatches to the correct viewer based on asset.format_type:
 *
 *   gltf_static / gltf_animated  →  ModelViewer   (existing GLTF + animation mixer)
 *   vat                          →  VATViewer      (GPU vertex-animation textures)
 *   frame_sequence               →  FrameSequenceViewer (per-frame GLB swap)
 */

import ModelViewer from './ModelViewer.jsx'
import VATViewer from './VATViewer.jsx'
import FrameSequenceViewer from './FrameSequenceViewer.jsx'

export default function AssetViewer({ asset, className = '' }) {
  const { format_type } = asset ?? {}

  if (format_type === 'vat') {
    if (!asset.mesh_url || !asset.vat_pos_url || !asset.vat_json_url) {
      return (
        <div className={`model-viewer-wrap ${className}`}>
          <div className="viewer-error">
            <span>VAT files not found</span>
            <small>mesh.glb / vat_pos.bin / vat.json missing</small>
          </div>
        </div>
      )
    }
    return (
      <VATViewer
        meshUrl={asset.mesh_url}
        vatPosUrl={asset.vat_pos_url}
        vatJsonUrl={asset.vat_json_url}
        className={className}
      />
    )
  }

  if (format_type === 'frame_sequence') {
    if (!asset.frame_sequence_url || !asset.frame_url_template) {
      return (
        <div className={`model-viewer-wrap ${className}`}>
          <div className="viewer-error">
            <span>Frame sequence not found</span>
            <small>frame_sequence.json or frames/ folder missing</small>
          </div>
        </div>
      )
    }
    return (
      <FrameSequenceViewer
        frameSequenceUrl={asset.frame_sequence_url}
        frameUrlTemplate={asset.frame_url_template}
        className={className}
      />
    )
  }

  // Default: GLTF static or animated
  const url = asset?.glb_url
  if (!url) {
    return (
      <div className={`model-viewer-wrap ${className}`}>
        <div className="viewer-error">
          <span>No 3D file available</span>
        </div>
      </div>
    )
  }
  return <ModelViewer url={url} className={className} />
}
