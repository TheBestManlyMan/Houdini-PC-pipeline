// FX File Manager — data layer.
// Fetches live data from the pipeline server; falls back to mock data if unreachable.

const API_BASE = "http://127.0.0.1:8765/api";
let _demoMode = false;

// ─── Mock fallback data ──────────────────────────────────────────────────────

const MOCK_PROJECTS = [
  {
    name: "Loose Lips",   folder: "loose-lips",  fps: 24, resolution: "2048x858",
    color: "#FF7A35",     sequences: ["SQ010", "SQ020", "SQ030"],
    assets: { character: ["hero", "villain"], environment: ["alley", "rooftop"], prop: ["pistol", "case"] },
  },
  {
    name: "Snowman Sim",  folder: "snowman-sim", fps: 24, resolution: "1920x1080",
    color: "#8AC7FF",     sequences: ["SQ010"],
    assets: { character: ["snowman"], environment: ["yard"] },
  },
  {
    name: "Vehicle Reel", folder: "vehicle-reel", fps: 30, resolution: "3840x2160",
    color: "#B5E36A",     sequences: ["SQ010", "SQ020"],
    assets: { vehicle: ["truck", "bike", "drone"] },
  },
];

const MOCK_HIPS = {
  "loose-lips/SQ010/0020": [
    { task: "dust-sim",    version: 1, size: 12_400_000, modified_ts: Date.now()/1000 - 172800, author: "max", desc: "First pass — base velocity field." },
    { task: "dust-sim",    version: 2, size: 14_200_000, modified_ts: Date.now()/1000 - 86400,  author: "max", desc: "Pyro source from anim cache." },
    { task: "dust-sim",    version: 3, size: 14_800_000, modified_ts: Date.now()/1000 - 18000,  author: "max", desc: "Adjusted dissipation, added wind." },
    { task: "dust-sim",    version: 4, size: 15_100_000, modified_ts: Date.now()/1000 - 1920,   author: "max", desc: "Final shading pass + density tweak." },
    { task: "falling-ice", version: 1, size:  9_800_000, modified_ts: Date.now()/1000 - 259200, author: "max", desc: "RBD setup, 240 chunks." },
    { task: "falling-ice", version: 2, size: 10_400_000, modified_ts: Date.now()/1000 - 172800, author: "max", desc: "Glue constraints + ground collision." },
    { task: "falling-ice", version: 3, size: 10_900_000, modified_ts: Date.now()/1000 - 86400,  author: "max", desc: "Secondary chips + dust trails." },
    { task: "smoke-trail", version: 1, size:  7_200_000, modified_ts: Date.now()/1000 - 345600, author: "max", desc: "Pyro lookdev start." },
    { task: "smoke-trail", version: 2, size:  7_900_000, modified_ts: Date.now()/1000 - 86400,  author: "max", desc: "Camera-tracked source." },
    { task: "muzzle-flash",version: 1, size:  3_100_000, modified_ts: Date.now()/1000 - 604800, author: "max", desc: "Quick lookdev — 4 frames." },
  ],
  "loose-lips/SQ010/0010": [
    { task: "dust-sim",    version: 1, size: 11_200_000, modified_ts: Date.now()/1000 - 604800, author: "max", desc: "Establishing wide. First sim." },
    { task: "dust-sim",    version: 2, size: 11_900_000, modified_ts: Date.now()/1000 - 345600, author: "max", desc: "Tightened dissipation." },
  ],
  "loose-lips/SQ010/0030": [
    { task: "smoke-trail", version: 1, size:  6_300_000, modified_ts: Date.now()/1000 - 259200, author: "max", desc: "" },
  ],
  "loose-lips/SQ020/0010": [
    { task: "fire-impact", version: 1, size: 18_300_000, modified_ts: Date.now()/1000 - 432000, author: "max", desc: "Initial Pyro burst." },
    { task: "fire-impact", version: 2, size: 19_100_000, modified_ts: Date.now()/1000 - 172800, author: "max", desc: "Added shockwave + sparks." },
  ],
  "loose-lips/asset/character/hero": [
    { task: "lookdev",     version: 1, size:  4_200_000, modified_ts: Date.now()/1000 - 604800, author: "max", desc: "Material lookdev turntable." },
    { task: "lookdev",     version: 2, size:  4_900_000, modified_ts: Date.now()/1000 - 259200, author: "max", desc: "Hair shader pass." },
    { task: "rig-fx",      version: 1, size:  6_100_000, modified_ts: Date.now()/1000 - 86400,  author: "max", desc: "Cloth + secondary motion rig." },
  ],
  "loose-lips/asset/prop/pistol": [
    { task: "lookdev",     version: 1, size:  2_400_000, modified_ts: Date.now()/1000 - 1209600,author: "max", desc: "Base metal + wear lookdev." },
  ],
};

const MOCK_RECENT = [
  { project: "loose-lips", entity: "SQ010/0020", task: "dust-sim",     version: 4, modified_ts: Date.now()/1000 - 1920 },
  { project: "loose-lips", entity: "SQ010/0020", task: "falling-ice",  version: 3, modified_ts: Date.now()/1000 - 86400 },
  { project: "loose-lips", entity: "SQ020/0010", task: "fire-impact",  version: 2, modified_ts: Date.now()/1000 - 172800 },
  { project: "loose-lips", entity: "asset/character/hero", task: "rig-fx", version: 1, modified_ts: Date.now()/1000 - 86400 },
];

