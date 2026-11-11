import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, BarChart3, CheckCircle2, ChevronRight, Crosshair, Database, Download, FileDown, FileUp, Globe2, History, LoaderCircle, MapPin, Route as RouteIcon } from "lucide-react";
import { analyzeLocationSeaStates, analyzeRouteSeaStates, analyzeSeaStates, fetchDemoSeaStates, fetchSeaStateResult, generateSeaRoute, inspectSeaStateFiles, listSeaStateResults, previewSpectrum } from "../api";
import RouteMap from "./RouteMap";
import ScatterHeatmap from "./ScatterHeatmap";
import ScientificLineChart from "./ScientificLineChart";
import { downloadRouteCellsCsv, downloadRouteMapPng, downloadScatterPng } from "../seaStateDownloads";

const METHODS = {
  zone: { title: "Zone scatter", icon: Globe2, kicker: "Regional wave climate", description: "Combine every grid cell inside a defined zone to produce one regional Hs–Tp probability matrix." },
  location: { title: "Location scatter", icon: Crosshair, kicker: "Nearest ERA5 cell", description: "Request any coordinate and use the complete time history from the nearest available ERA5 grid cell, with the offset reported." },
  route: { title: "Route scatter", icon: RouteIcon, kicker: "Along-route exposure", description: "Build a maritime route, snap its sampled path to ERA5 cells, and combine the encountered wave climates." },
};

const rangeLabel = (low, high, digits = 1) => `${Number(low).toFixed(digits)}–${Number(high).toFixed(digits)}`;

