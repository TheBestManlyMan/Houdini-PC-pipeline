"""
Houdini FX Pipeline — Publish Gallery Generator.
Scans all project entity roots for publish_meta.json files and writes gallery.html.

Usage:
    python publish_gallery.py [output.html]
    Defaults to {pipeline_root}/gallery.html, then opens it in the browser.
"""

import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def _find_entity_roots(projects_root: Path, projects: list) -> list:
    roots = []
    for proj in projects:
        folder = proj.get("folder", "")
        proj_name = proj.get("name", folder)
        proj_dir = projects_root / folder
        if not proj_dir.exists():
            continue

        # Shots: {proj}/{seq}/{shot}/FX/  (entity_root = FX dir)
        for seq_dir in proj_dir.iterdir():
            if not seq_dir.is_dir() or seq_dir.name == "assets":
                continue
            for shot_dir in seq_dir.iterdir():
                if not shot_dir.is_dir():
                    continue
                fx = shot_dir / "FX"
                if fx.exists():
                    entity_root = fx
                elif (shot_dir / "houdini").exists() or (shot_dir / "preview").exists():
                    entity_root = shot_dir  # legacy layout without FX/
                else:
                    continue
                roots.append({
                    "project": proj_name,
                    "entity_type": "shot",
                    "context": f"{seq_dir.name}/{shot_dir.name}",
                    "entity_root": entity_root,
                })

        # Assets: {proj}/assets/{asset_type}/{asset}/FX/
        assets_dir = proj_dir / "assets"
        if assets_dir.exists():
            for type_dir in assets_dir.iterdir():
                if not type_dir.is_dir():
                    continue
                for asset_dir in type_dir.iterdir():
                    if not asset_dir.is_dir():
                        continue
                    fx = asset_dir / "FX"
                    if fx.exists():
                        roots.append({
                            "project": proj_name,
                            "entity_type": "asset",
                            "context": f"{type_dir.name}/{asset_dir.name}",
                            "entity_root": fx,
                        })

    return roots


def _pub_type(meta: dict) -> str:
    if meta.get("publish_name") == "flipbook":
        return "flipbook"
    if "rop_name" in meta:
        return "render"
    return "asset"


def _find_media(meta_path: Path, meta: dict, pub_type: str) -> tuple:
    meta_dir = meta_path.parent

    def first_jpg(d):
        d = Path(d)
        if d.exists():
            jpgs = sorted(d.glob("*.jpg"))
            return jpgs[0].as_uri() if jpgs else None
        return None

    def first_mp4(d):
        d = Path(d)
        if d.exists():
            mp4s = sorted(d.glob("*.mp4"))
            return mp4s[0].as_uri() if mp4s else None
        return None

    if pub_type == "flipbook":
        return first_jpg(meta_dir), first_mp4(meta_dir)

    mp4_str = meta.get("preview_mp4")
    thumb = None
    mp4 = None
    if mp4_str:
        mp4_p = Path(mp4_str)
        if mp4_p.exists():
            mp4 = mp4_p.as_uri()
        thumb = first_jpg(mp4_p.parent)
    if not thumb:
        thumb = first_jpg(meta_dir)
    return thumb, mp4


def collect(projects_root: Path, projects: list) -> list:
    roots = _find_entity_roots(projects_root, projects)
    items = []
    for root_info in roots:
        for meta_path in root_info["entity_root"].rglob("publish_meta.json"):
            try:
                meta = json.loads(meta_path.read_text())
            except Exception:
                continue
            pt = _pub_type(meta)
            thumb, mp4 = _find_media(meta_path, meta, pt)
            items.append({
                "project": root_info["project"],
                "entity_type": root_info["entity_type"],
                "context": root_info["context"],
                "pub_type": pt,
                "entity": meta.get("entity", ""),
                "task": meta.get("task", ""),
                "publish_name": meta.get("publish_name", ""),
                "fmt": meta.get("fmt", pt),
                "version": meta.get("version", 0),
                "published_by": meta.get("published_by", ""),
                "published_at": meta.get("published_at", ""),
                "description": meta.get("description", ""),
                "frame_start": meta.get("frame_start"),
                "frame_end": meta.get("frame_end"),
                "thumbnail": thumb,
                "mp4": mp4,
            })
    items.sort(key=lambda x: x["published_at"], reverse=True)
    return items


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>FX Pipeline — Publish Gallery</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:#111;color:#ddd;min-height:100vh;
}

