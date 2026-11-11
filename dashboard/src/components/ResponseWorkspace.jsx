import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, CheckCircle2, Download, LoaderCircle, MapPin, Play, Waves } from "lucide-react";
import { calculateResponse, listAnalyses, previewSpectrum } from "../api";
import ScientificLineChart from "./ScientificLineChart";

const DOF_COLORS = {
  Surge: "#057a8a",
  Sway: "#d17d11",
  Heave: "#3169b0",
  Roll: "#9a4d9f",
  Pitch: "#d34f62",
  Yaw: "#5f7f3d",
};
const AXIS_COLORS = { Ax: "#057a8a", Ay: "#d17d11", Az: "#3169b0" };

function displayNumber(value, digits = 3) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  if (number !== 0 && (Math.abs(number) >= 1000 || Math.abs(number) < 0.001)) return number.toExponential(2);
  return number.toFixed(digits);
}

function completedAnalyses(data) {
  return (data?.jobs || []).filter((job) => job.status === "completed" && job.rao_available);
}

export default function ResponseWorkspace({ selectedSeaState, hydrodynamicJob, onOpenHydrodynamics }) {
  const [inputs, setInputs] = useState({
    hs: selectedSeaState?.hs ?? 2.75,
    tp: selectedSeaState?.tp ?? 10.5,
    gamma: 3.3,
    heading_deg: 90,
    speed_knots: 0,
    duration_days: 42,
    exceedance_percent: 1,
    x: 120,
    y: 0,
    z: 0,
  });
  const [analyses, setAnalyses] = useState([]);
  const [raoJobId, setRaoJobId] = useState(hydrodynamicJob?.status === "completed" ? hydrodynamicJob.job_id : "");
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [activePlot, setActivePlot] = useState("spectrum");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedSeaState) return;
    setInputs((current) => ({ ...current, hs: selectedSeaState.hs, tp: selectedSeaState.tp }));
  }, [selectedSeaState]);

  useEffect(() => {
    let cancelled = false;
    listAnalyses().then((data) => {
      if (cancelled) return;
      const completed = completedAnalyses(data);
      setAnalyses(completed);
      setRaoJobId((current) => {
        if (hydrodynamicJob?.status === "completed" && completed.some((job) => job.job_id === hydrodynamicJob.job_id)) return hydrodynamicJob.job_id;
        return completed.some((job) => job.job_id === current) ? current : (completed[0]?.job_id || "");
      });
    }).catch((requestError) => { if (!cancelled) setError(requestError.message); });
    return () => { cancelled = true; };
  }, [hydrodynamicJob]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      previewSpectrum({ hs: Number(inputs.hs), tp: Number(inputs.tp), gamma: Number(inputs.gamma), points: 500 })
        .then(setPreview)
        .catch(() => setPreview(null));
    }, 180);
    return () => { window.clearTimeout(timer); };
  }, [inputs.hs, inputs.tp, inputs.gamma]);

  const selectedAnalysis = analyses.find((job) => job.job_id === raoJobId);
  const update = (key, value) => setInputs((current) => ({ ...current, [key]: value }));
  const run = async () => {
    if (!raoJobId) { setError("Complete or select a hydrodynamic analysis containing RAOs first."); return; }
    setLoading(true);
    setError("");
    try {
      const data = await calculateResponse({
        rao_job_id: raoJobId,
        hs: Number(inputs.hs),
        tp: Number(inputs.tp),
        gamma: Number(inputs.gamma),
        heading_deg: Number(inputs.heading_deg),
        speed_knots: Number(inputs.speed_knots),
        point: { x: Number(inputs.x), y: Number(inputs.y), z: Number(inputs.z) },
        duration_days: Number(inputs.duration_days),
        exceedance_probability: Number(inputs.exceedance_percent) / 100,
      });
      setResult(data);
      setActivePlot("acceleration");
    } catch (requestError) { setError(requestError.message); }
    finally { setLoading(false); }
  };

  const chart = useMemo(() => {
    if (activePlot === "spectrum") {
      const source = result || preview;
      if (!source) return null;
      return {
        x: source.omega,
        xLabel: "ω [rad/s]",
        yLabel: "Sη [m²·s/rad]",
        series: [
          { key: "pm", label: "Pierson–Moskowitz", values: source.pm, color: "#9aa9b7" },
          { key: "jonswap", label: "JONSWAP", values: source.jonswap, color: "#0797a5" },
        ],
      };
    }
    if (!result) return null;
    if (activePlot === "motion") return {
      x: result.omega,
      xLabel: "ω [rad/s]",
      yLabel: "Motion response PSD",
      series: result.available_dofs.map((dof) => ({ key: dof, label: dof, values: result.motion_spectra[dof], color: DOF_COLORS[dof] })),
    };
    return {
      x: result.encounter_omega,
      xLabel: "|ωe| [rad/s]",
      yLabel: "Acceleration PSD [(m/s²)²·s/rad]",
      logY: true,
      series: Object.keys(AXIS_COLORS).map((axis) => ({ key: axis, label: axis, values: result.point_acceleration_spectra[axis], color: AXIS_COLORS[axis] })),
    };
  }, [activePlot, preview, result]);

  return (
    <main className="module-page response-page">
      <div className="module-heading response-heading">
        <div><h1>Spectral response & acceleration</h1><p>Couple a JONSWAP sea state with complex vessel RAOs and evaluate acceleration at a specified point.</p></div>
        <span className="method-chip">Complex RAO phase</span>
      </div>

      <section className="response-setup-band">
        <label><span>Hs</span><span className="unit-input"><input aria-label="Response Hs" type="number" min="0.01" step="0.05" value={inputs.hs} onChange={(event) => update("hs", event.target.value)} /><i>m</i></span></label>
        <label><span>Tp</span><span className="unit-input"><input aria-label="Response Tp" type="number" min="0.1" step="0.1" value={inputs.tp} onChange={(event) => update("tp", event.target.value)} /><i>s</i></span></label>
        <label><span>JONSWAP γ</span><input aria-label="JONSWAP gamma" type="number" min="1" max="10" step="0.1" value={inputs.gamma} onChange={(event) => update("gamma", event.target.value)} /></label>
        <label className="rao-select"><span>Hydrodynamic RAOs</span><select aria-label="Hydrodynamic RAO analysis" value={raoJobId} onChange={(event) => setRaoJobId(event.target.value)}><option value="">Select a completed analysis</option>{analyses.map((job) => <option key={job.job_id} value={job.job_id}>{job.filename || "Hull analysis"} · {job.job_id.slice(0, 8)}</option>)}</select></label>
        <label><span>Wave heading</span><span className="unit-input"><input aria-label="Wave heading" type="number" min="0" max="360" step="1" value={inputs.heading_deg} onChange={(event) => update("heading_deg", event.target.value)} /><i>°</i></span></label>
        <label><span>Speed</span><span className="unit-input"><input aria-label="Vessel speed" type="number" min="0" step="0.1" value={inputs.speed_knots} onChange={(event) => update("speed_knots", event.target.value)} /><i>kn</i></span></label>
        <button className="button primary calculate-button" type="button" onClick={run} disabled={loading || !raoJobId}>{loading ? <LoaderCircle className="spin" size={17} /> : <Play size={16} fill="currentColor" />} Calculate response</button>
      </section>

      {error ? <div className="inline-error response-error"><AlertTriangle size={16} />{error}</div> : null}
      {!analyses.length ? (
        <section className="response-prerequisite"><Waves size={30} /><div><h2>Hydrodynamic RAOs are required</h2><p>Run the Capytaine workflow first. When it completes, its complex RAO file becomes available here.</p></div><button className="button primary" type="button" onClick={onOpenHydrodynamics}>Open hydrodynamics <ArrowRight size={17} /></button></section>
      ) : null}

      <div className="response-layout">
        <aside className="evaluation-panel">
          <div className="panel-kicker"><MapPin size={16} /> Evaluation point</div>
          <p>Coordinates are relative to the vessel reference origin used by the RAO model.</p>
          <div className="coordinate-stack">
            {(["x", "y", "z"]).map((axis) => <label key={axis}><span>{axis.toUpperCase()}</span><span className="unit-input"><input aria-label={`Evaluation point ${axis}`} type="number" step="0.1" value={inputs[axis]} onChange={(event) => update(axis, event.target.value)} /><i>m</i></span></label>)}
          </div>
          <div className="point-axis-sketch" aria-label="Vessel coordinate convention"><span className="axis-line x">+X forward</span><span className="axis-line y">+Y port</span><span className="axis-line z">+Z upward</span><i /></div>
          <div className="advanced-response-inputs">
            <label><span>Exposure duration</span><span className="unit-input"><input aria-label="Exposure duration" type="number" min="0.01" step="1" value={inputs.duration_days} onChange={(event) => update("duration_days", event.target.value)} /><i>days</i></span></label>
            <label><span>Exceedance probability</span><span className="unit-input"><input aria-label="Exceedance probability" type="number" min="0.001" max="100" step="0.1" value={inputs.exceedance_percent} onChange={(event) => update("exceedance_percent", event.target.value)} /><i>%</i></span></label>
          </div>
        </aside>

        <section className="response-chart-panel">
          <div className="response-tabs" role="tablist">
            <button type="button" role="tab" aria-selected={activePlot === "spectrum"} className={activePlot === "spectrum" ? "active" : ""} onClick={() => setActivePlot("spectrum")}>Wave spectrum</button>
            <button type="button" role="tab" aria-selected={activePlot === "motion"} disabled={!result} className={activePlot === "motion" ? "active" : ""} onClick={() => setActivePlot("motion")}>Motion spectra</button>
            <button type="button" role="tab" aria-selected={activePlot === "acceleration"} disabled={!result} className={activePlot === "acceleration" ? "active" : ""} onClick={() => setActivePlot("acceleration")}>Point acceleration</button>
          </div>
          {chart ? <ScientificLineChart x={chart.x} series={chart.series} xLabel={chart.xLabel} yLabel={chart.yLabel} logY={chart.logY} /> : <div className="panel-loading"><LoaderCircle className="spin" /><span>Preparing spectrum…</span></div>}
          {result?.warnings?.length ? <div className="calculation-warnings">{result.warnings.map((warning) => <span key={warning}><AlertTriangle size={14} />{warning}</span>)}</div> : null}
        </section>

        <aside className="response-results-panel">
          <div className="panel-kicker"><CheckCircle2 size={16} /> Point results</div>
          {result ? (
            <>
              <p>RMS and expected maximum over {result.inputs.duration_days} days.</p>
              <div className="axis-result-list">{Object.entries(result.point_results).map(([axis, metrics]) => <div key={axis}><span style={{ color: AXIS_COLORS[axis] }}>{axis}</span><strong>{displayNumber(metrics.rms)} <small>m/s² RMS</small></strong><em>{displayNumber(metrics.expected_max)} m/s² expected max</em></div>)}</div>
              <dl className="response-facts"><div><dt>Requested heading</dt><dd>{result.inputs.heading_requested_deg}°</dd></div><div><dt>Solved heading used</dt><dd>{result.inputs.heading_selected_deg}°</dd></div><div><dt>Spectrum Hm0</dt><dd>{displayNumber(result.spectrum_metrics.hm0, 2)} m</dd></div><div><dt>RAO source</dt><dd>{selectedAnalysis?.job_id.slice(0, 8)}</dd></div></dl>
              <a className="button secondary wide download-response" href={result.download_url} download><Download size={17} /> Download response package</a>
            </>
          ) : <div className="results-placeholder"><span>Run the calculation to see RMS, expected maxima, and response spectra.</span></div>}
        </aside>
      </div>

      {result ? (
        <section className="dof-results-section"><div><h2>Rigid-body response by degree of freedom</h2><p>Rotational motion is reported in radians; translational motion in metres.</p></div><div className="response-table-scroll"><table className="analysis-table"><thead><tr><th>DOF</th><th>Status</th><th>Motion RMS</th><th>Acceleration RMS</th><th>Peak period [s]</th></tr></thead><tbody>{result.dof_results.map((row) => <tr key={row.dof} className={row.available ? "" : "unavailable"}><td><strong>{row.dof}</strong></td><td>{row.available ? "Available" : "Treated as zero"}</td><td>{displayNumber(row.motion_rms)} {row.motion_unit}</td><td>{displayNumber(row.acceleration_rms)} {row.acceleration_unit}</td><td>{displayNumber(row.peak_period_s, 2)}</td></tr>)}</tbody></table></div></section>
      ) : null}
    </main>
  );
}