export default function SeaStateWorkspace({ selectedSeaState, onSelectSeaState, onOpenResponse }) {
  const [page, setPage] = useState("home");
  const [method, setMethod] = useState(null);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [files, setFiles] = useState([]);
  const [hsBin, setHsBin] = useState(0.5);
  const [tpBin, setTpBin] = useState(1.0);
  const [bounds, setBounds] = useState({ latitude_min: 48, latitude_max: 58, longitude_min: -8, longitude_max: 8 });
  const [location, setLocation] = useState({ latitude: 50, longitude: 1 });
  const [routeForm, setRouteForm] = useState({ origin_latitude: 51.92, origin_longitude: 4.48, destination_latitude: 40.68, destination_longitude: -74.04, stopover: false, stopover_latitude: 50.11, stopover_longitude: -5.53, sample_spacing_nm: 60, max_grid_distance_km: 100 });
  const [advanced, setAdvanced] = useState(false);
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [routeLoading, setRouteLoading] = useState(false);
  const [inspectionLoading, setInspectionLoading] = useState(false);
  const [sourceManifest, setSourceManifest] = useState(null);
  const [error, setError] = useState("");
  const [spectrum, setSpectrum] = useState(null);
  const inputRef = useRef(null);

  const selected = selectedSeaState || result?.selected_state;
  useEffect(() => {
    if (!selected) return undefined;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try { const data = await previewSpectrum({ hs: selected.hs, tp: selected.tp, gamma: 3.3, points: 350 }); if (!cancelled) setSpectrum(data); }
      catch { if (!cancelled) setSpectrum(null); }
    }, 120);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [selected]);

  const openMethod = (key) => { setMethod(key); setPage("setup"); setError(""); };
  const commitResult = (data, key = method) => { setMethod(key); setResult(data); onSelectSeaState(data.selected_state); setPage("results"); };
  const openHistory = async () => { setHistoryLoading(true); setError(""); try { setHistory(await listSeaStateResults()); setPage("history"); } catch (requestError) { setError(requestError.message); } finally { setHistoryLoading(false); } };
  const reopenResult = async (item) => { setHistoryLoading(true); setError(""); try { commitResult(await fetchSeaStateResult(item.job_id), item.method); } catch (requestError) { setError(requestError.message); } finally { setHistoryLoading(false); } };
  const loadDemo = async (key) => {
    setLoading(true); setError("");
    try { const data = await fetchDemoSeaStates(hsBin, tpBin); data.analysis_method = key; data.source_name = `${METHODS[key].title} · demonstration`; commitResult(data, key); }
    catch (requestError) { setError(requestError.message); }
    finally { setLoading(false); }
  };

  const requestRoute = async () => {
    setRouteLoading(true); setError("");
    try {
      const waypoints = routeForm.stopover ? [[Number(routeForm.stopover_longitude), Number(routeForm.stopover_latitude)]] : [];
      const generated = await generateSeaRoute({ origin: [Number(routeForm.origin_longitude), Number(routeForm.origin_latitude)], destination: [Number(routeForm.destination_longitude), Number(routeForm.destination_latitude)], waypoints });
      setRoute(generated); return generated;
    } catch (requestError) { setError(requestError.message); return null; }
    finally { setRouteLoading(false); }
  };

  const selectFiles = async (selectedFiles) => {
    const selected = Array.from(selectedFiles || []);
    if (selected.length > 100) {
      setFiles([]); setSourceManifest(null); setError(`You selected ${selected.length} files. The limit is 100 files per analysis.`); return;
    }
    const nextFiles = selected;
    setFiles(nextFiles); setSourceManifest(null); setError("");
    if (!nextFiles.length) return;
    setInspectionLoading(true);
    try { setSourceManifest(await inspectSeaStateFiles(nextFiles)); }
    catch (requestError) { setError(requestError.message); }
    finally { setInspectionLoading(false); }
  };

  const buildScatter = async () => {
    if (!files.length) { setError("Attach the Hs/Tp CSV or ERA5 NetCDF source for this analysis."); return; }
    setLoading(true); setError("");
    const common = { hs_bin_width: Number(hsBin), tp_bin_width: Number(tpBin) };
    try {
      let data;
      if (method === "zone") data = await analyzeSeaStates(files, { ...common, ...Object.fromEntries(Object.entries(bounds).map(([key, value]) => [key, Number(value)])) });
      if (method === "location") data = await analyzeLocationSeaStates(files, { ...common, latitude: Number(location.latitude), longitude: Number(location.longitude) });
      if (method === "route") {
        const activeRoute = route || await requestRoute();
        if (!activeRoute) return;
        data = await analyzeRouteSeaStates(files, { ...common, route_coordinates: activeRoute.geometry.coordinates, sample_spacing_nm: Number(routeForm.sample_spacing_nm), weighting: "route_distance", max_grid_distance_km: Number(routeForm.max_grid_distance_km) });
      }
      data.analysis_method = method;
      commitResult(data);
    } catch (requestError) { setError(requestError.message); }
    finally { setLoading(false); }
  };

  if (page === "home") return <SeaStateHome onOpen={openMethod} onDemo={loadDemo} onHistory={openHistory} loading={loading || historyLoading} error={error} />;
  if (page === "history") return <SeaStateHistory items={history} loading={historyLoading} error={error} onBack={() => setPage("home")} onOpen={reopenResult} />;
  if (page === "results" && result) return <SeaStateResults method={method} result={result} selected={selected} onSelect={onSelectSeaState} spectrum={spectrum} onEdit={() => setPage("setup")} onHome={() => setPage("home")} onOpenResponse={onOpenResponse} />;

  const sourceLabel = files.length ? (files.length === 1 ? files[0].name : `${files.length} files selected`) : "Attach wave-history files";
  const MethodIcon = METHODS[method].icon;
  return (
    <main className="module-page sea-state-page sea-dark">
      <button className="sea-back" type="button" onClick={() => setPage("home")}><ArrowLeft size={16} /> All sea-state methods</button>
      <div className="module-heading sea-page-heading"><div><span className="panel-kicker">{METHODS[method].kicker}</span><h1>{METHODS[method].title}</h1><p>{METHODS[method].description}</p></div><MethodIcon size={34} /></div>
      <section className="sea-setup-card">
        <div className="sea-setup-top"><div><span className="step-index">01</span><h2>Define analysis</h2></div><button type="button" className="advanced-toggle" onClick={() => setAdvanced(!advanced)}>Advanced settings <ChevronRight className={advanced ? "rotated" : ""} size={16} /></button></div>
        {method === "zone" ? <ZoneFields bounds={bounds} setBounds={setBounds} /> : null}
        {method === "location" ? <LocationFields location={location} setLocation={setLocation} /> : null}
        {method === "route" ? <RouteFields routeForm={routeForm} setRouteForm={setRouteForm} clearRoute={() => setRoute(null)} /> : null}
        {advanced ? <div className="sea-advanced"><label><span>Hs bin width</span><input type="number" min="0.1" step="0.1" value={hsBin} onChange={(event) => setHsBin(event.target.value)} /></label><label><span>Tp bin width</span><input type="number" min="0.1" step="0.1" value={tpBin} onChange={(event) => setTpBin(event.target.value)} /></label>{method === "route" ? <><label><span>Route sampling [nm]</span><input type="number" min="5" max="500" value={routeForm.sample_spacing_nm} onChange={(event) => setRouteForm({ ...routeForm, sample_spacing_nm: event.target.value })} /></label><label><span>Maximum ERA5 offset [km]</span><input type="number" min="1" max="1000" value={routeForm.max_grid_distance_km} onChange={(event) => setRouteForm({ ...routeForm, max_grid_distance_km: event.target.value })} /></label></> : null}</div> : null}
        <div className="sea-source-row"><div><span className="step-index">02</span><div><strong>Wave-history source</strong><small>Select up to 100 files: as many as 50 yearly Hs/Tp pairs, or 100 combined files. Every period is checked before analysis.</small></div></div><button type="button" className="dark-upload" onClick={() => inputRef.current?.click()}>{inspectionLoading ? <LoaderCircle className="spin" size={17} /> : <FileUp size={17} />} {sourceLabel}{sourceManifest ? <CheckCircle2 size={16} /> : null}</button><input ref={inputRef} className="visually-hidden" type="file" accept=".csv,.nc,.netcdf" multiple onChange={(event) => selectFiles(event.target.files)} /></div>
        {sourceManifest ? <SourceManifest manifest={sourceManifest} /> : null}
      </section>
      {method === "route" ? <section className="route-map-card"><div className="route-map-toolbar"><div><span className="step-index">03</span><div><strong>Global route preview</strong><small>Generate the route before mapping it to ERA5 cells.</small></div></div><button className="button secondary" type="button" onClick={requestRoute} disabled={routeLoading}>{routeLoading ? <LoaderCircle className="spin" size={17} /> : <RouteIcon size={17} />} Generate route</button></div><RouteMap coordinates={route?.geometry?.coordinates || []} stopover={routeForm.stopover ? { latitude: routeForm.stopover_latitude, longitude: routeForm.stopover_longitude } : null} /></section> : null}
      {error ? <div className="inline-error">{error}</div> : null}
      <div className="sea-run-bar"><p><strong>{method === "zone" ? "Selected-zone analysis" : method === "location" ? "One nearest grid cell" : "Along-route analysis"}</strong><span>{method === "zone" ? "Analysis stops if the upload does not cover the complete selected zone." : method === "location" ? "The matched cell and its distance from the requested position are written to results." : "Analysis stops if any sampled route position is farther than the allowed ERA5 offset."}</span></p><button className="button primary" type="button" onClick={buildScatter} disabled={loading || routeLoading || inspectionLoading || !sourceManifest}>{loading ? <LoaderCircle className="spin" size={17} /> : <BarChart3 size={17} />} Generate scatter</button></div>
    </main>
  );
}

