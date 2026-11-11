import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Download,
  FolderOpen,
  LoaderCircle,
  Play,
  RotateCw,
} from "lucide-react";
import { formatBytes, parseHeadings } from "../constants";

const IMPORTANT_OUTPUTS = [
  "hydrodynamics_and_rao.nc",
  "rao.csv",
  "added_mass.csv",
  "radiation_damping.csv",
  "roll_damping_percent_critical.csv",
  "excitation_force.csv",
  "summary.json",
];

function ConfigurationReview({ form }) {
  const headings = parseHeadings(form.analysis.headings_text);
  return (
    <div className="review-grid">
      <section><h3>Hull and vessel</h3><dl><div><dt>OBJ</dt><dd>{form.meshFile?.name || "Not attached"}</dd></div><div><dt>Mass</dt><dd>{form.body.mass_kg || "Displaced-water equilibrium"}</dd></div><div><dt>Centre of gravity</dt><dd>[{form.body.center_of_mass_m.join(", ")}] m</dd></div></dl></section>
      <section><h3>Environment and waves</h3><dl><div><dt>Water</dt><dd>{form.environment.water_density_kg_m3} kg/m³</dd></div><div><dt>Periods</dt><dd>{form.analysis.period_min_s}–{form.analysis.period_max_s} s</dd></div><div><dt>Headings</dt><dd>{headings.join("°, ")}°</dd></div></dl></section>
      <section><h3>Motion model</h3><dl><div><dt>DOFs</dt><dd>{form.analysis.degrees_of_freedom.join(", ")}</dd></div><div><dt>Roll damping</dt><dd>{form.response.roll_damping_target_percent || 0}% critical</dd></div><div><dt>Rotation reference</dt><dd>Centre of gravity</dd></div><div><dt>Inertia</dt><dd>{form.body.inertia_mode === "custom" ? "User supplied" : "Mesh estimate"}</dd></div></dl></section>
    </div>
  );
}

export default function ResultsPanel({ form, job, error, onRun, onOpenFolder, onUseInResponse }) {
  const [plot, setPlot] = useState("magnitude");
  const [showLog, setShowLog] = useState(false);
  const running = job && ["queued", "running"].includes(job.status);
  const completed = job?.status === "completed";
  const failed = job?.status === "failed";
  const outputs = completed ? IMPORTANT_OUTPUTS.map((name) => job.outputs?.find((item) => item.name === name)).filter(Boolean) : [];

  return (
    <>
      <div className="review-title-row">
        <div><h1>Review & run</h1><p>Confirm the setup, then launch the local Capytaine solver.</p></div>
        {completed ? <span className="complete-label"><CheckCircle2 size={19} /> Analysis complete</span> : null}
      </div>
      {!completed ? <ConfigurationReview form={form} /> : null}
      {running ? (
        <div className="run-state">
          <LoaderCircle className="spin" size={30} />
          <h2>{job.message || "Solving hydrodynamic cases"}</h2>
          <p>The dashboard is computing radiation, diffraction and RAO results. You can keep this page open.</p>
          <div className="indeterminate"><span /></div>
        </div>
      ) : null}
      {failed ? (
        <div className="run-state failed"><AlertTriangle size={30} /><h2>Analysis failed</h2><p>{job.message}</p></div>
      ) : null}
      {error ? <div className="inline-error">{error}</div> : null}

      {completed ? (
        <div className="results-layout">
          <section className="plot-panel">
            <div className="plot-tabs" role="tablist">
              <button className={plot === "magnitude" ? "active" : ""} onClick={() => setPlot("magnitude")} role="tab" aria-selected={plot === "magnitude"}>RAO magnitude</button>
              <button className={plot === "phase" ? "active" : ""} onClick={() => setPlot("phase")} role="tab" aria-selected={plot === "phase"}>RAO phase</button>
            </div>
            <div className="plot-image-frame">
              <img
                src={`/api/analysis/${job.job_id}/files/rao_${plot}.png`}
                alt={`Response Amplitude Operator ${plot} plot`}
              />
            </div>
          </section>
          <aside className="outputs-panel">
            <button className="button primary wide" type="button" onClick={onUseInResponse}><Play size={17} /> Use RAOs in response</button>
            <button className="button secondary wide" type="button" onClick={onRun}><RotateCw size={17} /> Run again</button>
            <button className="button secondary wide" type="button" onClick={onOpenFolder}><FolderOpen size={17} /> Open results folder</button>
            <div className="outputs-list">
              <h3>Outputs</h3>
              {outputs.map((item) => (
                <a key={item.name} href={`/api/analysis/${job.job_id}/files/${item.name}`} download>
                  <span><strong>{item.name}</strong><small>{formatBytes(item.size)}</small></span><Download size={16} />
                </a>
              ))}
            </div>
            <button className="log-toggle" type="button" onClick={() => setShowLog((value) => !value)}>
              <span><strong>Solver log</strong><small>{failed ? "Error" : "No errors"}</small></span><ChevronDown className={showLog ? "open" : ""} size={17} />
            </button>
          </aside>
        </div>
      ) : null}
      {showLog && job?.log_tail ? <pre className="solver-log">{job.log_tail}</pre> : null}
      {!running && !completed ? (
        <div className="review-run-bar">
          <div><strong>Ready to solve</strong><span>The run time depends on panel count, periods, headings and active DOFs.</span></div>
          <button className="button primary" type="button" onClick={onRun}><Play size={17} fill="currentColor" /> Run analysis</button>
        </div>
      ) : null}
    </>
  );
}
