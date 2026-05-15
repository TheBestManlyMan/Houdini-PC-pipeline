// Mock index — matches python/pipeline/indexer.py output shape (schema v2).
//
// Top-level: { project, folder, indexed_at, publish_count, publishes:[…], projects:[…] }
// Each publish: { uuid, schema_version, project, context, entity, task,
//                 publish_type, version, created_at, created_by,
//                 source:{hip,rop,git_commit,houdini_version},
//                 outputs:{thumbnail,mp4,frames,usd,cache},
//                 stats:{frame_start,frame_end,disk_mb},
//                 dependencies:[{type,publish_uuid}], tags:[], notes:[],
//                 wedge?:{parameter,value},
//                 _index_path, _warnings:[], _orphaned }

(() => {
  const PROJECTS_ROOT = '/home/maxborg/projects/shows';
  const USERS = ['maxborg', 'jchen', 'lwakefield'];
  const NOW = new Date('2026-05-13T00:21:00Z');

  // ──────────────── procedural thumbnail (inline SVG data URI) ────────────────
  const swatch = (hue, label, seed) => {
    const c1 = `oklch(${22 + (seed % 8)}% 0.04 ${hue})`;
    const c2 = `oklch(${38 + (seed % 18)}% 0.09 ${hue})`;
    const c3 = `oklch(${62 + (seed % 12)}% 0.13 ${hue})`;
    const grain = Array.from({ length: 14 }, (_, i) => {
      const x = ((seed * 31 + i * 73) % 100);
      const y = ((seed * 17 + i * 41) % 100);
      const r = 0.5 + ((seed + i) % 4) * 0.4;
      const op = 0.05 + ((seed + i) % 5) * 0.04;
      return `<circle cx="${x}%" cy="${y}%" r="${r}" fill="${c3}" opacity="${op}"/>`;
    }).join('');
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180">
        <defs>
          <linearGradient id="g${seed}" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="${c1}"/>
            <stop offset="60%" stop-color="${c2}"/>
            <stop offset="100%" stop-color="${c3}"/>
          </linearGradient>
          <radialGradient id="r${seed}" cx="${30 + (seed % 50)}%" cy="${30 + (seed % 40)}%" r="60%">
            <stop offset="0%" stop-color="${c3}" stop-opacity="0.55"/>
            <stop offset="100%" stop-color="${c1}" stop-opacity="0"/>
          </radialGradient>
        </defs>
        <rect width="320" height="180" fill="url(#g${seed})"/>
        <rect width="320" height="180" fill="url(#r${seed})"/>
        ${grain}
        <text x="50%" y="92%" font-family="ui-monospace,monospace" font-size="9" fill="${c3}" opacity="0.5" text-anchor="middle" letter-spacing="2">${label}</text>
      </svg>`
    );
  };

  // ──────────────── projects ────────────────
  const PROJECTS = [
    { name: 'Reel',         folder: 'reel',         fps: 24, resolution: '1920x1080', hue: 220 },
    { name: 'Kaiju v2',     folder: 'kaiju-v2',     fps: 24, resolution: '2048x858',  hue: 25 },
    { name: 'Neon City',    folder: 'neon-city',    fps: 30, resolution: '1920x1080', hue: 320 },
    { name: 'Sandbox',      folder: 'sandbox',      fps: 24, resolution: '1280x720',  hue: 150 },
  ];

  // ──────────────── entity seeds ────────────────
  // [project_folder, context, entity, task, [publish_types,...]]
  const ENTITY_SEEDS = [
    // Reel — SNOW sequence
    ['reel', { type:'shot', sequence:'SNOW', shot:'SNOW_0010' }, 'SNOW_0010', 'snowman-sim',     ['cache','flipbook']],
    ['reel', { type:'shot', sequence:'SNOW', shot:'SNOW_0010' }, 'SNOW_0010', 'snow-master',     ['cache','usd','flipbook']],
    ['reel', { type:'shot', sequence:'SNOW', shot:'SNOW_0010' }, 'SNOW_0010', 'beauty',          ['render','flipbook']],
    ['reel', { type:'shot', sequence:'SNOW', shot:'SNOW_0020' }, 'SNOW_0020', 'avalanche-sim',   ['cache','flipbook','hip']],
    ['reel', { type:'shot', sequence:'SNOW', shot:'SNOW_0020' }, 'SNOW_0020', 'dust-secondary',  ['cache','flipbook']],
    ['reel', { type:'shot', sequence:'SNOW', shot:'SNOW_0030' }, 'SNOW_0030', 'wind-streaks',    ['cache']],

    // Kaiju — KJU010/020
    ['kaiju-v2', { type:'shot', sequence:'KJU010', shot:'KJU010_0020' }, 'KJU010_0020', 'water-destroy', ['cache','flipbook','render']],
    ['kaiju-v2', { type:'shot', sequence:'KJU010', shot:'KJU010_0020' }, 'KJU010_0020', 'splash-detail', ['cache','flipbook']],
    ['kaiju-v2', { type:'shot', sequence:'KJU010', shot:'KJU010_0030' }, 'KJU010_0030', 'foam-spray',    ['cache','flipbook']],
    ['kaiju-v2', { type:'shot', sequence:'KJU010', shot:'KJU010_0030' }, 'KJU010_0030', 'beauty',        ['render','flipbook']],
    ['kaiju-v2', { type:'shot', sequence:'KJU020', shot:'KJU020_0010' }, 'KJU020_0010', 'destruction',   ['cache','flipbook','hip']],
    ['kaiju-v2', { type:'shot', sequence:'KJU020', shot:'KJU020_0040' }, 'KJU020_0040', 'firebreath',    ['cache','flipbook','render']],

    // Kaiju — assets
    ['kaiju-v2', { type:'asset', asset_type:'character',  asset:'kaiju' },       'kaiju',        'model',   ['usd','hip']],
    ['kaiju-v2', { type:'asset', asset_type:'character',  asset:'kaiju' },       'kaiju',        'lookdev', ['render','usd']],
    ['kaiju-v2', { type:'asset', asset_type:'prop',       asset:'city-blocks' }, 'city-blocks',  'model',   ['usd']],
    ['kaiju-v2', { type:'asset', asset_type:'environment',asset:'harbor' },      'harbor',       'model',   ['usd']],

    // Neon City
    ['neon-city', { type:'shot', sequence:'NEO004', shot:'NEO004_0010' }, 'NEO004_0010', 'rain-streaks', ['cache','flipbook']],
    ['neon-city', { type:'shot', sequence:'NEO004', shot:'NEO004_0010' }, 'NEO004_0010', 'splatter',     ['cache','flipbook']],
    ['neon-city', { type:'shot', sequence:'NEO004', shot:'NEO004_0010' }, 'NEO004_0010', 'beauty',       ['render']],
    ['neon-city', { type:'shot', sequence:'NEO006', shot:'NEO006_0050' }, 'NEO006_0050', 'sparks',       ['cache','flipbook']],
    ['neon-city', { type:'asset', asset_type:'prop', asset:'sign-array' }, 'sign-array', 'model',        ['usd']],

    // Sandbox
    ['sandbox', { type:'asset', asset_type:'misc',  asset:'torus-test' }, 'torus-test', 'lookdev',   ['render']],
    ['sandbox', { type:'shot',  sequence:'TEST',   shot:'TEST_heat'   }, 'TEST_heat',  'pyro-quick', ['cache','flipbook']],
  ];

  // ──────────────── note pools ────────────────
  const NOTE_POOLS = {
    'snowman-sim':    ['First sim pass — coarse voxels.', 'Tuned vorticity, more turbulent.', 'Sourced from layout v005.'],
    'snow-master':    ['Master sourcing snow+dust+wind.', 'Replaced source, less choppy.', 'Final master for screening.'],
    'avalanche-sim':  ['Coarse approval pass.', 'High-res sim, ~3hr bake.', 'Re-sim after collider fix.'],
    'water-destroy':  ['Flip sim, 6m particles.', 'New source curve, less stairstep.', 'Final — please pixar-screen.'],
    'splash-detail':  ['Whitewater pass.', 'Tuned vorticity.', 'Cleanup pass for B-side.'],
    'foam-spray':     ['Spray emitter test.', 'Final foam over flip surface.'],
    'destruction':    ['Voronoi pass, no constraints.', 'With glue constraints.', 'Final destruction approved.'],
    'firebreath':     ['Pyro flame look R&D.', 'New temperature ramp.', 'Final firebreath.'],
    'rain-streaks':   ['Rain master.', 'Reduced streak length.'],
    'beauty':         ['Lookdev beauty render.', 'Final beauty for comp.', 'Holdout pass added.'],
    'model':          ['Base mesh, ready for shading.', 'Topology fix on neck.', 'UV repack.'],
    'lookdev':        ['Roughness wedge.', 'New flake shader.', 'Final lookdev for sign-off.'],
    'dust-secondary': ['Coarse pass.', 'Increased emission.', 'Final dust master.'],
  };

  const TAG_POOL = {
    cache:    ['proxy', 'final', 'rebake', 'wedge'],
    flipbook: ['review', 'dailies', 'low-res', 'final'],
    render:   ['beauty', 'holdout', 'crypto', 'AOV', 'wedge'],
    usd:      ['hero', 'proxy', 'final'],
    hip:      ['snapshot', 'wip'],
  };

  // ──────────────── helpers ────────────────
  const uuid = (() => { let n = 0xc0ffee; return () => 'pub_' + (n++).toString(16).padStart(8,'0') + Math.floor(Math.random()*65536).toString(16).padStart(4,'0'); })();
  const pick = (arr, seed) => arr[seed % arr.length];

  const minusHours = (h) => {
    const t = new Date(NOW);
    t.setHours(t.getHours() - h);
    return t.toISOString().replace(/\.\d+Z$/, 'Z');
  };

  // ──────────────── build publishes ────────────────
  const publishes = [];
  let id = 0;

  ENTITY_SEEDS.forEach(([folder, context, entity, task, types]) => {
    const project = PROJECTS.find(p => p.folder === folder);
    types.forEach(publish_type => {
      const versions = 1 + Math.floor(Math.random() * 3); // 1..3 versions
      for (let v = 1; v <= versions; v++) {
        id += 1;

        // Build entity_root + version dir paths matching real layout
        const ctxPath = context.type === 'shot'
          ? `${context.sequence}/${context.shot}`
          : `assets/${context.asset_type}/${context.asset}`;
        const entityRoot = `${PROJECTS_ROOT}/${folder}/${ctxPath}/FX`;
        const verName = `v${String(v).padStart(3,'0')}`;
        const folderFmt = ({ cache:'geo', flipbook:'flipbook', render:'render', usd:'usd', hip:'houdini' })[publish_type];
        const pubName = publish_type === 'hip' ? 'main' : (publish_type === 'render' ? 'beauty' : publish_type);
        const topDir = publish_type === 'flipbook' ? 'preview' : 'publish';
        const verDir = `${entityRoot}/${topDir}/${folderFmt}/${task}/${pubName}/${verName}`;

        // Outputs
        const isAnimated = publish_type !== 'usd' && publish_type !== 'hip';
        const fStart = isAnimated ? 1001 : 1;
        const fEnd   = isAnimated ? (1001 + 40 + Math.floor(Math.random() * 120)) : 1;
        const hasMp4 = publish_type === 'flipbook' || publish_type === 'render';

        // Asset USD publishes carry a lightweight proxy GLB for browser 3D preview.
        // Real path: ${verDir}/proxy.glb — mock data uses a public demo asset.
        const hasProxy = context.type === 'asset' && publish_type === 'usd';

        const outputs = {
          thumbnail: swatch(project.hue + (id * 7) % 30, `${entity} · ${task} · ${verName}`, id),
          mp4: hasMp4 ? '__demo__' : '',
          frames: isAnimated ? `${verDir}/${entity}_fx_${task}_${pubName}_${verName}.$F4.${publish_type === 'flipbook' ? 'jpg' : 'exr'}` : '',
          usd:    publish_type === 'usd' ? `${verDir}/${entity}_fx_${task}_${pubName}_${verName}.usd` : '',
          cache:  publish_type === 'cache' ? `${verDir}/${entity}_fx_${task}_${pubName}_${verName}.$F4.bgeo.sc` : '',
          glb:    hasProxy ? 'https://modelviewer.dev/shared-assets/models/Astronaut.glb' : '',
        };

        // Stats
        const stats = {
          frame_start: isAnimated ? fStart : 1,
          frame_end:   isAnimated ? fEnd   : 1,
          disk_mb: Math.round((publish_type === 'render' ? 800 : publish_type === 'cache' ? 350 : 40) * (0.6 + Math.random() * 1.4)),
        };

        // Source
        const hipName = `${entity}_fx_${task}_${verName}.hip`;
        const source = {
          hip: `${PROJECTS_ROOT}/${folder}/${ctxPath}/FX/work/houdini/${hipName}`,
          houdini_version: '21.0.440',
          rop: publish_type === 'render' ? `/obj/${entity}/render/OUT_${pubName}` : (publish_type === 'cache' ? `/obj/${entity}/${task}/OUT_${pubName}` : ''),
          git_commit: ['9c2a3b1', 'a4f6e09', '57bdc2d', '113e85f'][id % 4],
        };

        // Notes
        const notesArr = NOTE_POOLS[task] || [];
        const notes = notesArr.length ? [notesArr[(id + v) % notesArr.length]] : [];

        // Tags
        const tagPool = TAG_POOL[publish_type] || [];
        const tags = tagPool.length ? [tagPool[(id) % tagPool.length]] : [];
        if (v === versions && Math.random() < 0.4) tags.push('latest');

        // Warnings (some publishes are flagged)
        const _warnings = [];
        if (publish_type === 'cache' && Math.random() < 0.12) _warnings.push('missing_preview_mp4');
        if (publish_type === 'usd'   && Math.random() < 0.18) _warnings.push('missing_thumbnail');
        if (Math.random() < 0.05) _warnings.push('missing_metadata');

        // Wedge (rare)
        let wedge;
        if ((publish_type === 'cache' || publish_type === 'render') && Math.random() < 0.15) {
          wedge = {
            parameter: pick(['vorticity', 'particle_separation', 'flame_intensity', 'collide_friction', 'gravity_y'], id),
            value: [0.25, 0.5, 1.0, 1.5, 2.0][v % 5],
          };
        }

        publishes.push({
          schema_version: 2,
          uuid: uuid(),
          project: project.name,
          context,
          entity,
          task,
          publish_type,
          version: v,
          created_at: minusHours(Math.floor(Math.random() * 24 * 30) + (versions - v) * 18),
          created_by: pick(USERS, id + v),
          source,
          outputs,
          stats,
          dependencies: [], // filled after all publishes exist
          tags,
          notes,
          ...(wedge ? { wedge } : {}),
          _index_path: verDir,
          _warnings,
          _orphaned: false,
          // Project folder convenience (used by sidebar grouping; not part of real schema)
          _project_folder: folder,
        });
      }
    });
  });

  // ──────────────── wire some dependencies ────────────────
  // Renders/flipbooks often depend on a cache; masters depend on inputs.
  publishes.forEach(p => {
    if (p.publish_type === 'render' || p.publish_type === 'flipbook') {
      const cache = publishes.find(c =>
        c.publish_type === 'cache' &&
        c.entity === p.entity &&
        c.task === p.task &&
        c.version <= p.version
      );
      if (cache) p.dependencies.push({ type: 'sources', publish_uuid: cache.uuid });
    }
    if (p.task === 'snow-master') {
      const inputs = publishes.filter(c =>
        c.publish_type === 'cache' &&
        c.entity === p.entity &&
        ['snowman-sim'].includes(c.task) &&
        c.version === c.version
      ).slice(0, 1);
      inputs.forEach(i => p.dependencies.push({ type: 'merges', publish_uuid: i.uuid }));
    }
  });

  // ──────────────── sort newest first ────────────────
  publishes.sort((a, b) => b.created_at.localeCompare(a.created_at));

  // ──────────────── final index payload ────────────────
  window.MOCK_INDEX = {
    project: 'All Projects',
    folder: null,
    indexed_at: NOW.toISOString().replace(/\.\d+Z$/, 'Z'),
    publish_count: publishes.length,
    publishes,
    projects: PROJECTS.map(({ hue, ...rest }) => rest),
  };
})();
