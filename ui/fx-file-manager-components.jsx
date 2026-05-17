// FX File Manager — leaf components.

const { useState, useEffect, useMemo, useRef } = React;

// ─── Icons ───────────────────────────────────────────────────────────────────
const Icon = ({ name, size = 16 }) => {
  const paths = {
    folder:      <path d="M2 4.5A1.5 1.5 0 0 1 3.5 3h3.379a1.5 1.5 0 0 1 1.06.44l.621.62a1.5 1.5 0 0 0 1.06.44H12.5A1.5 1.5 0 0 1 14 6v6.5A1.5 1.5 0 0 1 12.5 14h-9A1.5 1.5 0 0 1 2 12.5v-8Z" />,
    chevron:     <path d="m6 4 4 4-4 4" />,
    chevronDown: <path d="m4 6 4 4 4-4" />,
    search:      <><circle cx="7" cy="7" r="4.5" /><path d="m10.5 10.5 3 3" /></>,
    plus:        <><path d="M8 3v10" /><path d="M3 8h10" /></>,
    open:        <><path d="M3 3h5" /><path d="M3 3v5" /><path d="m3 3 6 6" /><path d="M13 13H8" /><path d="M13 13V8" /><path d="m13 13-6-6" /></>,
    copy:        <><rect x="5" y="5" width="8" height="8" rx="1" /><path d="M3 11V4a1 1 0 0 1 1-1h7" /></>,
    reveal:      <path d="M2 4.5A1.5 1.5 0 0 1 3.5 3h3l1.5 1.5h4A1.5 1.5 0 0 1 13.5 6v6A1.5 1.5 0 0 1 12 13.5H3.5A1.5 1.5 0 0 1 2 12V4.5Z" />,
    shot:        <><rect x="2" y="4" width="9" height="8" rx="1" /><path d="m11 7 3-2v6l-3-2z" /></>,
    asset:       <><path d="M8 2 14 5v6l-6 3-6-3V5z" /><path d="M2 5l6 3 6-3" /><path d="M8 8v6" /></>,
    star:        <path d="M8 2.5l1.8 3.7 4.1.6-3 2.9.7 4.1L8 11.9l-3.6 1.9.7-4.1-3-2.9 4.1-.6z" />,
    clock:       <><circle cx="8" cy="8" r="6" /><path d="M8 4.5V8l2.5 1.5" /></>,
    cog:         <><circle cx="8" cy="8" r="2.5" /><path d="M8 1.5v2M8 12.5v2M14.5 8h-2M3.5 8h-2M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4M12.6 12.6l-1.4-1.4M4.8 4.8 3.4 3.4" /></>,
    sync:        <><path d="M3 8a5 5 0 0 1 8.5-3.5L13 6" /><path d="M13 3v3h-3" /><path d="M13 8a5 5 0 0 1-8.5 3.5L3 10" /><path d="M3 13v-3h3" /></>,
    dot:         <circle cx="8" cy="8" r="3" />,
    box:         <><path d="M2 5 8 2l6 3v6l-6 3-6-3z" /><path d="M2 5l6 3 6-3" /><path d="M8 8v6" /></>,
    hip:         <><rect x="2.5" y="2.5" width="11" height="11" rx="1.5" /><path d="M5.5 5.5h5M5.5 8h5M5.5 10.5h3" /></>,
    close:       <><path d="m4 4 8 8" /><path d="m12 4-8 8" /></>,
    warning:     <><path d="M8 3 1.5 13.5h13z" /><path d="M8 7v3.5" /><circle cx="8" cy="12" r=".75" fill="currentColor" /></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none"
      stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      {paths[name]}
    </svg>
  );
};

// ─── Version pill ─────────────────────────────────────────────────────────────
const VersionPill = ({ version, latest = false, color }) => (
  <span style={{
    fontFamily: "var(--mono)", fontSize: 11, fontWeight: 600,
    padding: "2px 7px", borderRadius: 4,
    background: latest ? color : "rgba(255,255,255,0.05)",
    color: latest ? "#0F1012" : "var(--text-dim)",
    letterSpacing: 0.2, lineHeight: 1.4,
  }}>v{String(version).padStart(3, "0")}</span>
);

