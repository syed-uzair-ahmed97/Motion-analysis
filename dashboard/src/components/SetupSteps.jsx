import { useRef, useState } from "react";
import { Check, FileUp, Info, RotateCcw } from "lucide-react";
import { DOFS, ROTATIONAL_DOFS } from "../constants";
import { Field, NumberInput, SectionHeading, Toggle } from "./Fields";
import MeshViewer from "./MeshViewer";
import { UploadCloud } from "./Icons";

function HullSketch() {
  return (
    <svg className="hull-sketch" viewBox="0 0 460 150" role="img" aria-label="Wireframe hull crossing a waterline">
      <path className="waterline" d="M25 99H435" />
      <path d="M76 46c52-19 241-21 326 2-12 22-23 40-50 51-66 24-201 29-255 4-15-7-20-27-21-57Z" />
      <path d="M83 60c75 15 215 15 300-2M93 79c83 14 198 15 274 0M110 98c72 12 165 13 234 2" />
      <path d="M118 50 143 108M170 43l15 74M226 40l1 81M282 42l-14 76M336 45l-30 64" />
    </svg>
  );
}

export function HullStep({ form, updateSection, setMeshFile, setMeshInspection, error }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const acceptFile = (file) => {
    if (file?.name.toLowerCase().endsWith(".obj")) setMeshFile(file);
  };
  return (
    <>
      <SectionHeading title="Hull mesh" description="Attach the panelized OBJ and confirm its scale and waterline." />
      {form.meshFile ? (
        <MeshViewer
          file={form.meshFile}
          scaleToM={form.mesh.scale_to_m}
          waterlineZ={form.environment.free_surface_z_m}
          onReplace={() => inputRef.current?.click()}
          onInspection={setMeshInspection}
        />
      ) : (
        <div
          className={`upload-zone${dragging ? " dragging" : ""}`}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFile(event.dataTransfer.files[0]); }}
        >
          <HullSketch />
          <UploadCloud className="upload-icon" size={30} />
          <strong>Drop OBJ hull here</strong>
          <span>Triangles, quadrilaterals and polygon faces are supported</span>
          <button className="button secondary compact" type="button" onClick={() => inputRef.current?.click()}>
            <FileUp size={16} /> Browse file
          </button>
        </div>
      )}
      <input ref={inputRef} className="visually-hidden" type="file" accept=".obj" onChange={(event) => acceptFile(event.target.files[0])} />
      {error ? <div className="inline-error">{error}</div> : null}
      <div className="form-grid two-column">
        <Field label="Mesh units" hint="Original OBJ coordinate units">
          <select
            value={form.mesh.units}
            onChange={(event) => {
              const scales = { m: 1, mm: 0.001, cm: 0.01 };
              updateSection("mesh", { units: event.target.value, scale_to_m: scales[event.target.value] });
            }}
          >
            <option value="m">metres (m)</option>
            <option value="mm">millimetres (mm)</option>
            <option value="cm">centimetres (cm)</option>
          </select>
        </Field>
        <Field label="Scale to metres" hint="Multiplier applied to every OBJ coordinate">
          <NumberInput ariaLabel="Scale to metres" value={form.mesh.scale_to_m} min={0.000000001} onChange={(value) => updateSection("mesh", { scale_to_m: value })} />
        </Field>
        <Field label="Waterline z" hint="Mean free-surface position in scaled coordinates" unit="m">
          <NumberInput ariaLabel="Waterline z" value={form.environment.free_surface_z_m} onChange={(value) => updateSection("environment", { free_surface_z_m: value })} />
        </Field>
        <Field label="Coordinate convention" hint="The dashboard expects this orientation">
          <input value="x forward · y port · z up" readOnly />
        </Field>
      </div>
      <div className="open-panel mesh-repair">
        <h3>Mesh repair</h3>
        <Toggle checked={form.mesh.heal} onChange={(value) => updateSection("mesh", { heal: value })} label="Heal mesh" description="Merge duplicates and remove invalid faces" />
        <Toggle checked={form.mesh.closed_mesh} onChange={(value) => updateSection("mesh", { closed_mesh: value })} label="Closed mesh" description="Use outward-normal healing for a watertight hull" />
        <Toggle checked={form.mesh.flip_normals} onChange={(value) => updateSection("mesh", { flip_normals: value })} label="Flip normals" description="Use only when the imported normals point inward" />
      </div>
    </>
  );
}