function SeaStateHome({ onOpen, onDemo, onHistory, loading, error }) {
  return <main className="module-page sea-state-page sea-dark"><div className="module-heading sea-home-heading"><div><span className="panel-kicker">Environmental analysis</span><h1>Sea-state modelling</h1><p>Choose the spatial question first. Each method has its own inputs and auditable result page.</p></div><button className="button secondary history-button" type="button" onClick={onHistory} disabled={loading}><History size={17} /> Saved analyses</button></div><section className="sea-method-list">{Object.entries(METHODS).map(([key, item], index) => { const Icon = item.icon; return <article key={key} className="sea-method-card"><span className="method-number">0{index + 1}</span><div className="method-icon"><Icon size={28} /></div><div><span className="panel-kicker">{item.kicker}</span><h2>{item.title}</h2><p>{item.description}</p><button type="button" className="demo-link" disabled={loading} onClick={() => onDemo(key)}>Open demonstration results</button></div><button type="button" className="method-open" onClick={() => onOpen(key)} aria-label={`Configure ${item.title}`}>Configure <ChevronRight size={18} /></button></article>; })}</section>{error ? <div className="inline-error">{error}</div> : null}</main>;
}

function SeaStateHistory({ items, loading, error, onBack, onOpen }) {
  return <main className="module-page sea-state-page sea-dark"><button className="sea-back" type="button" onClick={onBack}><ArrowLeft size={16} /> Sea-state methods</button><div className="module-heading sea-page-heading"><div><span className="panel-kicker">Saved work</span><h1>Sea-state analysis history</h1><p>Reopen a completed matrix or download its complete stored data.</p></div><History size={34} /></div>{error ? <div className="inline-error">{error}</div> : null}{loading ? <div className="panel-loading"><LoaderCircle className="spin" /> Loading saved analyses…</div> : <section className="sea-history-list">{items.length ? items.map((item) => <article key={item.job_id}><div><span className="history-method">{item.method}</span><strong>{item.title}</strong><small>{item.time_start?.slice(0, 10) || "Unknown date"} to {item.time_end?.slice(0, 10) || "unknown"} · {Number(item.valid_observations || 0).toLocaleString()} paired records</small></div><div className="history-actions"><a className="button secondary" href={`/api/sea-states/${item.job_id}/files/scatter.csv`} download><FileDown size={15} /> CSV</a><a className="button secondary" href={`/api/sea-states/${item.job_id}/files/scatter.json`} download><FileDown size={15} /> JSON</a><button className="button primary" type="button" onClick={() => onOpen(item)}>Open result <ArrowRight size={15} /></button></div></article>) : <div className="history-empty">No saved sea-state analyses are available yet.</div>}</section>}</main>;
}

