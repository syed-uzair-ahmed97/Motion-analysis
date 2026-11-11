export function Field({ label, hint, unit, error, children, className = "" }) {
  return (
    <label className={`field ${className}`}>
      <span className="field-label">{label}</span>
      {hint ? <span className="field-hint">{hint}</span> : null}
      <span className={`input-shell${error ? " invalid" : ""}`}>
        {children}
        {unit ? <span className="input-unit">{unit}</span> : null}
      </span>
      {error ? <span className="field-error">{error}</span> : null}
    </label>
  );
}

export function NumberInput({ value, onChange, min, step = "any", ariaLabel }) {
  return (
    <input
      aria-label={ariaLabel}
      type="number"
      value={value}
      min={min}
      step={step}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export function Toggle({ checked, onChange, label, description }) {
  return (
    <label className="toggle-row">
      <span>
        <strong>{label}</strong>
        {description ? <small>{description}</small> : null}
      </span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="toggle-control" aria-hidden="true" />
    </label>
  );
}

export function SectionHeading({ title, description, action }) {
  return (
    <div className="section-heading">
      <div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {action}
    </div>
  );
}