export function VesselStep({ form, updateSection, updateVector, error }) {
  const custom = form.body.inertia_mode === "custom";
  const updateInertia = (key, value) => updateSection("body", { inertia: { ...form.body.inertia, [key]: value } });
  return (
    <>
      <SectionHeading title="Vessel" description="Define mass properties about the centre of gravity." />
      <div className="form-grid two-column">
        <Field label="Analysis name" hint="Used for folders and dataset labels">
          <input value={form.body.name} onChange={(event) => updateSection("body", { name: event.target.value })} />
        </Field>
        <Field label="Mass" hint="Leave blank to use displaced-water equilibrium" unit="kg">
          <NumberInput ariaLabel="Vessel mass" value={form.body.mass_kg} min={0} onChange={(value) => updateSection("body", { mass_kg: value })} />
        </Field>
      </div>
      <div className="open-panel">
        <div className="panel-heading">
          <div><h3>Centre of gravity</h3><p>All rotational DOFs use this point. There is no separate rotation-centre input.</p></div>
          <Info size={18} />
        </div>
        <div className="vector-grid">
          {["x", "y", "z"].map((axis, index) => (
            <Field key={axis} label={`CG ${axis}`} unit="m">
              <NumberInput ariaLabel={`Centre of gravity ${axis}`} value={form.body.center_of_mass_m[index]} onChange={(value) => updateVector("body", "center_of_mass_m", index, value)} />
            </Field>
          ))}
        </div>
      </div>
      <div className="open-panel">
        <div className="panel-heading">
          <div><h3>Rigid-body inertia</h3><p>Use the mesh approximation for early checks or enter measured values for engineering RAOs.</p></div>
        </div>
        <div className="choice-row" role="radiogroup" aria-label="Inertia source">
          <label className={custom ? "" : "selected"}><input type="radio" name="inertia" checked={!custom} onChange={() => updateSection("body", { inertia_mode: "estimate" })} /> Homogeneous mesh estimate</label>
          <label className={custom ? "selected" : ""}><input type="radio" name="inertia" checked={custom} onChange={() => updateSection("body", { inertia_mode: "custom" })} /> Enter inertia values</label>
        </div>
        {custom ? (
          <div className="inertia-grid">
            {["ixx", "iyy", "izz", "ixy", "ixz", "iyz"].map((key) => (
              <Field key={key} label={key.toUpperCase()} unit="kg·m²">
                <NumberInput ariaLabel={key.toUpperCase()} value={form.body.inertia[key]} onChange={(value) => updateInertia(key, value)} />
              </Field>
            ))}
          </div>
        ) : null}
      </div>
      {error ? <div className="inline-error">{error}</div> : null}
    </>
  );
}

export function EnvironmentStep({ form, updateSection }) {
  return (
    <>
      <SectionHeading title="Environment" description="Set the fluid properties and water depth used by the BEM solver." />
      <div className="form-grid two-column">
        <Field label="Water density" unit="kg/m³"><NumberInput ariaLabel="Water density" value={form.environment.water_density_kg_m3} min={1} onChange={(value) => updateSection("environment", { water_density_kg_m3: value })} /></Field>
        <Field label="Gravity" unit="m/s²"><NumberInput ariaLabel="Gravity" value={form.environment.gravity_m_s2} min={0.1} onChange={(value) => updateSection("environment", { gravity_m_s2: value })} /></Field>
      </div>
      <div className="open-panel">
        <Toggle checked={form.environment.deep_water} onChange={(value) => updateSection("environment", { deep_water: value })} label="Deep water" description="Use infinite water depth in the Green function" />
        {!form.environment.deep_water ? (
          <div className="panel-inline-field"><Field label="Finite water depth" unit="m"><NumberInput ariaLabel="Finite water depth" value={form.environment.water_depth_m} min={0.01} onChange={(value) => updateSection("environment", { water_depth_m: value })} /></Field></div>
        ) : null}
      </div>
    </>
  );
}