/* ---- Header ---- */
header{
  padding:16px 28px;background:#161616;
  border-bottom:1px solid #202020;
  display:flex;align-items:center;gap:12px;
}
header h1{font-size:17px;font-weight:600;color:#eee;letter-spacing:.02em}
header .pipe-dot{color:#333;font-size:18px}
header .subtitle{font-size:11px;color:#444;margin-left:auto}

/* ---- Controls ---- */
.controls{
  padding:12px 28px;background:#161616;
  border-bottom:1px solid #1c1c1c;
  display:flex;gap:8px;flex-wrap:wrap;align-items:center;
}

.search{
  flex:1;min-width:180px;
  background:#1a1a1a;border:1px solid #282828;border-radius:6px;
  color:#ddd;padding:7px 12px;font-size:13px;outline:none;
  transition:border-color .15s;
}
.search:focus{border-color:#3a3a3a}
.search::placeholder{color:#3a3a3a}

select{
  background:#1a1a1a;border:1px solid #282828;border-radius:6px;
  color:#bbb;padding:7px 10px;font-size:13px;outline:none;cursor:pointer;
}

.type-btns{display:flex;gap:3px}
.type-btn{
  background:#1a1a1a;border:1px solid #252525;border-radius:5px;
  color:#666;padding:6px 11px;font-size:12px;cursor:pointer;
  font-weight:500;transition:all .12s;
}
.type-btn:hover{border-color:#383838;color:#bbb}
.type-btn.active{border-color:#444;color:#eee;background:#232323}
.type-btn[data-type=flipbook].active{border-color:#c04060;color:#e06080;background:#200e14}
.type-btn[data-type=render].active{border-color:#b09030;color:#d0b040;background:#201a08}
.type-btn[data-type=asset].active{border-color:#30a070;color:#50c090;background:#081a12}

.count{font-size:11px;color:#383838;margin-left:auto;white-space:nowrap}

/* ---- Grid ---- */
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(268px,1fr));
  gap:14px;padding:20px 28px;
}

.empty{
  grid-column:1/-1;text-align:center;
  padding:80px 20px;color:#333;font-size:14px;
}

/* ---- Card ---- */
.card{
  background:#181818;border:1px solid #222;border-radius:8px;
  overflow:hidden;cursor:pointer;
  transition:border-color .15s,transform .1s,box-shadow .15s;
}
.card:hover{
  border-color:#333;transform:translateY(-2px);
  box-shadow:0 8px 24px rgba(0,0,0,.4);
}

/* ---- Thumbnail ---- */
.thumb{
  position:relative;width:100%;padding-top:56.25%;
  background:#0d0d0d;overflow:hidden;
}
.thumb img,.thumb video{
  position:absolute;inset:0;width:100%;height:100%;object-fit:cover;
}
.thumb .no-preview{
  position:absolute;inset:0;display:flex;
  align-items:center;justify-content:center;
  color:#2a2a2a;font-size:12px;letter-spacing:.05em;
}
.play-icon{
  position:absolute;bottom:8px;right:8px;
  width:26px;height:26px;border-radius:50%;
  background:rgba(0,0,0,.65);
  display:flex;align-items:center;justify-content:center;
  font-size:9px;color:#fff;
  opacity:0;transition:opacity .15s;pointer-events:none;
}
.card:hover .play-icon{opacity:1}

/* ---- Card body ---- */
.card-body{padding:9px 11px 11px}

.badges{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:7px}
.badge{
  font-size:9px;font-weight:700;letter-spacing:.05em;
  padding:2px 5px;border-radius:3px;color:#fff;text-transform:uppercase;
}

.badge.type-flipbook{background:#6a1a30}
.badge.type-render{background:#6a5010}
.badge.type-asset{background:#0e4a28}

.badge.fmt-usd{background:#173a6a}
.badge.fmt-abc{background:#6a3a10}
.badge.fmt-bgeo{background:#0e4a30}
.badge.fmt-vdb{background:#3a1070}
.badge.fmt-flipbook{background:#5a1028}
.badge.fmt-render{background:#6a5010}

.badge.ver{background:transparent;border:1px solid #2c2c2c;color:#555}

.card-title{
  font-size:13px;font-weight:600;color:#dedede;margin-bottom:2px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.card-context{
  font-size:10px;color:#444;margin-bottom:6px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.card-meta{font-size:10px;color:#383838;margin-bottom:4px}
.card-desc{
  font-size:11px;color:#555;line-height:1.45;
  display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden;
}
.frame-range{font-size:10px;color:#333;margin-top:4px}
</style>
</head>
<body>

<header>
  <h1>FX Publish Gallery</h1>
  <span class="pipe-dot">/</span>
  <span id="gen-time" style="font-size:12px;color:#555"></span>
  <span class="subtitle">Houdini PC Pipeline</span>
</header>

<div class="controls">
  <input class="search" id="search" type="text" placeholder="Search entity, task, description…">
  <select id="proj-filter"><option value="">All projects</option></select>
  <div class="type-btns">
    <button class="type-btn active" data-type="">All</button>
    <button class="type-btn" data-type="flipbook">Flipbook</button>
    <button class="type-btn" data-type="render">Render</button>
    <button class="type-btn" data-type="asset">Asset</button>
  </div>
  <span class="count" id="count"></span>
</div>

<div class="grid" id="grid"></div>

<script>
const PUBLISHES = __DATA__;
const GEN_TIME  = __GENTIME__;

document.getElementById('gen-time').textContent =
  new Date(GEN_TIME).toLocaleString(undefined, {
    month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'
  });

function fmtKey(pub) {
  if (pub.pub_type === 'flipbook') return 'flipbook';
  if (pub.pub_type === 'render')   return 'render';
  return pub.fmt || 'asset';
}

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(undefined,
    {month:'short',day:'numeric',year:'numeric'});
}

function pad3(n) { return String(n).padStart(3,'0'); }

function makeCard(pub) {
  const card = document.createElement('div');
  card.className = 'card';

  // --- thumbnail / video ---
  const thumb = document.createElement('div');
  thumb.className = 'thumb';

  if (pub.mp4) {
    const video = document.createElement('video');
    video.src = pub.mp4;
    if (pub.thumbnail) video.poster = pub.thumbnail;
    video.muted = true;
    video.loop  = true;
    video.playsInline = true;
    video.preload = 'none';
    thumb.appendChild(video);

    card.addEventListener('mouseenter', () => video.play().catch(()=>{}));
    card.addEventListener('mouseleave', () => { video.pause(); video.currentTime = 0; });

    const icon = document.createElement('div');
    icon.className = 'play-icon';
    icon.textContent = '▶';
    thumb.appendChild(icon);

    card.addEventListener('click', () => window.open(pub.mp4, '_blank'));

  } else if (pub.thumbnail) {
    const img = document.createElement('img');
    img.src = pub.thumbnail;
    img.alt = '';
    img.loading = 'lazy';
    thumb.appendChild(img);
  } else {
    const np = document.createElement('div');
    np.className = 'no-preview';
    np.textContent = 'NO PREVIEW';
    thumb.appendChild(np);
  }

  card.appendChild(thumb);

  // --- body ---
  const body = document.createElement('div');
  body.className = 'card-body';

  // badges
  const badges = document.createElement('div');
  badges.className = 'badges';

  const typeBadge = document.createElement('span');
  typeBadge.className = 'badge type-' + pub.pub_type;
  typeBadge.textContent = pub.pub_type;
  badges.appendChild(typeBadge);

  const fk = fmtKey(pub);
  const fmtBadge = document.createElement('span');
  fmtBadge.className = 'badge fmt-' + fk;
  fmtBadge.textContent = fk.toUpperCase();
  badges.appendChild(fmtBadge);

  const verBadge = document.createElement('span');
  verBadge.className = 'badge ver';
  verBadge.textContent = 'v' + pad3(pub.version);
  badges.appendChild(verBadge);

  body.appendChild(badges);

  // title
  const title = document.createElement('div');
  title.className = 'card-title';
  const parts = [pub.entity, pub.task];
  if (pub.publish_name && pub.publish_name !== pub.task && pub.publish_name !== 'flipbook') {
    parts.push(pub.publish_name);
  }
  title.textContent = parts.join(' · ');
  body.appendChild(title);

  // context
  const ctx = document.createElement('div');
  ctx.className = 'card-context';
  ctx.textContent = pub.project + '  ·  ' + pub.entity_type + '  ·  ' + pub.context;
  body.appendChild(ctx);

  // date / user
  const meta = document.createElement('div');
  meta.className = 'card-meta';
  meta.textContent = [formatDate(pub.published_at), pub.published_by].filter(Boolean).join('  ·  ');
  body.appendChild(meta);

  // description
  if (pub.description) {
    const desc = document.createElement('div');
    desc.className = 'card-desc';
    desc.title = pub.description;
    desc.textContent = pub.description;
    body.appendChild(desc);
  }

  // frame range
  if (pub.frame_start != null && pub.frame_end != null) {
    const fr = document.createElement('div');
    fr.className = 'frame-range';
    fr.textContent = 'frames ' + pub.frame_start + '–' + pub.frame_end;
    body.appendChild(fr);
  }

  card.appendChild(body);
  return card;
}

// populate project filter
const projs = [...new Set(PUBLISHES.map(p => p.project))].sort();
const projSel = document.getElementById('proj-filter');
projs.forEach(p => {
  const o = document.createElement('option');
  o.value = p; o.textContent = p;
  projSel.appendChild(o);
});

let activeType = '', activeProject = '', searchQuery = '';

function render() {
  const grid = document.getElementById('grid');
  grid.innerHTML = '';

  const q = searchQuery.toLowerCase();
  const filtered = PUBLISHES.filter(p => {
    if (activeType && p.pub_type !== activeType) return false;
    if (activeProject && p.project !== activeProject) return false;
    if (q) {
      const hay = [p.entity, p.task, p.publish_name, p.description, p.context, p.project]
        .join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  document.getElementById('count').textContent =
    filtered.length + ' of ' + PUBLISHES.length;

  if (!filtered.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'No publishes found.';
    grid.appendChild(empty);
    return;
  }

  filtered.forEach(p => grid.appendChild(makeCard(p)));
}

document.querySelectorAll('.type-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.type-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeType = btn.dataset.type;
    render();
  });
});

projSel.addEventListener('change', e => {
  activeProject = e.target.value;
  render();
});

let searchTimer;
document.getElementById('search').addEventListener('input', e => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { searchQuery = e.target.value; render(); }, 150);
});

render();
</script>
</body>
</html>
"""


def generate_html(publishes: list) -> str:
    data_json = json.dumps(publishes, ensure_ascii=False)
    gen_time  = json.dumps(datetime.now().isoformat())
    return _HTML.replace("__DATA__", data_json).replace("__GENTIME__", gen_time)


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else _PIPELINE_ROOT / "gallery.html"
    proj_root = pipeline.projects_root()
    projects  = pipeline.load_projects()
    print(f"Scanning: {proj_root}")
    publishes = collect(proj_root, projects)
    print(f"Found {len(publishes)} publish(es).")
    html = generate_html(publishes)
    output.write_text(html, encoding="utf-8")
    print(f"Gallery written: {output}")
    webbrowser.open(output.as_uri())


if __name__ == "__main__":
    main()
