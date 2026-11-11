import { Check } from "lucide-react";
import { STEPS } from "../constants";
import { Gauge, stepIcons } from "./Icons";

export function Header({ version = "2.3.1" }) {
  return (
    <header className="app-header">
      <div className="brand">
        <Gauge aria-hidden="true" size={25} strokeWidth={1.8} />
        <span>Motion Analysis</span>
      </div>
      <div className="version">Capytaine {version}</div>
    </header>
  );
}

export function StepRail({ activeStep, completedThrough, onSelect }) {
  return (
    <nav className="step-rail" aria-label="Analysis setup steps">
      {STEPS.map((step, index) => {
        const Icon = stepIcons[index];
        const active = index === activeStep;
        const completed = index < completedThrough || (completedThrough === STEPS.length && index < STEPS.length);
        return (
          <button
            className={`step-item${active ? " active" : ""}${completed ? " completed" : ""}`}
            key={step.key}
            type="button"
            onClick={() => onSelect(index)}
            aria-current={active ? "step" : undefined}
          >
            <span className="step-number">{completed ? <Check size={15} strokeWidth={2.5} /> : index + 1}</span>
            <Icon className="step-icon" aria-hidden="true" size={20} strokeWidth={1.7} />
            <span className="step-label">{step.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

export function AppShell({ children, activeStep, completedThrough, onSelectStep, version }) {
  return (
    <div className="app-shell">
      <Header version={version} />
      <StepRail activeStep={activeStep} completedThrough={completedThrough} onSelect={onSelectStep} />
      {children}
    </div>
  );
}