export function WavesStep({ form, updateSection, toggleDof, error }) {
  return (
    <>
      <SectionHeading title="Waves & DOFs" description="Choose the frequency sweep, headings and motions to solve." />
      <div className="form-grid three-column">
        <Field label="Minimum period" unit="s"><NumberInput ariaLabel="Minimum wave period" value={form.analysis.period_min_s} min={0.01} onChange={(value) => updateSection("analysis", { period_min_s: value })} /></Field>
        <Field label="Maximum period" unit="s"><NumberInput ariaLabel="Maximum wave period" value={form.analysis.period_max_s} min={0.01} onChange={(value) => updateSection("analysis", { period_max_s: value })} /></Field>
        <Field label="Number of periods"><NumberInput ariaLabel="Number of wave periods" value={form.analysis.period_count} min={1} step={1} onChange={(value) => updateSection("analysis", { period_count: value })} /></Field>
      </div>
      <Field label="Wave headings" hint="Degrees, separated by commas" className="full-field">
        <input value={form.analysis.headings_text} onChange={(event) => updateSection("analysis", { headings_text: event.target.value })} placeholder="0, 45, 90, 135, 180" />
      </Field>
      <div className="open-panel">
        <h3>Degrees of freedom</h3>
        <div className="dof-selector">
          {DOFS.map((dof) => {
            const selected = form.analysis.degrees_of_freedom.includes(dof);
            return <button key={dof} type="button" className={selected ? "selected" : ""} onClick={() => toggleDof(dof)}><span>{selected ? <Check size={15} /> : null}</span>{dof}</button>;
          })}
        </div>
      </div>
      {error ? <div className="inline-error">{error}</div> : null}
    </>
  );
}

export function DampingStep({ form, updateSection, updateResponse, resetResponse }) {
  const activeDofs = DOFS.filter((dof) => form.analysis.degrees_of_freedom.includes(dof));
  const rollActive = activeDofs.includes("Roll");
  return (
    <>
      <SectionHeading title="Damping & mooring" description="Set the target Roll damping and diagonal mooring stiffness." />
      <div className="explanation-panel">
        <Info size={20} />
        <p><strong>Roll damping is entered as a percentage of critical damping.</strong> Enter 5 for 5%. The solver adds the Roll damping needed to reach this total target at the wave period with the largest Roll response.</p>
      </div>
      <div className={`roll-damping-card${rollActive ? "" : " disabled"}`}>
        <div>
          <strong>Target total Roll damping</strong>
          <span>{rollActive ? "Percentage of the critical Roll damping coefficient" : "Enable the Roll DOF in Waves & DOFs to use this target"}</span>
        </div>
        <label className="percent-input-shell">
          <input
            aria-label="Target roll damping percent critical"
            type="number"
            min="0"
            step="any"
            disabled={!rollActive}
            value={form.response.roll_damping_target_percent}
            onChange={(event) => updateSection("response", { roll_damping_target_percent: event.target.value })}
          />
          <span>% critical</span>
        </label>
      </div>
      <div className="damping-table-wrap">
        <div className="table-actions"><button type="button" onClick={resetResponse}><RotateCcw size={15} /> Reset values</button></div>
        <table className="damping-table">
          <thead><tr><th>DOF</th><th>Mooring stiffness</th><th>Units</th></tr></thead>
          <tbody>
            {activeDofs.map((dof) => {
              const rotational = ROTATIONAL_DOFS.has(dof);
              return (
                <tr key={dof}>
                  <th scope="row">{dof}</th>
                  <td><input aria-label={`${dof} mooring stiffness`} type="number" min="0" step="any" value={form.response.mooring_stiffness_diagonal[dof]} onChange={(event) => updateResponse("mooring_stiffness_diagonal", dof, event.target.value)} /></td>
                  <td><span>{rotational ? "N·m/rad" : "N/m"}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
