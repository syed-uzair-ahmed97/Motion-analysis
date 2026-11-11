export const DOFS = ["Surge", "Sway", "Heave", "Roll", "Pitch", "Yaw"];
export const ROTATIONAL_DOFS = new Set(["Roll", "Pitch", "Yaw"]);

export const STEPS = [
  { label: "Hull mesh", key: "hull" },
  { label: "Vessel", key: "vessel" },
  { label: "Environment", key: "environment" },
  { label: "Waves & DOFs", key: "waves" },
  { label: "Damping & mooring", key: "damping" },
  { label: "Review & run", key: "review" },
];

const zeroByDof = Object.fromEntries(DOFS.map((dof) => [dof, 0]));

export const INITIAL_FORM = {
  meshFile: null,
  mesh: {
    units: "m",
    scale_to_m: 1,
    heal: true,
    closed_mesh: true,
    flip_normals: false,
    lid_enabled: false,
  },
  body: {
    name: "my_hull",
    mass_kg: "",
    center_of_mass_m: [0, 0, -1],
    inertia_mode: "estimate",
    inertia: { ixx: "", iyy: "", izz: "", ixy: 0, ixz: 0, iyz: 0 },
  },
  environment: {
    water_density_kg_m3: 1025,
    gravity_m_s2: 9.81,
    free_surface_z_m: 0,
    deep_water: true,
    water_depth_m: "",
  },
  analysis: {
    period_min_s: 2,
    period_max_s: 20,
    period_count: 37,
    headings_text: "0, 45, 90, 135, 180",
    degrees_of_freedom: [...DOFS],
  },
  response: {
    roll_damping_target_percent: 0,
    mooring_stiffness_diagonal: { ...zeroByDof },
  },
};

export function parseHeadings(text) {
  return String(text)
    .split(/[;,\s]+/)
    .filter(Boolean)
    .map(Number)
    .filter(Number.isFinite);
}

export function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