function ZoneFields({ bounds, setBounds }) {
  const field = (key, label, min, max) => <label><span>{label}</span><input type="number" min={min} max={max} value={bounds[key]} onChange={(event) => setBounds({ ...bounds, [key]: event.target.value })} /></label>;
  return <div className="sea-coordinate-grid zone-coordinate-grid"><div className="field-intro"><strong>Zone boundary</strong><span>All grid-cell centres inside these bounds are aggregated.</span></div>{field("latitude_min", "South latitude", -90, 90)}{field("latitude_max", "North latitude", -90, 90)}{field("longitude_min", "West longitude", -180, 180)}{field("longitude_max", "East longitude", -180, 180)}</div>;
}

function LocationFields({ location, setLocation }) {
  return <div className="sea-coordinate-grid location-coordinate-grid"><div className="field-intro"><strong>Requested position</strong><span>The nearest source-grid coordinate and great-circle offset are reported.</span></div><label><span>Latitude</span><input type="number" min="-90" max="90" step="0.01" value={location.latitude} onChange={(event) => setLocation({ ...location, latitude: event.target.value })} /></label><label><span>Longitude</span><input type="number" min="-180" max="180" step="0.01" value={location.longitude} onChange={(event) => setLocation({ ...location, longitude: event.target.value })} /></label></div>;
}

