/* Injects a real "SU-76" project into MOCK_INDEX with a publish that points
   at the actual GLB file in the GitHub repo. The 3D viewer in the detail panel
   detects `real_glb` on a publish and shows a live <model-viewer>. Runs after mock-data.js. */

(() => {
  if (!window.MOCK_INDEX) return;

  const NOW_ISO = '2026-05-13T00:21:00Z';
  const hoursAgo = (h) => {
    const t = new Date(NOW_ISO);
    t.setHours(t.getHours() - h);
    return t.toISOString().replace(/\.\d+Z$/, 'Z');
  };

  const REAL_GLB_URL = 'https://raw.githubusercontent.com/TheBestManlyMan/Houdini-PC-pipeline/claude/3d-file-preview-lwPZz/su-76.glb';

  const proj = { name: 'SU-76', folder: 'su-76', fps: 24, resolution: '2048x858' };
  window.MOCK_INDEX.projects = [proj, ...window.MOCK_INDEX.projects];

  const thumb = 'data:image/svg+xml;utf8,' + encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180">
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="oklch(24% 0.04 80)"/>
          <stop offset="100%" stop-color="oklch(14% 0.02 100)"/>
        </linearGradient>
      </defs>
      <rect width="320" height="180" fill="url(#g)"/>
      <g fill="none" stroke="oklch(72% 0.13 80)" stroke-width="1" opacity="0.6">
        <rect x="80" y="100" width="160" height="32" rx="2"/>
        <rect x="120" y="68" width="80" height="32"/>
        <path d="M200 84 L260 84"/>
        <circle cx="105" cy="138" r="8"/>
        <circle cx="135" cy="138" r="8"/>
        <circle cx="165" cy="138" r="8"/>
        <circle cx="195" cy="138" r="8"/>
        <circle cx="225" cy="138" r="8"/>
      </g>
      <text x="50%" y="92%" font-family="ui-monospace,monospace" font-size="9"
            fill="oklch(72% 0.13 80)" opacity="0.55"
            text-anchor="middle" letter-spacing="2">SU_76 · MODEL · v001</text>
    </svg>
  `);

  const publish = {
    schema_version: 2,
    uuid: 'pub_su76_real_glb_0001',
    project: 'SU-76',
    context: { type: 'asset', asset_type: 'vehicle', asset: 'su_76' },
    entity: 'su_76',
    task: 'model',
    publish_type: 'usd',
    version: 1,
    created_at: hoursAgo(2),
    created_by: 'maxborg',
    source: {
      hip: '/home/maxborg/projects/shows/su-76/assets/vehicle/su_76/FX/work/houdini/su_76_fx_model_v001.hip',
      houdini_version: '21.0.440',
      rop: '/obj/su_76/render/OUT_model',
      git_commit: '8659d33',
    },
    outputs: {
      thumbnail: thumb,
      mp4: '',
      frames: '',
      usd:    '/home/maxborg/projects/shows/su-76/assets/vehicle/su_76/FX/publish/usd/model/v001/su_76_fx_model_v001.usd',
      cache:  '',
      glb:    REAL_GLB_URL,
    },
    stats: { frame_start: 1, frame_end: 1, disk_mb: 6.6 },
    dependencies: [],
    tags: ['hero', 'final'],
    notes: ['First model publish — interior is placeholder. Treads animated separately.'],
    _index_path: '/home/maxborg/projects/shows/su-76/assets/vehicle/su_76/FX/publish/usd/model/v001',
    _warnings: [],
    _orphaned: false,
    _project_folder: 'su-76',
    real_glb: REAL_GLB_URL,
  };

  window.MOCK_INDEX.publishes = [publish, ...window.MOCK_INDEX.publishes];
  window.MOCK_INDEX.publish_count = window.MOCK_INDEX.publishes.length;
})();