// ─── Project switcher ─────────────────────────────────────────────────────────
const ProjectSwitcher = ({ projects, active, onChange }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef();
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);
  if (!active) return null;
  return (
    <div ref={ref} style={{ position: "relative", padding: "10px 12px 8px" }}>
      <button onClick={() => setOpen(!open)} style={{
        width: "100%", display: "flex", alignItems: "center", gap: 10,
        padding: "8px 10px", borderRadius: 6,
        background: open ? "var(--panel-3)" : "var(--panel-2)",
        border: "1px solid var(--border)", cursor: "pointer",
        color: "var(--text)", textAlign: "left",
      }}>
        <div style={{
          width: 22, height: 22, borderRadius: 5, background: active.color,
          display: "flex", alignItems: "center", justifyContent: "center",
          color: "#0F1012", fontWeight: 700, fontSize: 11, flexShrink: 0,
        }}>{active.name.split(" ").map(w => w[0]).join("").slice(0, 2)}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{active.name}</div>
          <div style={{ fontSize: 10.5, color: "var(--text-mute)", fontFamily: "var(--mono)", letterSpacing: 0.2 }}>
            {active.resolution} · {active.fps}fps
          </div>
        </div>
        <Icon name="chevronDown" size={14} />
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "100%", left: 12, right: 12, marginTop: 4,
          background: "var(--panel-3)", border: "1px solid var(--border)",
          borderRadius: 7, boxShadow: "0 10px 30px rgba(0,0,0,0.45)", zIndex: 50,
          overflow: "hidden",
        }}>
          {projects.map((p, i) => (
            <div key={p.folder} onClick={() => { onChange(p); setOpen(false); }} style={{
              display: "flex", alignItems: "center", gap: 10, padding: "8px 10px",
              cursor: "pointer", background: p.folder === active.folder ? "rgba(255,255,255,0.04)" : "transparent",
              borderBottom: i < projects.length - 1 ? "1px solid var(--border)" : "none",
            }}
            onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.06)"}
            onMouseLeave={e => e.currentTarget.style.background = p.folder === active.folder ? "rgba(255,255,255,0.04)" : "transparent"}>
              <div style={{
                width: 20, height: 20, borderRadius: 4, background: p.color,
                display: "flex", alignItems: "center", justifyContent: "center",
                color: "#0F1012", fontWeight: 700, fontSize: 10,
              }}>{p.name.split(" ").map(w => w[0]).join("").slice(0, 2)}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12.5, fontWeight: 500 }}>{p.name}</div>
                <div style={{ fontSize: 10, color: "var(--text-mute)", fontFamily: "var(--mono)" }}>{p.folder}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── Tree row ─────────────────────────────────────────────────────────────────
const TreeRow = ({ icon, label, level = 0, expanded, hasChildren, selected, badge, onClick, color }) => (
  <div onClick={onClick} style={{
    display: "flex", alignItems: "center", gap: 6,
    padding: "4px 12px 4px " + (10 + level * 14) + "px",
    cursor: "pointer", userSelect: "none",
    background: selected ? "var(--row-sel)" : "transparent",
    color: selected ? "var(--text)" : "var(--text-dim)",
    fontSize: 12.5, lineHeight: 1.4,
    borderLeft: selected ? "2px solid var(--accent)" : "2px solid transparent",
  }}
  onMouseEnter={e => { if (!selected) e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
  onMouseLeave={e => { if (!selected) e.currentTarget.style.background = "transparent"; }}>
    <div style={{ width: 12, display: "flex", alignItems: "center", color: "var(--text-mute)" }}>
      {hasChildren ? <Icon name={expanded ? "chevronDown" : "chevron"} size={11} /> : null}
    </div>
    {icon && <div style={{ color: color || "var(--text-mute)", display: "flex" }}><Icon name={icon} size={13} /></div>}
    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: selected ? 600 : 400 }}>{label}</span>
    {badge != null && (
      <span style={{
        fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-mute)",
        padding: "0 5px", borderRadius: 3, background: "rgba(255,255,255,0.04)",
      }}>{badge}</span>
    )}
  </div>
);

