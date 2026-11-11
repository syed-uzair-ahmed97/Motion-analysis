import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";
import { fetchAnalysis, openResultsFolder, startAnalysis } from "../api";
import ResultsPanel from "./ResultsPanel";
import { DampingStep, EnvironmentStep, HullStep, VesselStep, WavesStep } from "./SetupSteps";
import SummaryRail from "./SummaryRail";
import { stepIcons } from "./Icons";
import { DOFS, INITIAL_FORM, STEPS, parseHeadings } from "../constants";

const stepTitles = STEPS.map((step) => step.label);

function validateStep(step, form) {
  if (step === 0 && !form.meshFile) return "Attach an OBJ hull before continuing.";
  if (step === 1) {
    if (form.body.inertia_mode === "custom" && form.body.mass_kg === "") return "Mass is required when entering custom inertia values.";
    if (form.body.inertia_mode === "custom" && ["ixx", "iyy", "izz"].some((key) => form.body.inertia[key] === "")) return "IXX, IYY and IZZ are required for custom inertia.";
  }
  if (step === 3) {
    const min = Number(form.analysis.period_min_s);
    const max = Number(form.analysis.period_max_s);
    if (!(min > 0 && max > min)) return "Maximum wave period must be greater than the positive minimum period.";
    if (!parseHeadings(form.analysis.headings_text).length) return "Enter at least one numeric wave heading.";
    if (!form.analysis.degrees_of_freedom.length) return "Select at least one degree of freedom.";
  }
  return "";
}

function HydroStepper({ activeStep, completedThrough, onSelect }) {
  return (
    <nav className="hydro-stepper" aria-label="Hydrodynamic setup steps">
      {STEPS.map((step, index) => {
        const Icon = stepIcons[index];
        const active = index === activeStep;
        const completed = index < completedThrough || (completedThrough === STEPS.length && index < STEPS.length);
        return (
          <button key={step.key} type="button" className={`${active ? "active " : ""}${completed ? "completed" : ""}`} onClick={() => onSelect(index)} aria-current={active ? "step" : undefined}>
            <span className="hydro-step-number">{completed ? <Check size={13} /> : index + 1}</span>
            <Icon size={17} strokeWidth={1.7} />
            <span>{step.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

export default function HydrodynamicsWorkspace({ onJobChange, onUseInResponse }) {
  const [form, setForm] = useState(INITIAL_FORM);
  const [activeStep, setActiveStep] = useState(0);
  const [completedThrough, setCompletedThrough] = useState(0);
  const [stepError, setStepError] = useState("");
  const [job, setJob] = useState(null);
  const [runError, setRunError] = useState("");
  const [meshInspection, setMeshInspection] = useState(null);

  useEffect(() => { if (job) onJobChange(job); }, [job, onJobChange]);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return undefined;
    let cancelled = false;
    const poll = async () => {
      try {
        const nextJob = await fetchAnalysis(job.job_id);
        if (!cancelled) setJob(nextJob);
      } catch (error) {
        if (!cancelled) setRunError(error.message);
      }
    };
    const timer = window.setTimeout(poll, 1400);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [job]);

  const headings = useMemo(() => parseHeadings(form.analysis.headings_text), [form.analysis.headings_text]);
  const updateSection = (section, partial) => setForm((current) => ({ ...current, [section]: { ...current[section], ...partial } }));
  const updateVector = (section, key, index, value) => setForm((current) => {
    const vector = [...current[section][key]];
    vector[index] = value;
    return { ...current, [section]: { ...current[section], [key]: vector } };
  });
  const setMeshFile = (file) => {
    setMeshInspection(null);
    setForm((current) => ({ ...current, meshFile: file, body: { ...current.body, name: current.body.name === "my_hull" ? file.name.replace(/\.obj$/i, "") : current.body.name } }));
    setStepError("");
  };
  const toggleDof = (dof) => setForm((current) => {
    const selected = current.analysis.degrees_of_freedom.includes(dof);
    return { ...current, analysis: { ...current.analysis, degrees_of_freedom: selected ? current.analysis.degrees_of_freedom.filter((item) => item !== dof) : DOFS.filter((item) => [...current.analysis.degrees_of_freedom, dof].includes(item)) } };
  });
  const updateResponse = (matrix, dof, value) => setForm((current) => ({ ...current, response: { ...current.response, [matrix]: { ...current.response[matrix], [dof]: value } } }));
  const resetResponse = () => setForm((current) => ({ ...current, response: { roll_damping_target_percent: 0, mooring_stiffness_diagonal: Object.fromEntries(DOFS.map((dof) => [dof, 0])) } }));

  const goToStep = (next) => {
    if (next > activeStep) {
      const error = validateStep(activeStep, form);
      if (error) { setStepError(error); return; }
      setCompletedThrough((value) => Math.max(value, activeStep + 1));
    }
    setStepError("");
    setActiveStep(next);
  };
  const runAnalysis = async () => {
    const errors = [0, 1, 3].map((step) => validateStep(step, form)).filter(Boolean);
    if (errors.length) { setRunError(errors[0]); return; }
    setRunError("");
    try {
      const newJob = await startAnalysis(form, headings);
      setJob(newJob);
      setCompletedThrough(STEPS.length);
    } catch (error) { setRunError(error.message); }
  };
  const openFolder = async () => {
    try { await openResultsFolder(job.job_id); } catch (error) { setRunError(error.message); }
  };

  const stepProps = { form, updateSection, updateVector, setMeshFile, setMeshInspection, toggleDof, updateResponse, resetResponse, error: stepError };
  const stepContent = [
    <HullStep key="hull" {...stepProps} />,
    <VesselStep key="vessel" {...stepProps} />,
    <EnvironmentStep key="environment" {...stepProps} />,
    <WavesStep key="waves" {...stepProps} />,
    <DampingStep key="damping" {...stepProps} />,
  ];

  return (
    <div className="hydro-module">
      <HydroStepper activeStep={activeStep} completedThrough={completedThrough} onSelect={goToStep} />
      <main className={`workspace hydro-workspace${activeStep === 5 ? " review-workspace" : ""}`}>
        <section className="primary-content" aria-label={stepTitles[activeStep]}>
          {activeStep < 5 ? stepContent[activeStep] : <ResultsPanel form={form} job={job} error={runError} onRun={runAnalysis} onOpenFolder={openFolder} onUseInResponse={() => onUseInResponse(job)} />}
          {activeStep < 5 ? (
            <footer className="step-footer">
              <button className="button secondary" type="button" disabled={activeStep === 0} onClick={() => goToStep(activeStep - 1)}><ArrowLeft size={17} /> Back</button>
              <button className="button primary" type="button" onClick={() => goToStep(activeStep + 1)}>Continue to {STEPS[activeStep + 1].label.toLowerCase()} <ArrowRight size={17} /></button>
            </footer>
          ) : null}
        </section>
        {activeStep < 5 ? <SummaryRail form={form} activeStep={activeStep} job={job} meshInspection={meshInspection} /> : null}
      </main>
    </div>
  );
}