// Project accent colors cycle (server projects have no color field)
const PROJECT_COLORS = ["#FF7A35", "#8AC7FF", "#B5E36A", "#E0A6FF", "#F0C969", "#6FE3C8", "#FF8FA3"];
function projectColor(index) { return PROJECT_COLORS[index % PROJECT_COLORS.length]; }

// ─── Utility functions (exposed globally for components) ─────────────────────

function taskColor(task) {
  const palette = ["#FF7A35","#8AC7FF","#B5E36A","#E0A6FF","#F0C969","#6FE3C8","#FF8FA3","#9DB0FF"];
  let h = 0;
  for (let i = 0; i < task.length; i++) h = (h * 31 + task.charCodeAt(i)) >>> 0;
  return palette[h % palette.length];
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function hipFilename(entity, task, version) {
  const e = entity.replaceAll("/", "_").toLowerCase();
  const v = String(version).padStart(3, "0");
  return `${e}_fx_${task}_v${v}.hip`;
}

function timeAgo(ts) {
  if (!ts) return "unknown";
  const diff = Date.now() / 1000 - ts;
  if (diff < 60)      return "just now";
  if (diff < 3600)    return Math.floor(diff / 60) + "m ago";
  if (diff < 86400)   return Math.floor(diff / 3600) + "h ago";
  if (diff < 172800)  return "yesterday";
  if (diff < 604800)  return Math.floor(diff / 86400) + " days ago";
  if (diff < 1209600) return "1 week ago";
  if (diff < 2592000) return Math.floor(diff / 604800) + " weeks ago";
  return new Date(ts * 1000).toLocaleDateString();
}

function isDemoMode() { return _demoMode; }

// ─── API functions ───────────────────────────────────────────────────────────

async function apiFetch(path) {
  const res = await fetch(API_BASE + path);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function loadProjects() {
  try {
    const raw = await apiFetch("/projects");
    _demoMode = false;
    return raw.map((p, i) => ({
      ...p,
      color: PROJECT_COLORS[i % PROJECT_COLORS.length],
      assets: {},  // loaded separately
    }));
  } catch {
    _demoMode = true;
    return MOCK_PROJECTS;
  }
}

async function loadSequences(folder) {
  if (_demoMode) {
    const p = MOCK_PROJECTS.find(p => p.folder === folder);
    return p ? p.sequences : [];
  }
  try {
    return await apiFetch(`/projects/${folder}/sequences`);
  } catch {
    return [];
  }
}

async function loadShots(folder, seq) {
  if (_demoMode) return SHOTS_BY_SEQ_MOCK[seq] || [];
  try {
    return await apiFetch(`/projects/${folder}/sequences/${seq}/shots`);
  } catch {
    return [];
  }
}

async function loadAssets(folder) {
  if (_demoMode) {
    const p = MOCK_PROJECTS.find(p => p.folder === folder);
    return p ? p.assets : {};
  }
  try {
    return await apiFetch(`/projects/${folder}/assets`);
  } catch {
    return {};
  }
}

async function loadHips(folder, entityPath) {
  // entityPath is either "SEQ/SHOT" or "asset/<type>/<name>"
  const mockKey = `${folder}/${entityPath}`;
  if (_demoMode) {
    return (MOCK_HIPS[mockKey] || []).map(h => ({ ...h, modified: timeAgo(h.modified_ts) }));
  }
  try {
    let raw;
    if (entityPath.startsWith("asset/")) {
      const [, assetType, assetName] = entityPath.split("/");
      raw = await apiFetch(`/projects/${folder}/assets/${assetType}/${assetName}/hips`);
    } else {
      const [seq, shot] = entityPath.split("/");
      raw = await apiFetch(`/projects/${folder}/sequences/${seq}/shots/${shot}/hips`);
    }
    return raw.map(h => ({
      task:        h.task,
      version:     h.version,
      size:        h.size,
      modified_ts: h.modified_ts,
      modified:    timeAgo(h.modified_ts),
      author:      "",
      desc:        "",
      path:        h.path,
      name:        h.name,
    }));
  } catch {
    return (MOCK_HIPS[mockKey] || []).map(h => ({ ...h, modified: timeAgo(h.modified_ts) }));
  }
}

// Mock shots lookup used in demo mode
const SHOTS_BY_SEQ_MOCK = {
  SQ010: ["0010", "0020", "0030", "0040"],
  SQ020: ["0010", "0020", "0030", "0040", "0050", "0060"],
  SQ030: ["0010", "0020"],
};

// Recent files — persisted in localStorage
const RECENT_KEY = "fx-file-manager.recent";
function loadRecent() {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY)) || [];
  } catch { return []; }
}
function saveRecent(entry) {
  // entry: { project, entity, task, version, modified_ts }
  try {
    let recent = loadRecent();
    recent = recent.filter(r => !(r.project === entry.project && r.entity === entry.entity && r.task === entry.task && r.version === entry.version));
    recent.unshift(entry);
    localStorage.setItem(RECENT_KEY, JSON.stringify(recent.slice(0, 20)));
  } catch {}
}

Object.assign(window, {
  API_BASE, MOCK_PROJECTS, MOCK_HIPS, MOCK_RECENT,
  taskColor, formatSize, hipFilename, timeAgo, isDemoMode,
  loadProjects, loadSequences, loadShots, loadAssets, loadHips,
  loadRecent, saveRecent,
});
