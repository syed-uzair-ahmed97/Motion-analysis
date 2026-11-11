import { Activity, CheckCircle2, Grid3X3, Waves } from "lucide-react";

const stages = [
  {
    key: "sea-states",
    number: "01",
    title: "Sea-state modelling",
    description: "The reference workflow uses hourly Hs and Tp records from ERA5, the fifth-generation ECMWF reanalysis produced by the Copernicus Climate Change Service. Valid paired observations are binned into count and probability scatter diagrams for representative sea-state selection.",
    action: "Open sea states",
    icon: Grid3X3,
    basis: "Hs–Tp occurrence matrix and selected representative sea state",
  },
  {
    key: "hydrodynamics",
    number: "02",
    title: "Hydrodynamic analysis",
    description: "Capytaine is a Python boundary-element-method solver built from Nemoh for linear potential-flow radiation and diffraction in the frequency domain. It calculates hydrodynamic coefficients, excitation forces, and complex vessel RAOs from the panelized hull.",
    action: "Open hydrodynamics",
    icon: Waves,
    basis: "Linear potential-flow RAOs with configured roll damping and mooring stiffness",
  },
  {
    key: "response",
    number: "03",
    title: "Acceleration & response analysis",
    description: "A selected sea state is represented by a JONSWAP wave spectrum and coupled with complex vessel RAOs. The workflow calculates six-DOF motion spectra and acceleration at user-defined vessel points, including RMS values and expected maxima.",
    action: "Open response analysis",
    icon: Activity,
    basis: "JONSWAP spectrum, complex RAO phase, and rigid-body point transformation",
  },
];

export default function OverviewWorkspace({ seaState, hydrodynamicJob, onNavigate }) {
  const hydroReady = hydrodynamicJob?.status === "completed" && hydrodynamicJob?.rao_available !== false;
  return (
    <main className="module-page overview-page">
      <div className="module-heading">
        <div>
          <h1>Motion Analysis Overview</h1>
          <p>A three-stage workflow to model environmental conditions, compute hydrodynamic behaviour, and evaluate vessel response.</p>
        </div>
      </div>
      <section className="pipeline" aria-label="Analysis workflow">
        {stages.map(({ key, number, title, description, action, icon: Icon }) => {
          const ready = key === "sea-states" ? Boolean(seaState) : key === "hydrodynamics" ? hydroReady : Boolean(seaState && hydroReady);
          return (
            <article className="pipeline-stage" key={key}>
              <div className="pipeline-number">{number}</div>
              <div className="pipeline-icon"><Icon size={25} strokeWidth={1.55} /></div>
              <div className="pipeline-copy">
                <div className="pipeline-title-row">
                  <h2>{title}</h2>
                  {ready ? <span className="ready-mark"><CheckCircle2 size={16} /> Ready</span> : null}
                </div>
                <p>{description}</p>
                {key === "sea-states" && seaState ? <small>Selected: Hs {seaState.hs.toFixed(2)} m · Tp {seaState.tp.toFixed(1)} s</small> : null}
                {key === "hydrodynamics" && hydroReady ? <small>RAO analysis {hydrodynamicJob.job_id.slice(0, 8)} complete</small> : null}
                {key === "response" && !ready ? <small>Select a sea state and complete a hydrodynamic analysis first.</small> : null}
              </div>
              <button type="button" onClick={() => onNavigate(key)}>{action}</button>
            </article>
          );
        })}
      </section>
      <section className="method-band" aria-label="Method summary">
        {stages.map(({ key, title, basis, icon: Icon }) => (
          <div key={key}>
            <Icon size={19} strokeWidth={1.6} aria-hidden="true" />
            <span><strong>{title}</strong><small>{basis}</small></span>
          </div>
        ))}
      </section>
    </main>
  );
}
