import { Activity, Grid3X3, LayoutDashboard, Menu, Waves } from "lucide-react";
import { Gauge } from "./Icons";

const MODULES = [
  { key: "overview", label: "Overview", icon: LayoutDashboard },
  { key: "sea-states", label: "Sea states", icon: Grid3X3 },
  { key: "hydrodynamics", label: "Hydrodynamics", icon: Waves },
  { key: "response", label: "Response analysis", icon: Activity },
];

export default function ProductShell({ activeModule, onSelectModule, children }) {
  return (
    <div className="product-shell">
      <header className="app-header product-header">
        <button className="nav-menu-button" type="button" aria-label="Application menu"><Menu size={20} /></button>
        <div className="brand">
          <Gauge aria-hidden="true" size={25} strokeWidth={1.8} />
          <span>Motion Analysis</span>
        </div>
        <nav className="product-nav" aria-label="Analysis workspaces">
          {MODULES.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              className={activeModule === key ? "active" : ""}
              onClick={() => onSelectModule(key)}
              aria-label={label}
              aria-current={activeModule === key ? "page" : undefined}
            >
              <Icon size={21} strokeWidth={1.7} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </header>
      <div className="product-content">{children}</div>
    </div>
  );
}