const SectionLabel = ({ children, right }) => (
  <div style={{
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "12px 14px 4px", fontSize: 10.5, fontWeight: 600,
    letterSpacing: 0.8, textTransform: "uppercase", color: "var(--text-mute)",
  }}>
    <span>{children}</span>{right}
  </div>
);

// ─── Breadcrumbs ──────────────────────────────────────────────────────────────
const Crumb = ({ children, active, onClick }) => (
  <span onClick={onClick} style={{
    cursor: onClick ? "pointer" : "default",
    color: active ? "var(--text)" : "var(--text-dim)",
    fontWeight: active ? 600 : 400, fontSize: 13,
  }}>{children}</span>
);

const Breadcrumbs = ({ parts }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
    {parts.map((p, i) => (
      <React.Fragment key={i}>
        {i > 0 && <span style={{ color: "var(--text-mute)", fontSize: 11 }}>/</span>}
        <Crumb active={i === parts.length - 1} onClick={p.onClick}>{p.label}</Crumb>
      </React.Fragment>
    ))}
  </div>
);

// ─── Tab row ──────────────────────────────────────────────────────────────────
const TabRow = ({ tabs, active, onChange }) => (
  <div style={{ display: "flex", gap: 2, padding: 3, background: "var(--panel-2)", borderRadius: 7, border: "1px solid var(--border)" }}>
    {tabs.map(t => (
      <button key={t.key} onClick={() => onChange(t.key)} style={{
        padding: "5px 12px", fontSize: 12, fontWeight: 500,
        background: active === t.key ? "var(--panel-4)" : "transparent",
        color: active === t.key ? "var(--text)" : "var(--text-dim)",
        border: "none", borderRadius: 5, cursor: "pointer",
        display: "flex", alignItems: "center", gap: 6,
      }}>
        {t.label}
        {t.count != null && (
          <span style={{
            fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-mute)",
            padding: "0 5px", borderRadius: 3, background: "rgba(255,255,255,0.04)",
          }}>{t.count}</span>
        )}
      </button>
    ))}
  </div>
);

// ─── Hip row ──────────────────────────────────────────────────────────────────
const HipRow = ({ hip, entity, latest, selected, density, onSelect, onOpen }) => {
  const filename = hipFilename(entity, hip.task, hip.version);
  const padding = density === "compact" ? "5px 12px" : "9px 12px";
  return (
    <div onClick={onSelect} onDoubleClick={onOpen} style={{
      display: "grid",
      gridTemplateColumns: "minmax(0,1fr) 56px 70px 90px 70px",
      gap: 12, alignItems: "center", padding,
      cursor: "pointer", userSelect: "none",
      background: selected ? "var(--row-sel)" : "transparent",
      borderLeft: selected ? "2px solid var(--accent)" : "2px solid transparent",
      borderBottom: "1px solid var(--border-soft)",
    }}
    onMouseEnter={e => { if (!selected) e.currentTarget.style.background = "rgba(255,255,255,0.025)"; }}
    onMouseLeave={e => { if (!selected) e.currentTarget.style.background = "transparent"; }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
        <Icon name="hip" size={14} />
        <span style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: latest ? 600 : 400 }}>
          {filename}
        </span>
        {latest && <span style={{ fontSize: 10, color: "var(--accent)", fontWeight: 600, letterSpacing: 0.5, textTransform: "uppercase" }}>latest</span>}
      </div>
      <VersionPill version={hip.version} latest={latest} color={taskColor(hip.task)} />
      <span style={{ fontFamily: "var(--mono)", fontSize: 11.5, color: "var(--text-dim)" }}>{formatSize(hip.size)}</span>
      <span style={{ fontSize: 12, color: "var(--text-dim)" }}>{hip.modified || timeAgo(hip.modified_ts)}</span>
      <span style={{ fontFamily: "var(--mono)", fontSize: 11.5, color: "var(--text-mute)" }}>{hip.author || "—"}</span>
    </div>
  );
};

