// FX File Manager — main app.

const { useState, useEffect, useMemo, useCallback } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent":      "#FF7A35",
  "density":     "comfortable",
  "theme":       "dark",
  "showRail":    true,
  "showDetails": true,
  "showRecent":  true
}/*EDITMODE-END*/;

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  useEffect(() => {
    document.documentElement.style.setProperty("--accent", t.accent);
    document.documentElement.dataset.theme = t.theme;
  }, [t.accent, t.theme]);

  // ── Data state ──────────────────────────────────────────────────────────────
  const [projects,      setProjects]      = useState([]);
  const [project,       setProject]       = useState(null);
  const [seqMap,        setSeqMap]        = useState({});   // seq → [shots]
  const [assetMap,      setAssetMap]      = useState({});   // type → [names]
  const [hips,          setHips]          = useState([]);
  const [loadingHips,   setLoadingHips]   = useState(false);
  const [demoMode,      setDemoMode]      = useState(false);

  // ── Nav state ───────────────────────────────────────────────────────────────
  const [entity,          setEntity]          = useState(null);
  const [expanded,        setExpanded]        = useState({});
  const [search,          setSearch]          = useState("");
  const [view,            setView]            = useState("work");
  const [selectedKey,     setSelectedKey]     = useState(null);
  const [showVersionModal,setShowVersionModal]= useState(false);
  const [toast,           setToast]           = useState(null);
  const [recent,          setRecent]          = useState([]);

  // ── Bootstrap: load projects ─────────────────────────────────────────────
  useEffect(() => {
    loadProjects().then(ps => {
      setProjects(ps);
      setDemoMode(isDemoMode());
      if (ps.length > 0) {
        setProject(ps[0]);
      }
    });
    setRecent(loadRecent());
  }, []);

  // ── When project changes: load sequences + assets ─────────────────────────
  useEffect(() => {
    if (!project) return;
    setEntity(null);
    setHips([]);
    setSelectedKey(null);
    setSeqMap({});
    setAssetMap({});

    // If demo mode already populated sequences/assets in the project object, use them
    if (project.sequences && project.sequences.length) {
      const initialExpanded = {};
      project.sequences.forEach(s => { initialExpanded[s] = false; });
      setExpanded(initialExpanded);
      // Pre-populate seqMap from project.sequences (demo); shots loaded lazily
      const sm = {};
      project.sequences.forEach(s => { sm[s] = null; }); // null = not yet loaded
      setSeqMap(sm);
      // Default entity = first seq first shot (demo)
      if (isDemoMode() && project.sequences[0]) {
        const seq = project.sequences[0];
        const shots = SHOTS_BY_SEQ_MOCK[seq] || [];
        const sm2 = { ...sm, [seq]: shots };
        setSeqMap(sm2);
        setExpanded({ [seq]: true });
        if (shots[1]) setEntity(`${seq}/${shots[1]}`);
        else if (shots[0]) setEntity(`${seq}/${shots[0]}`);
      }
    } else {
      // Live mode: fetch sequences
      loadSequences(project.folder).then(seqs => {
        const sm = {};
        seqs.forEach(s => { sm[s] = null; });
        const initialExpanded = {};
        seqs.forEach(s => { initialExpanded[s] = false; });
        setSeqMap(sm);
        setExpanded(initialExpanded);
        if (seqs.length > 0) setExpanded(prev => ({ ...prev, [seqs[0]]: true }));
      });
    }

    if (project.assets && Object.keys(project.assets).length) {
      setAssetMap(project.assets);
    } else {
      loadAssets(project.folder).then(setAssetMap);
    }
  }, [project?.folder]);

  // ── When entity changes: load hips ─────────────────────────────────────────
  useEffect(() => {
    if (!project || !entity) { setHips([]); return; }
    setLoadingHips(true);
    setHips([]);
    setSelectedKey(null);
    loadHips(project.folder, entity).then(h => {
      setHips(h);
      setLoadingHips(false);
    });
  }, [project?.folder, entity]);

  // ── Toggle seq expansion + lazy-load shots ────────────────────────────────
  const toggleSeq = useCallback(async (seq) => {
    const nowOpen = !expanded[seq];
    setExpanded(prev => ({ ...prev, [seq]: nowOpen }));
    if (nowOpen && seqMap[seq] === null) {
      const shots = await loadShots(project.folder, seq);
      setSeqMap(prev => ({ ...prev, [seq]: shots }));
    }
  }, [expanded, seqMap, project?.folder]);

  // ── Derived ───────────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    if (!search) return hips;
    const s = search.toLowerCase();
    return hips.filter(h => h.task.toLowerCase().includes(s) || String(h.version).includes(s));
  }, [hips, search]);

  const groups = useMemo(() => {
    const g = {};
    filtered.forEach(h => { (g[h.task] = g[h.task] || []).push(h); });
    Object.values(g).forEach(arr => arr.sort((a, b) => a.version - b.version));
    return g;
  }, [filtered]);

  const selectedHip = useMemo(() => {
    if (!selectedKey) return null;
    return hips.find(h => `${h.task}_v${h.version}` === selectedKey);
  }, [selectedKey, hips]);

  const versionsOfSelected = useMemo(() => {
    if (!selectedHip) return [];
    return hips.filter(h => h.task === selectedHip.task).sort((a, b) => a.version - b.version);
  }, [selectedHip, hips]);

  const crumbParts = useMemo(() => {
    if (!project) return [];
    const parts = [{ label: project.name }];
    if (!entity) return parts;
    if (entity.startsWith("asset/")) {
      const [, type, name] = entity.split("/");
      parts.push({ label: "Assets" }, { label: type }, { label: name });
    } else {
      const [seq, shot] = entity.split("/");
      parts.push({ label: seq });
      if (shot) parts.push({ label: shot });
    }
    return parts;
  }, [project, entity]);

  const entityLabel = entity
    ? (entity.startsWith("asset/") ? entity.split("/").slice(1).join(" / ") : entity.replace("/", " · "))
    : "—";

  // ── Actions ───────────────────────────────────────────────────────────────
  const flash = msg => { setToast(msg); setTimeout(() => setToast(null), 2500); };

  const openHip = hip => {
    // In live mode, signal Houdini via the pipeline server
    const path = hip.path;
    if (path && !isDemoMode()) {
      fetch(`${API_BASE}/open-hip`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      }).catch(() => {});
    }
    if (entity) saveRecent({ project: project.folder, entity, task: hip.task, version: hip.version, modified_ts: hip.modified_ts || 0 });
    setRecent(loadRecent());
    flash(`Opening ${hipFilename(entity, hip.task, hip.version)}…`);
  };

  const copyPath = () => {
    if (selectedHip?.path) navigator.clipboard?.writeText(selectedHip.path).catch(() => {});
    flash("Path copied to clipboard");
  };

  const reveal = () => flash("Revealed in file manager");

  const newVersion = () => setShowVersionModal(true);

  const createVersion = task => {
    flash(`Created ${hipFilename(entity, task, 1)}`);
    setShowVersionModal(false);
  };

  const navTo = newEntity => { setEntity(newEntity); setSelectedKey(null); setSearch(""); };

  const switchProject = p => {
    setProject(p);
    setEntity(null);
    setSelectedKey(null);
    setSearch("");
  };

  const handleRefresh = () => {
    if (!project || !entity) return;
    setLoadingHips(true);
    loadHips(project.folder, entity).then(h => { setHips(h); setLoadingHips(false); });
    flash("Refreshed");
  };

  if (!project) {
    return (
      <div className="root" style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ color: "var(--text-mute)", fontFamily: "var(--mono)", fontSize: 12 }}>Loading…</div>
      </div>
    );
  }

  return (
    <div className="root" data-screen-label="FX File Manager">
      {/* Chrome */}
      <header className="chrome">
        <div className="chrome-lights">
          <span style={{ background: "#FF5F57" }} />
          <span style={{ background: "#FEBC2E" }} />
          <span style={{ background: "#28C840" }} />
        </div>
        <div className="chrome-title">
          <Icon name="hip" size={13} />
          <span>FX File Manager</span>
          <span className="chrome-sep">/</span>
          <span className="chrome-project">{project.name}</span>
          {demoMode && (
            <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 3, background: "rgba(255,122,53,0.15)", color: "var(--accent)", fontWeight: 600, letterSpacing: 0.5 }}>
              DEMO
            </span>
          )}
        </div>
        <div className="chrome-actions">
          <button className="icon-btn" title="Refresh" onClick={handleRefresh}><Icon name="sync" size={13} /></button>
          <button className="icon-btn" title="Settings"><Icon name="cog" size={13} /></button>
        </div>
      </header>

      <div className="layout">
        {/* Left rail */}
        {t.showRail && (
          <aside className="rail">
            <ProjectSwitcher projects={projects} active={project} onChange={switchProject} />
            <div className="rail-scroll">
              {t.showRecent && recent.filter(r => r.project === project.folder).length > 0 && (
                <>
                  <SectionLabel>Recent</SectionLabel>
                  {recent.filter(r => r.project === project.folder).slice(0, 5).map((r, i) => {
                    const isSel = r.entity === entity;
                    return (
                      <div key={i} onClick={() => navTo(r.entity)} style={{
                        display: "flex", alignItems: "center", gap: 8,
                        padding: "5px 14px", cursor: "pointer",
                        background: isSel ? "var(--row-sel)" : "transparent",
                        borderLeft: isSel ? "2px solid var(--accent)" : "2px solid transparent",
                      }}
                      onMouseEnter={e => { if (!isSel) e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
                      onMouseLeave={e => { if (!isSel) e.currentTarget.style.background = "transparent"; }}>
                        <div style={{ width: 4, height: 4, borderRadius: 2, background: taskColor(r.task) }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 12, color: "var(--text)", fontFamily: "var(--mono)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {r.entity.replace("asset/", "")}
                          </div>
                          <div style={{ fontSize: 10.5, color: "var(--text-mute)", fontFamily: "var(--mono)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {r.task} · v{String(r.version).padStart(3, "0")} · {timeAgo(r.modified_ts)}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </>
              )}

              <SectionLabel right={<button className="rail-add" title="New sequence"><Icon name="plus" size={11} /></button>}>
                Shots
              </SectionLabel>
              {Object.keys(seqMap).map(seq => {
                const isExp = !!expanded[seq];
                const shots = seqMap[seq] || [];
                return (
                  <React.Fragment key={seq}>
                    <TreeRow
                      icon="folder" label={seq} level={0}
                      expanded={isExp} hasChildren
                      badge={shots.length || "…"}
                      onClick={() => toggleSeq(seq)}
                    />
                    {isExp && shots.map(shot => {
                      const path = `${seq}/${shot}`;
                      return (
                        <TreeRow key={shot} icon="shot" label={shot} level={1}
                          selected={entity === path} color="var(--text-mute)"
                          onClick={() => navTo(path)} />
                      );
                    })}
                  </React.Fragment>
                );
              })}

              <SectionLabel right={<button className="rail-add" title="New asset"><Icon name="plus" size={11} /></button>}>
                Assets
              </SectionLabel>
              {Object.entries(assetMap).map(([type, names]) => {
                const isExp = !!expanded[type];
                return (
                  <React.Fragment key={type}>
                    <TreeRow
                      icon="folder" label={type} level={0}
                      expanded={isExp} hasChildren={names.length > 0}
                      badge={names.length}
                      onClick={() => setExpanded(prev => ({ ...prev, [type]: !isExp }))}
                    />
                    {isExp && names.map(name => {
                      const path = `asset/${type}/${name}`;
                      return (
                        <TreeRow key={name} icon="asset" label={name} level={1}
                          selected={entity === path}
                          onClick={() => navTo(path)} />
                      );
                    })}
                  </React.Fragment>
                );
              })}
              <div style={{ height: 12 }} />
            </div>
          </aside>
        )}

        {/* Center */}
        <main className="main">
          <div className="main-header">
            <Breadcrumbs parts={crumbParts} />
            <div className="main-header-meta">
              <span>{hips.length} hip files</span>
              <span>·</span>
              <span>{Object.keys(groups).length} tasks</span>
            </div>
          </div>

          <div className="main-toolbar">
            <TabRow
              tabs={[
                { key: "work",      label: "Work files",  count: hips.length },
                { key: "publishes", label: "Publishes",   count: null },
                { key: "previews",  label: "Previews",    count: null },
              ]}
              active={view}
              onChange={setView}
            />
            <div className="search">
              <Icon name="search" size={13} />
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Filter by task or version…" />
              {search && <button onClick={() => setSearch("")} className="search-clear"><Icon name="close" size={11} /></button>}
            </div>
            <button className="primary-btn" onClick={newVersion}>
              <Icon name="plus" size={13} /> New version
            </button>
          </div>

          {view === "work" && (
            <div className="list-header">
              <span>Filename</span>
              <span>Version</span>
              <span>Size</span>
              <span>Modified</span>
              <span>Author</span>
            </div>
          )}

          <div className="main-body">
            {view !== "work" && <EmptyState view={view} />}
            {view === "work" && !entity && (
              <div className="empty">
                <div className="empty-icon"><Icon name="folder" size={26} /></div>
                <div className="empty-title">Select a shot or asset</div>
                <div className="empty-sub">Choose a shot or asset from the navigation rail to browse its hip files.</div>
              </div>
            )}
            {view === "work" && entity && loadingHips && (
              <div className="empty">
                <div style={{ color: "var(--text-mute)", fontFamily: "var(--mono)", fontSize: 12 }}>Loading…</div>
              </div>
            )}
            {view === "work" && entity && !loadingHips && Object.keys(groups).length === 0 && (
              <NoFiles search={search} entity={entityLabel} onNew={newVersion} />
            )}
            {view === "work" && entity && !loadingHips && Object.entries(groups).map(([task, taskHips]) => (
              <TaskGroup
                key={task} task={task} hips={taskHips} entity={entity}
                selectedKey={selectedKey}
                density={t.density}
                onSelect={setSelectedKey}
                onOpen={openHip}
              />
            ))}
          </div>

          <footer className="status">
            <span><span className="status-dot" style={{ background: demoMode ? "#FEBC2E" : "#4ADE80", boxShadow: demoMode ? "0 0 6px #FEBC2EAA" : "0 0 6px #4ADE80AA" }} /> {demoMode ? "demo mode" : "connected"}</span>
            <span style={{ fontFamily: "var(--mono)" }}>…/{project.folder}</span>
            <span style={{ flex: 1 }} />
            <span>{project.fps} fps · {project.resolution}</span>
            <span>·</span>
            <span>{projects.length} projects</span>
          </footer>
        </main>

        {/* Right details pane */}
        {t.showDetails && (
          <aside className="details">
            <DetailPane
              selected={selectedHip}
              allVersions={selectedHip ? versionsOfSelected : []}
              entity={entity || ""}
              onOpen={() => selectedHip && openHip(selectedHip)}
              onCopyPath={copyPath}
              onReveal={reveal}
              onNewVersion={newVersion}
            />
          </aside>
        )}
      </div>

      {showVersionModal && (
        <NewVersionModal
          entity={entity || ""}
          suggestedTask={selectedHip?.task}
          onClose={() => setShowVersionModal(false)}
          onCreate={createVersion}
        />
      )}

      {toast && (
        <div className="toast">
          <span className="status-dot" /> {toast}
        </div>
      )}

      <TweaksPanel title="Tweaks">
        <TweakSection label="Appearance">
          <TweakColor label="Accent" value={t.accent}
            options={["#FF7A35", "#7DD3FC", "#B5E36A", "#E0A6FF", "#F472B6"]}
            onChange={v => setTweak("accent", v)} />
          <TweakRadio label="Theme" value={t.theme}
            options={["dark", "darker"]}
            onChange={v => setTweak("theme", v)} />
          <TweakRadio label="Density" value={t.density}
            options={["comfortable", "compact"]}
            onChange={v => setTweak("density", v)} />
        </TweakSection>
        <TweakSection label="Layout">
          <TweakToggle label="Navigation rail"  value={t.showRail}    onChange={v => setTweak("showRail", v)} />
          <TweakToggle label="Recent section"   value={t.showRecent}  onChange={v => setTweak("showRecent", v)} />
          <TweakToggle label="Details pane"     value={t.showDetails} onChange={v => setTweak("showDetails", v)} />
        </TweakSection>
      </TweaksPanel>
    </div>
  );
}

// ── Empty states ──────────────────────────────────────────────────────────────
const EmptyState = ({ view }) => (
  <div className="empty">
    <div className="empty-icon"><Icon name={view === "publishes" ? "box" : "clock"} size={26} /></div>
    <div className="empty-title">{view === "publishes" ? "Publishes browser" : "Preview gallery"}</div>
    <div className="empty-sub">
      {view === "publishes"
        ? "Browse published USD, ABC, BGEO and VDB for this entity, with version metadata and source hip links."
        : "Flipbooks and rendered MP4 previews show up here once you've published them."}
    </div>
    <div className="empty-tag">Coming soon</div>
  </div>
);

const NoFiles = ({ search, entity, onNew }) => (
  <div className="empty">
    <div className="empty-icon"><Icon name="hip" size={26} /></div>
    <div className="empty-title">{search ? "No matches" : `No hip files in ${entity} yet`}</div>
    <div className="empty-sub">
      {search
        ? `Nothing matches "${search}". Clear the filter to see all versions.`
        : "Create the first versioned scene to start working on this shot."}
    </div>
    {!search && (
      <button className="primary-btn" style={{ marginTop: 14 }} onClick={onNew}>
        <Icon name="plus" size={13} /> Create first version
      </button>
    )}
  </div>
);

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
