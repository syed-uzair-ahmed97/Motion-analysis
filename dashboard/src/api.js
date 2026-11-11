export async function startAnalysis(form, headings) {
  const payload = {
    mesh: form.mesh,
    body: form.body,
    environment: {
      ...form.environment,
      water_depth_m: form.environment.deep_water ? null : form.environment.water_depth_m,
    },
    analysis: {
      ...form.analysis,
      wave_headings_deg: headings,
    },
    response: form.response,
  };
  delete payload.analysis.headings_text;

  const request = new FormData();
  request.append("mesh_file", form.meshFile);
  request.append("payload", JSON.stringify(payload));
  const response = await fetch("/api/analysis", { method: "POST", body: request });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Unable to start analysis");
  return data;
}

export async function fetchAnalysis(jobId) {
  const response = await fetch(`/api/analysis/${jobId}`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Unable to read analysis status");
  return data;
}

export async function openResultsFolder(jobId) {
  const response = await fetch(`/api/analysis/${jobId}/open-folder`, { method: "POST" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Unable to open results folder");
  return data;
}

async function readJson(response, fallback) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || fallback);
  return data;
}

export async function listAnalyses() {
  return readJson(await fetch("/api/analysis"), "Unable to list hydrodynamic analyses");
}

export async function fetchDemoSeaStates(hsBinWidth = 0.5, tpBinWidth = 1.0) {
  const query = new URLSearchParams({
    hs_bin_width: String(hsBinWidth),
    tp_bin_width: String(tpBinWidth),
  });
  return readJson(await fetch(`/api/sea-states/demo?${query}`), "Unable to build the demonstration scatter diagram");
}

export async function listSeaStateResults() {
  return readJson(await fetch("/api/sea-states"), "Unable to load saved sea-state analyses");
}

export async function fetchSeaStateResult(jobId) {
  return readJson(await fetch(`/api/sea-states/${jobId}`), "Unable to reopen the sea-state analysis");
}

async function submitSeaStateFiles(endpoint, files, config) {
  const selectedFiles = Array.from(files || []);
  if (!selectedFiles.length) throw new Error("Attach a CSV or NetCDF wave-history file first");
  if (selectedFiles.length > 100) throw new Error("Select no more than 100 wave-history files per analysis");
  const request = new FormData();
  selectedFiles.forEach((file) => request.append("data_files", file));
  request.append("payload", JSON.stringify(config));
  return readJson(await fetch(endpoint, { method: "POST", body: request }), "Unable to build the scatter diagram");
}

export async function inspectSeaStateFiles(files) {
  const selectedFiles = Array.from(files || []);
  if (!selectedFiles.length) throw new Error("Attach a CSV or NetCDF wave-history file first");
  if (selectedFiles.length > 100) throw new Error("Select no more than 100 wave-history files per analysis");
  const request = new FormData();
  selectedFiles.forEach((file) => request.append("data_files", file));
  return readJson(await fetch("/api/sea-states/inspect", { method: "POST", body: request }), "Unable to inspect the wave-history source");
}

export async function analyzeSeaStates(files, config) {
  return submitSeaStateFiles("/api/sea-states", files, config);
}

export async function analyzeLocationSeaStates(files, config) {
  return submitSeaStateFiles("/api/sea-states/location", files, config);
}

export async function analyzeRouteSeaStates(files, config) {
  return submitSeaStateFiles("/api/sea-states/route", files, config);
}

export async function generateSeaRoute(payload) {
  return readJson(await fetch("/api/sea-routes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), "Unable to generate the sea route");
}

export async function previewSpectrum(payload) {
  return readJson(await fetch("/api/spectrum", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), "Unable to calculate the JONSWAP spectrum");
}

export async function calculateResponse(payload) {
  return readJson(await fetch("/api/responses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), "Unable to calculate the vessel response");
}