// ─── Task group ───────────────────────────────────────────────────────────────
const TaskGroup = ({ task, hips, entity, selectedKey, onSelect, onOpen, density }) => {
  const [expanded, setExpanded] = useState(true);
  const color = taskColor(task);
  const latestVersion = Math.max(...hips.map(h => h.version));
  const totalSize = hips.reduce((s, h) => s + (h.size || 0), 0);
  return (
    <div>
      <div onClick={() => setExpanded(!expanded)} style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "10px 12px 8px", cursor: "pointer", userSelect: "none",
        background: "var(--panel-2)", borderBottom: "1px solid var(--border)",
      }}>
        <div style={{ color: "var(--text-mute)", display: "flex" }}>
          <Icon name={expanded ? "chevronDown" : "chevron"} size={11} />
        </div>
        <div style={{ width: 4, height: 14, borderRadius: 1.5, background: color }} />
        <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text)", whiteSpace: "nowrap" }}>{task}</span>
        <span style={{ fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--text-mute)", padding: "1px 6px", borderRadius: 3, background: "rgba(255,255,255,0.04)", whiteSpace: "nowrap" }}>
          {hips.length} version{hips.length !== 1 ? "s" : ""}
        </span>
        <div style={{ flex: 1 }} />
        <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-mute)", whiteSpace: "nowrap" }}>
          latest v{String(latestVersion).padStart(3, "0")}
        </span>
        {totalSize > 0 && <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-mute)", whiteSpace: "nowrap" }}>{formatSize(totalSize)}</span>}
      </div>
      {expanded && hips.map(h => {
        const key = `${h.task}_v${h.version}`;
        return (
          <HipRow key={key} hip={h} entity={entity}
            latest={h.version === latestVersion}
            selected={selectedKey === key}
            density={density}
            onSelect={() => onSelect(key)}
            onOpen={() => onOpen(h)} />
        );
      })}
    </div>
  );
};

// ─── Detail pane ──────────────────────────────────────────────────────────────
const ghostBtnStyle = {
  flex: 1, padding: "7px 10px", borderRadius: 5,
  background: "var(--panel-3)", border: "1px solid var(--border)",
  color: "var(--text-dim)", fontSize: 12, cursor: "pointer",
  display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
};

