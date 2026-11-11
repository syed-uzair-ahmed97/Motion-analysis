import { CheckCircle2, FileWarning } from "lucide-react";
import { DOFS, formatBytes, parseHeadings } from "../constants";

function SummaryItem({ label, children }) {
  return (
    <div className="summary-item">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function MeshInspectionRail({ form, inspection }) {
  return (
    <aside className="summary-rail mesh-inspection-rail">
      <h2>Mesh inspection</h2>
      <div className={`summary-status ${form.meshFile ? "ready" : "missing"}`}>
        {form.meshFile ? <CheckCircle2 size={18} /> : <FileWarning size={18} />}
        <span>{form.meshFile ? form.meshFile.name : "No OBJ attached"}</span>
      </div>
      {form.meshFile ? (
        <>
          <dl>
            <SummaryItem label="File size">{formatBytes(form.meshFile.size)}</SummaryItem>
            <SummaryItem label="Geometry">
              {inspection?.status === "ready" ? `${inspection.vertexCount.toLocaleString()} vertices · ${inspection.faceCount.toLocaleString()} faces` : inspection?.status === "error" ? "Preview could not be parsed" : "Reading OBJ…"}
            </SummaryItem>
            {inspection?.status === "ready" ? <SummaryItem label="Waterline check">{inspection.waterlineStatus}</SummaryItem> : null}
          </dl>
          {inspection?.status === "error" ? <div className="mesh-diagnostic error"><strong>OBJ preview error</strong><span>{inspection.error}</span></div> : null}
          {inspection?.status === "ready" && inspection.warnings.length ? (
            <div className="mesh-diagnostic warning">
              <strong>Check before solving</strong>
              {inspection.warnings.map((warning) => <span key={warning}>{warning}</span>)}
            </div>
          ) : null}
        </>
      ) : (
        <p className="mesh-empty-note">Attach an OBJ to inspect its geometry, global origin, dimensions and position relative to the waterline before entering analysis parameters.</p>
      )}
      <div className="axis-legend">
        <strong>Coordinate convention</strong>
        <span><i className="axis-x" /> X — forward</span>
        <span><i className="axis-y" /> Y — port</span>
        <span><i className="axis-z" /> Z — up</span>
        <small>The coloured axes are drawn from the OBJ global origin (0, 0, 0).</small>
      </div>
    </aside>
  );
}

export default function SummaryRail({ form, activeStep, job, meshInspection }) {
  if (activeStep === 0) return <MeshInspectionRail form={form} inspection={meshInspection} />;
  const headings = parseHeadings(form.analysis.headings_text);
  const selectedDofs = DOFS.filter((dof) => form.analysis.degrees_of_freedom.includes(dof));
  return (
    <aside className="summary-rail">
      <h2>Analysis brief</h2>
      <div className={`summary-status ${form.meshFile ? "ready" : "missing"}`}>
        {form.meshFile ? <CheckCircle2 size={18} /> : <FileWarning size={18} />}
        <span>{form.meshFile ? form.meshFile.name : "No hull attached"}</span>
      </div>
      <dl>
        <SummaryItem label="Vessel mass">
          {form.body.mass_kg === "" ? "Displaced-water equilibrium" : `${Number(form.body.mass_kg).toLocaleString()} kg`}
        </SummaryItem>
        <SummaryItem label="Water">
          {form.environment.water_density_kg_m3} kg/m³ · {form.environment.deep_water ? "Deep water" : `${form.environment.water_depth_m || 0} m depth`}
        </SummaryItem>
        <SummaryItem label="Wave periods">
          {form.analysis.period_min_s}–{form.analysis.period_max_s} s · {form.analysis.period_count} values
        </SummaryItem>
        <SummaryItem label="Headings">
          {headings.length ? `${headings.join("°, ")}°` : "Not defined"}
        </SummaryItem>
        <SummaryItem label="Active DOFs">
          <span className="summary-dofs">{selectedDofs.join(", ") || "None"}</span>
        </SummaryItem>
        <SummaryItem label="Rotation reference">Centre of gravity</SummaryItem>
      </dl>
      {activeStep === 4 ? (
        <div className="formula-note">
          <strong>Response model</strong>
          <span>−ω²(M + A) − iω(B + Bₑ) + (C + Kₘ)</span>
          <small>Roll target: {form.response.roll_damping_target_percent || 0}% critical. Mooring stiffness is supplied diagonally per DOF.</small>
        </div>
      ) : null}
      {job ? (
        <div className={`job-mini-status ${job.status}`}>
          <span className="status-dot" />
          <div>
            <strong>{job.status === "completed" ? "Analysis complete" : job.status === "failed" ? "Analysis failed" : "Analysis running"}</strong>
            <small>{job.message}</small>
          </div>
        </div>
      ) : null}
    </aside>
  );
}