function RouteFields({ routeForm, setRouteForm, clearRoute }) {
  const update = (key, value) => { clearRoute(); setRouteForm({ ...routeForm, [key]: value }); };
  return <><div className="sea-coordinate-grid route-coordinate-grid"><div className="field-intro"><strong>Route endpoints</strong><span>Coordinates use decimal degrees.</span></div><label><span>Origin latitude</span><input type="number" min="-90" max="90" step="0.01" value={routeForm.origin_latitude} onChange={(event) => update("origin_latitude", event.target.value)} /></label><label><span>Origin longitude</span><input type="number" min="-180" max="180" step="0.01" value={routeForm.origin_longitude} onChange={(event) => update("origin_longitude", event.target.value)} /></label><label><span>Destination latitude</span><input type="number" min="-90" max="90" step="0.01" value={routeForm.destination_latitude} onChange={(event) => update("destination_latitude", event.target.value)} /></label><label><span>Destination longitude</span><input type="number" min="-180" max="180" step="0.01" value={routeForm.destination_longitude} onChange={(event) => update("destination_longitude", event.target.value)} /></label></div><label className="stopover-check"><input type="checkbox" checked={routeForm.stopover} onChange={(event) => update("stopover", event.target.checked)} /><span><strong>Add stopover</strong><small>Reveal one optional intermediate coordinate.</small></span></label>{routeForm.stopover ? <div className="sea-coordinate-grid stopover-grid"><div className="field-intro"><strong>Stopover</strong><span>The route is generated as two connected sea legs.</span></div><label><span>Stopover latitude</span><input type="number" min="-90" max="90" step="0.01" value={routeForm.stopover_latitude} onChange={(event) => update("stopover_latitude", event.target.value)} /></label><label><span>Stopover longitude</span><input type="number" min="-180" max="180" step="0.01" value={routeForm.stopover_longitude} onChange={(event) => update("stopover_longitude", event.target.value)} /></label></div> : null}</>;
}

function SeaStateResults({ method, result, selected, onSelect, spectrum, onEdit, onHome, onOpenResponse }) {
  const routeMapRef = useRef(null);
  return <main className="module-page sea-state-page sea-dark sea-results-page">
    <div className="results-nav"><button className="sea-back" type="button" onClick={onHome}><ArrowLeft size={16} /> Sea-state methods</button><button className="button secondary" type="button" onClick={onEdit}>Back to setup</button></div>
    <div className="module-heading sea-page-heading"><div><span className="panel-kicker">{METHODS[method].kicker}</span><h1>{METHODS[method].title} results</h1><p>{result.source_name}</p></div><CheckCircle2 size={34} /></div>
    {result.source_manifest ? <SourceManifest manifest={result.source_manifest} result /> : null}
    {method === "location" && result.spatial_selection ? <LocationResult selection={result.spatial_selection} /> : null}
    {method === "route" && result.route ? <section className="route-result-map" ref={routeMapRef}><RouteMap coordinates={result.route.coordinates} gridPoints={result.route.grid_points} /><div className="route-download-row"><p>{result.route.unique_grid_cells} unique cells · {result.route.length_nm.toFixed(0)} nm · maximum source offset {result.route.maximum_match_distance_km.toFixed(1)} km</p><button className="button secondary" type="button" onClick={() => downloadRouteMapPng(routeMapRef.current, result)}><Download size={16} /> Download map PNG</button><button className="button secondary" type="button" onClick={() => downloadRouteCellsCsv(result)}><FileDown size={16} /> Download route CSV</button></div></section> : null}
    {result.job_id ? <div className="matrix-downloads"><span>Complete matrix data</span><a className="button secondary" href={`/api/sea-states/${result.job_id}/files/scatter.csv`} download><FileDown size={15} /> CSV</a><a className="button secondary" href={`/api/sea-states/${result.job_id}/files/scatter.json`} download><FileDown size={15} /> JSON</a></div> : null}
    <div className="sea-state-layout"><section className="scatter-panel"><div className="scatter-panel-heading"><div><span className="panel-kicker">Analysis output</span><h2>Hs–Tp probability matrix</h2></div><div className="scatter-heading-actions"><span className="probability-badge">Probability [%]</span><button className="button primary" type="button" onClick={() => downloadScatterPng(method, result)}><Download size={16} /> Download scatter PNG</button></div></div><ScatterHeatmap result={result} mode="probability" selected={selected} onSelect={onSelect} /><TopStates result={result} /></section><SelectedState selected={selected} spectrum={spectrum} onOpenResponse={onOpenResponse} /></div>
  </main>;
}