const DetailPane = ({ selected, allVersions, entity, onOpen, onCopyPath, onReveal, onNewVersion }) => {
  if (!selected) {
    return (
      <div style={{
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        height: "100%", padding: 24, gap: 12, color: "var(--text-mute)",
      }}>
        <div style={{ width: 56, height: 56, borderRadius: 10, background: "var(--panel-2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon name="hip" size={26} />
        </div>
        <div style={{ fontSize: 13, textAlign: "center", lineHeight: 1.5, maxWidth: 220 }}>
          Select a hip file to see its details, version history, and actions.
        </div>
      </div>
    );
  }
  const color = taskColor(selected.task);
  const filename = hipFilename(entity, selected.task, selected.version);
  const fullPath = selected.path || `…/FX/work/houdini/${filename}`;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Preview area */}
      <div style={{
        position: "relative",
        background: `linear-gradient(135deg, ${color}22, transparent 60%), repeating-linear-gradient(45deg, var(--panel-2), var(--panel-2) 6px, var(--panel-3) 6px, var(--panel-3) 12px)`,
        height: 168, flexShrink: 0, borderBottom: "1px solid var(--border)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <div style={{ textAlign: "center" }}>
          <div style={{
            width: 48, height: 48, borderRadius: 10, background: color, margin: "0 auto 10px",
            display: "flex", alignItems: "center", justifyContent: "center", color: "#0F1012",
            boxShadow: `0 8px 24px ${color}55`,
          }}>
            <Icon name="hip" size={22} />
          </div>
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-mute)", letterSpacing: 1, textTransform: "uppercase" }}>
            no preview yet
          </div>
        </div>
        <div style={{ position: "absolute", top: 10, left: 10, fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-mute)", letterSpacing: 0.5 }}>
          .hip · houdini scene
        </div>
        <div style={{ position: "absolute", top: 10, right: 10 }}>
          <VersionPill version={selected.version} latest color={color} />
        </div>
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "14px 16px" }}>
        <div style={{ fontFamily: "var(--mono)", fontSize: 12.5, fontWeight: 600, color: "var(--text)", lineHeight: 1.4, wordBreak: "break-all" }}>
          {filename}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
          <span style={{ width: 6, height: 6, borderRadius: 3, background: color }} />
          <span style={{ fontSize: 12, color: "var(--text-dim)" }}>{selected.task}</span>
          <span style={{ fontSize: 11, color: "var(--text-mute)" }}>·</span>
          <span style={{ fontSize: 12, color: "var(--text-dim)" }}>{selected.modified || timeAgo(selected.modified_ts)}</span>
        </div>

        {selected.desc && (
          <div style={{ marginTop: 12, padding: "10px 12px", background: "var(--panel-2)", borderRadius: 6, fontSize: 12, lineHeight: 1.5, color: "var(--text-dim)", border: "1px solid var(--border)" }}>
            {selected.desc}
          </div>
        )}

        <div style={{ marginTop: 18 }}>
          <SectionLabel>Details</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "6px 14px", padding: "4px 14px", fontSize: 12 }}>
            <span style={{ color: "var(--text-mute)" }}>Size</span>
            <span style={{ fontFamily: "var(--mono)", color: "var(--text-dim)" }}>{formatSize(selected.size || (selected.size_mb || 0) * 1024 * 1024)}</span>
            {selected.author && <><span style={{ color: "var(--text-mute)" }}>Author</span><span style={{ color: "var(--text-dim)" }}>{selected.author}</span></>}
            <span style={{ color: "var(--text-mute)" }}>Modified</span>
            <span style={{ color: "var(--text-dim)" }}>{selected.modified || timeAgo(selected.modified_ts)}</span>
            <span style={{ color: "var(--text-mute)" }}>Path</span>
            <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-dim)", wordBreak: "break-all", lineHeight: 1.5 }}>{fullPath}</span>
          </div>
        </div>

        {allVersions.length > 0 && (
          <div style={{ marginTop: 18 }}>
            <SectionLabel>Version history</SectionLabel>
            <div style={{ padding: "0 14px" }}>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 38, marginBottom: 10 }}>
                {allVersions.map(v => {
                  const isSel = v.version === selected.version;
                  const isLatest = v.version === Math.max(...allVersions.map(x => x.version));
                  const maxSz = Math.max(...allVersions.map(x => x.size || (x.size_mb || 0) * 1024 * 1024));
                  const sz = v.size || (v.size_mb || 0) * 1024 * 1024;
                  const ratio = maxSz > 0 ? sz / maxSz : 0.5;
                  return (
                    <div key={v.version} title={`v${String(v.version).padStart(3,"0")} · ${formatSize(sz)}`} style={{
                      flex: 1, height: `${Math.max(20, ratio * 100)}%`, borderRadius: 2,
                      background: isSel ? color : isLatest ? `${color}66` : "rgba(255,255,255,0.07)",
                      cursor: "pointer",
                    }} />
                  );
                })}
              </div>
              {allVersions.slice().reverse().map(v => {
                const isSel = v.version === selected.version;
                return (
                  <div key={v.version} style={{
                    display: "flex", alignItems: "center", gap: 10, padding: "6px 8px",
                    borderRadius: 5, background: isSel ? "rgba(255,255,255,0.04)" : "transparent",
                    marginBottom: 2,
                  }}>
                    <VersionPill version={v.version} latest={isSel} color={color} />
                    <span style={{ flex: 1, fontSize: 11.5, color: "var(--text-dim)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {v.desc || <span style={{ color: "var(--text-mute)", fontStyle: "italic" }}>No description</span>}
                    </span>
                    <span style={{ fontSize: 11, color: "var(--text-mute)" }}>{v.modified || timeAgo(v.modified_ts)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Footer actions */}
      <div style={{
        borderTop: "1px solid var(--border)", padding: "12px 14px",
        display: "flex", flexDirection: "column", gap: 8, background: "var(--panel-2)",
      }}>
        <button onClick={onOpen} style={{
          width: "100%", padding: "9px 12px", borderRadius: 6, border: "none",
          background: "var(--accent)", color: "#0F1012", fontWeight: 600, fontSize: 13,
          cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
        }}>
          <Icon name="open" size={13} /> Open in Houdini
        </button>
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={onCopyPath} style={ghostBtnStyle}>
            <Icon name="copy" size={12} /> Copy path
          </button>
          <button onClick={onReveal} style={ghostBtnStyle}>
            <Icon name="reveal" size={12} /> Reveal
          </button>
          <button onClick={onNewVersion} style={{...ghostBtnStyle, color: "var(--text)"}}>
            <Icon name="plus" size={12} /> Version
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── New Version modal ────────────────────────────────────────────────────────
const NewVersionModal = ({ entity, suggestedTask, onClose, onCreate }) => {
  const [task, setTask] = useState(suggestedTask || "");
  const STANDARD = ["dust-sim", "falling-ice", "smoke-trail", "fire-impact", "muzzle-flash", "lookdev", "rig-fx"];
  const filename = task ? hipFilename(entity, task, 1) : "—";
  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
      backdropFilter: "blur(2px)",
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: "var(--panel)", border: "1px solid var(--border)", borderRadius: 10,
        width: 460, padding: 0, boxShadow: "0 24px 60px rgba(0,0,0,0.6)", overflow: "hidden",
      }}>
        <div style={{ padding: "16px 18px 12px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text)" }}>New Houdini version</div>
            <div style={{ fontSize: 11.5, color: "var(--text-mute)", fontFamily: "var(--mono)", marginTop: 2 }}>{entity}</div>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text-mute)", cursor: "pointer", padding: 4 }}>
            <Icon name="close" size={14} />
          </button>
        </div>
        <div style={{ padding: "16px 18px" }}>
          <label style={{ fontSize: 11, color: "var(--text-mute)", letterSpacing: 0.6, textTransform: "uppercase", fontWeight: 600 }}>Task</label>
          <input value={task} onChange={e => setTask(e.target.value)} placeholder="e.g. dust-sim"
            style={{
              width: "100%", padding: "9px 11px", marginTop: 6, marginBottom: 10,
              background: "var(--panel-2)", border: "1px solid var(--border)", borderRadius: 6,
              color: "var(--text)", fontSize: 13, fontFamily: "var(--mono)", outline: "none",
            }} />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 14 }}>
            {STANDARD.map(t => (
              <button key={t} onClick={() => setTask(t)} style={{
                fontSize: 11, padding: "3px 8px", borderRadius: 4,
                background: t === task ? "rgba(255,122,53,0.16)" : "var(--panel-2)",
                color: t === task ? "var(--accent)" : "var(--text-dim)",
                border: t === task ? "1px solid rgba(255,122,53,0.4)" : "1px solid var(--border)",
                cursor: "pointer", fontFamily: "var(--mono)",
              }}>{t}</button>
            ))}
          </div>
          <label style={{ fontSize: 11, color: "var(--text-mute)", letterSpacing: 0.6, textTransform: "uppercase", fontWeight: 600 }}>Will create</label>
          <div style={{
            marginTop: 6, padding: "10px 12px", background: "var(--panel-2)", borderRadius: 6,
            fontFamily: "var(--mono)", fontSize: 12.5,
            color: task ? "var(--text)" : "var(--text-mute)",
            border: "1px solid var(--border)",
          }}>{filename}</div>
        </div>
        <div style={{ padding: "12px 18px", borderTop: "1px solid var(--border)", background: "var(--panel-2)", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button onClick={onClose} style={{ ...ghostBtnStyle, flex: "none", padding: "7px 14px" }}>Cancel</button>
          <button onClick={() => task && onCreate(task)} disabled={!task} style={{
            padding: "7px 16px", borderRadius: 5, border: "none",
            background: task ? "var(--accent)" : "var(--panel-3)",
            color: task ? "#0F1012" : "var(--text-mute)",
            fontWeight: 600, fontSize: 12.5, cursor: task ? "pointer" : "not-allowed",
          }}>Create v001</button>
        </div>
      </div>
    </div>
  );
};

Object.assign(window, {
  Icon, VersionPill, ProjectSwitcher, TreeRow, SectionLabel,
  Breadcrumbs, TabRow, HipRow, TaskGroup, DetailPane, NewVersionModal,
  ghostBtnStyle,
});
