// Demo data for the Pipeline Manager — used when the FastAPI server isn't reachable.
// Mirrors the server's response shapes:
//   GET  /projects                                  → [{name, folder, fps, resolution, sequences[]}]
//   GET  /projects/{f}/sequences                    → ["SEQ", ...]
//   GET  /projects/{f}/sequences/{s}/shots          → ["SHOT", ...]
//   GET  /projects/{f}/assets                       → {type: [asset, ...]}
//   GET  /publishes?project=…                       → [publish records]
//
// The manager mutates this in-memory only; nothing touches the filesystem in demo mode.

(() => {
  const projects = [
    {
      name: 'Reel', folder: 'reel', fps: 24, resolution: '1920x1080',
      sequences: ['SNOW', 'BEACH'],
    },
    {
      name: 'Kaiju v2', folder: 'kaiju-v2', fps: 24, resolution: '2048x858',
      sequences: ['KJU010', 'KJU020'],
    },
    {
      name: 'Neon City', folder: 'neon-city', fps: 30, resolution: '1920x1080',
      sequences: ['NEO004', 'NEO006'],
    },
    {
      name: 'Sandbox', folder: 'sandbox', fps: 24, resolution: '1280x720',
      sequences: ['TEST'],
    },
  ];

  const shots = {
    'reel/SNOW':        ['SNOW_0010', 'SNOW_0020', 'SNOW_0030'],
    'reel/BEACH':       ['BEACH_0010'],
    'kaiju-v2/KJU010':  ['KJU010_0020', 'KJU010_0030'],
    'kaiju-v2/KJU020':  ['KJU020_0010', 'KJU020_0040'],
    'neon-city/NEO004': ['NEO004_0010'],
    'neon-city/NEO006': ['NEO006_0050'],
    'sandbox/TEST':     ['TEST_heat'],
  };

  const assets = {
    'reel':      {},
    'kaiju-v2':  {
      character:   ['kaiju'],
      prop:        ['city-blocks'],
      environment: ['harbor'],
    },
    'neon-city': { prop: ['sign-array'] },
    'sandbox':   { misc: ['torus-test'] },
  };

  // Rough publish count per project — used by the Overview tab.
  const publishCounts = { 'reel': 14, 'kaiju-v2': 22, 'neon-city': 9, 'sandbox': 4 };

  // ─── public surface — mimics the fetch responses ────────────────────────
  window.PIPELINE_MOCK = {
    listProjects: () => structuredClone(projects),

    createProject: ({ name, folder, fps, resolution }) => {
      const slug = (folder || name).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      if (projects.some(p => p.folder === slug)) throw new Error(`Project '${slug}' already exists.`);
      const p = { name, folder: slug, fps: fps || 24, resolution: resolution || '1920x1080', sequences: [] };
      projects.push(p);
      assets[slug] = {};
      publishCounts[slug] = 0;
      return p;
    },

    deleteProject: (folder) => {
      const i = projects.findIndex(p => p.folder === folder);
      if (i < 0) throw new Error(`Project '${folder}' not found.`);
      projects.splice(i, 1);
      delete assets[folder];
      delete publishCounts[folder];
      Object.keys(shots).forEach(k => { if (k.startsWith(folder + '/')) delete shots[k]; });
    },

    listSequences: (folder) => {
      const p = projects.find(p => p.folder === folder);
      return p ? [...p.sequences] : [];
    },

    createSequence: (folder, seq) => {
      const p = projects.find(p => p.folder === folder);
      if (!p) throw new Error(`Project '${folder}' not found.`);
      const code = seq.trim().toUpperCase();
      if (!code) throw new Error('Sequence code is required.');
      if (p.sequences.includes(code)) throw new Error(`Sequence '${code}' already exists.`);
      p.sequences.push(code);
      shots[`${folder}/${code}`] = [];
      return code;
    },

    deleteSequence: (folder, seq) => {
      const p = projects.find(p => p.folder === folder);
      if (!p) return;
      p.sequences = p.sequences.filter(s => s !== seq);
      delete shots[`${folder}/${seq}`];
    },

    listShots: (folder, seq) => [...(shots[`${folder}/${seq}`] || [])],

    createShot: (folder, seq, shot) => {
      const key = `${folder}/${seq}`;
      const code = shot.trim();
      if (!code) throw new Error('Shot code is required.');
      shots[key] = shots[key] || [];
      if (shots[key].includes(code)) throw new Error(`Shot '${code}' already exists.`);
      shots[key].push(code);
      shots[key].sort();
      return code;
    },

    deleteShot: (folder, seq, shot) => {
      const key = `${folder}/${seq}`;
      if (shots[key]) shots[key] = shots[key].filter(s => s !== shot);
    },

    listAssets: (folder) => structuredClone(assets[folder] || {}),

    createAssetType: (folder, type) => {
      assets[folder] = assets[folder] || {};
      const t = type.trim().toLowerCase();
      if (!t) throw new Error('Asset type is required.');
      assets[folder][t] = assets[folder][t] || [];
      return t;
    },

    deleteAssetType: (folder, type) => {
      if (assets[folder]) delete assets[folder][type];
    },

    createAsset: (folder, type, asset) => {
      const code = asset.trim();
      if (!code) throw new Error('Asset name is required.');
      assets[folder] = assets[folder] || {};
      assets[folder][type] = assets[folder][type] || [];
      if (assets[folder][type].includes(code)) throw new Error(`Asset '${code}' already exists.`);
      assets[folder][type].push(code);
      assets[folder][type].sort();
      return code;
    },

    deleteAsset: (folder, type, asset) => {
      if (assets[folder]?.[type]) assets[folder][type] = assets[folder][type].filter(a => a !== asset);
    },

    publishCount: (folder) => publishCounts[folder] || 0,
  };
})();