function SourceManifest({ manifest, result = false }) {
  const coverage = manifest.coverage || {};
  const years = manifest.years?.length ? (manifest.years.length === 1 ? String(manifest.years[0]) : `${manifest.years[0]}–${manifest.years.at(-1)}`) : "Dates unavailable";
  const coordinates = coverage.latitude_min == null ? "No coordinates" : `${coverage.latitude_min.toFixed(2)}°…${coverage.latitude_max.toFixed(2)}° lat · ${coverage.longitude_min.toFixed(2)}°…${coverage.longitude_max.toFixed(2)}° lon`;
  const pairing = manifest.pairing === "separate_hs_tp" ? "Hs/Tp pairs identified by variables" : manifest.pairing === "mixed_collection" ? "Combined files and Hs/Tp pairs" : "Combined Hs/Tp files";
  const shownFiles = manifest.files.slice(0, 6);
  return <section className={`source-manifest ${result ? "result-manifest" : ""}`}><div className="manifest-status"><CheckCircle2 size={19} /><div><strong>{result ? "Calculation provenance" : "Source collection validated"}</strong><span>{manifest.file_count || manifest.files.length} files · {manifest.period_count || 1} periods · {pairing}</span></div></div><div><span>Period</span><strong>{years}</strong><small>{manifest.time_start?.slice(0, 10) || "Unknown"} to {manifest.time_end?.slice(0, 10) || "unknown"}</small>{manifest.missing_years?.length ? <small className="manifest-gap">Missing years: {manifest.missing_years.join(", ")}</small> : <small>Continuous uploaded year sequence</small>}</div><div><span>Geographic coverage</span><strong>{coordinates}</strong><small>{manifest.grid_points ? `${manifest.grid_points.toLocaleString()} grid cells per period` : "Grid size unavailable"}</small></div><div className="manifest-files"><span>Detected files</span>{shownFiles.map((file) => <small key={`${file.input_index}-${file.file_name}`}><b>{file.role === "hs" ? "Hs" : file.role === "tp" ? "Tp" : "Hs + Tp"}</b> {file.file_name} · {file.hs_variable || file.tp_variable}</small>)}{manifest.files.length > shownFiles.length ? <small className="manifest-more">+ {manifest.files.length - shownFiles.length} more validated files</small> : null}</div></section>;
}

function LocationResult({ selection }) { return <section className="spatial-result-strip"><MapPin size={20} /><div><span>Requested</span><strong>{selection.requested.latitude.toFixed(3)}°, {selection.requested.longitude.toFixed(3)}°</strong></div><div><span>Nearest ERA5 grid</span><strong>{selection.matched.latitude.toFixed(3)}°, {selection.matched.longitude.toFixed(3)}°</strong></div><div><span>Offset</span><strong>{selection.distance_km.toFixed(2)} km</strong></div></section>; }
function TopStates({ result }) { return <div className="top-state-table-wrap"><h3>Top sea states by probability</h3><table className="analysis-table"><thead><tr><th>Rank</th><th>Hs range [m]</th><th>Tp range [s]</th><th>Probability [%]</th></tr></thead><tbody>{result.top_states.slice(0, 5).map((state, index) => <tr key={`${state.hs_index}-${state.tp_index}`}><td>{index + 1}</td><td>{rangeLabel(state.hs_low, state.hs_high)}</td><td>{rangeLabel(state.tp_low, state.tp_high)}</td><td>{state.probability.toFixed(3)}</td></tr>)}</tbody></table></div>; }
function SelectedState({ selected, spectrum, onOpenResponse }) { return <aside className="selected-state-rail"><h2>Selected sea state</h2>{selected ? <><dl><div><dt>Hs</dt><dd>{selected.hs.toFixed(2)} <small>m</small></dd></div><div><dt>Tp</dt><dd>{selected.tp.toFixed(1)} <small>s</small></dd></div><div className="accent"><dt>Probability</dt><dd>{selected.probability.toFixed(3)} <small>%</small></dd></div><div><dt>JONSWAP gamma</dt><dd>3.3</dd></div></dl><button className="button primary wide" type="button" onClick={onOpenResponse}>Use in response analysis <ArrowRight size={17} /></button>{spectrum ? <ScientificLineChart compact title="JONSWAP preview" x={spectrum.omega} xLabel="ω [rad/s]" yLabel="Sη" series={[{ key: "jonswap", label: "JONSWAP", values: spectrum.jonswap, color: "#20d9e5" }]} /> : null}</> : <p>Select a populated scatter cell.</p>}</aside>; }
