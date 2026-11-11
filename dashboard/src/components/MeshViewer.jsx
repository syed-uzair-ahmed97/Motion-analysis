import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box, Crosshair, Rotate3D } from "lucide-react";
import { formatBytes } from "../constants";

const MAX_PREVIEW_FACES = 12000;
const INITIAL_VIEW = { yaw: -0.72, pitch: 0.48, zoom: 1 };

function parseObj(text) {
  const lines = text.split(/\r?\n/);
  const vertices = [];
  let faceCount = 0;
  let malformedVertices = 0;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("v ") || trimmed.startsWith("v\t")) {
      const values = trimmed.split(/\s+/).slice(1, 4).map(Number);
      if (values.length === 3 && values.every(Number.isFinite)) vertices.push(...values);
      else malformedVertices += 1;
    } else if (trimmed.startsWith("f ") || trimmed.startsWith("f\t")) {
      faceCount += 1;
    }
  }

  const vertexCount = vertices.length / 3;
  if (!vertexCount) throw new Error("This OBJ does not contain readable vertex records (v x y z).");
  if (!faceCount) throw new Error("This OBJ does not contain any face records (f ...).");

  const sampleStride = Math.max(1, Math.ceil(faceCount / MAX_PREVIEW_FACES));
  const faces = [];
  let currentVertexCount = 0;
  let seenFaces = 0;
  let invalidFaces = 0;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("v ") || trimmed.startsWith("v\t")) {
      currentVertexCount += 1;
      continue;
    }
    if (!(trimmed.startsWith("f ") || trimmed.startsWith("f\t"))) continue;
    const shouldSample = seenFaces % sampleStride === 0;
    seenFaces += 1;
    if (!shouldSample) continue;

    const indices = trimmed.split(/\s+/).slice(1).map((token) => {
      const raw = Number.parseInt(token.split("/")[0], 10);
      if (!Number.isInteger(raw) || raw === 0) return -1;
      return raw < 0 ? currentVertexCount + raw : raw - 1;
    });
    if (indices.length < 3 || indices.some((index) => index < 0 || index >= vertexCount)) {
      invalidFaces += 1;
      continue;
    }
    faces.push(indices);
  }

  if (!faces.length) throw new Error("Faces were found, but their vertex indices could not be resolved.");

  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (let index = 0; index < vertices.length; index += 3) {
    for (let axis = 0; axis < 3; axis += 1) {
      const value = vertices[index + axis];
      min[axis] = Math.min(min[axis], value);
      max[axis] = Math.max(max[axis], value);
    }
  }

  return {
    vertices: new Float32Array(vertices),
    faces,
    vertexCount,
    faceCount,
    sampledFaceCount: faces.length,
    malformedVertices,
    invalidFaces,
    bounds: { min, max },
  };
}

function compactNumber(value) {
  if (!Number.isFinite(value)) return "—";
  const absolute = Math.abs(value);
  if (absolute >= 10000 || (absolute > 0 && absolute < 0.001)) return value.toExponential(2);
  return Number(value.toFixed(3)).toLocaleString();
}

function scaledBounds(bounds, scale) {
  return {
    min: bounds.min.map((value) => value * scale),
    max: bounds.max.map((value) => value * scale),
  };
}

export default function MeshViewer({ file, scaleToM, waterlineZ, onReplace, onInspection }) {
  const canvasRef = useRef(null);
  const frameRef = useRef(0);
  const viewRef = useRef({ ...INITIAL_VIEW });
  const dragRef = useRef(null);
  const [geometry, setGeometry] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [activeView, setActiveView] = useState("Isometric");

  useEffect(() => {
    let cancelled = false;
    setGeometry(null);
    setError("");
    setLoading(true);
    viewRef.current = { ...INITIAL_VIEW };
    setActiveView("Isometric");

    file.text()
      .then((text) => parseObj(text))
      .then((parsed) => { if (!cancelled) setGeometry(parsed); })
      .catch((reason) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Unable to read this OBJ file."); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [file]);

  const scale = Number(scaleToM) > 0 ? Number(scaleToM) : 1;
  const rawWaterline = Number(waterlineZ) / scale;

  const inspection = useMemo(() => {
    if (loading) return { status: "loading", filename: file.name };
    if (error || !geometry) return { status: "error", filename: file.name, error };

    const bounds = scaledBounds(geometry.bounds, scale);
    const size = bounds.max.map((value, axis) => value - bounds.min[axis]);
    const originInside = bounds.min.every((value, axis) => value <= 0 && bounds.max[axis] >= 0);
    let below = 0;
    let above = 0;
    const tolerance = Math.max(...size, 1) * 1e-8;
    for (let index = 2; index < geometry.vertices.length; index += 3) {
      const z = geometry.vertices[index] * scale;
      if (z <= Number(waterlineZ) + tolerance) below += 1;
      if (z >= Number(waterlineZ) - tolerance) above += 1;
    }

    const warnings = [];
    if (!originInside) warnings.push("Global origin (0, 0, 0) is outside the mesh bounds.");
    if (!below) warnings.push("No vertices are below the waterline; the solver will have no immersed hull.");
    if (!above) warnings.push("The entire mesh is below the waterline (fully submerged geometry).");
    if (size.some((value) => value <= tolerance)) warnings.push("The mesh has zero or near-zero extent along at least one axis.");
    if (geometry.malformedVertices || geometry.invalidFaces) warnings.push("Some malformed OBJ records were skipped in the preview.");

    return {
      status: "ready",
      filename: file.name,
      vertexCount: geometry.vertexCount,
      faceCount: geometry.faceCount,
      sampledFaceCount: geometry.sampledFaceCount,
      bounds,
      size,
      originInside,
      waterlineStatus: below && above ? "Waterline intersects the mesh" : below ? "Mesh is fully below the waterline" : "Mesh is above the waterline",
      warnings,
    };
  }, [error, file.name, geometry, loading, scale, waterlineZ]);

  useEffect(() => { onInspection(inspection); }, [inspection, onInspection]);

  const drawScene = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !geometry) return;
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const pixelWidth = Math.round(rect.width * ratio);
    const pixelHeight = Math.round(rect.height * ratio);
    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
      canvas.width = pixelWidth;
      canvas.height = pixelHeight;
    }
    const context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, rect.width, rect.height);

    const meshMin = geometry.bounds.min;
    const meshMax = geometry.bounds.max;
    const fitMin = meshMin.map((value, axis) => Math.min(value, axis === 2 ? rawWaterline : 0, 0));
    const fitMax = meshMax.map((value, axis) => Math.max(value, axis === 2 ? rawWaterline : 0, 0));
    const center = fitMin.map((value, axis) => (value + fitMax[axis]) / 2);
    const extent = Math.max(...fitMax.map((value, axis) => value - fitMin[axis]), 1e-9);
    const screenScale = Math.min(rect.width, rect.height) * 0.72 * viewRef.current.zoom / extent;
    const { yaw, pitch } = viewRef.current;
    const cy = Math.cos(yaw);
    const sy = Math.sin(yaw);
    const cp = Math.cos(pitch);
    const sp = Math.sin(pitch);

    const project = (x, y, z) => {
      const px = x - center[0];
      const py = y - center[1];
      const pz = z - center[2];
      const rx = cy * px - sy * py;
      const ry = sy * px + cy * py;
      const rz = cp * pz + sp * ry;
      return [rect.width / 2 + rx * screenScale, rect.height / 2 - rz * screenScale];
    };

    const planePadding = Math.max(meshMax[0] - meshMin[0], meshMax[1] - meshMin[1], extent * 0.15) * 0.08;
    const plane = [
      [meshMin[0] - planePadding, meshMin[1] - planePadding, rawWaterline],
      [meshMax[0] + planePadding, meshMin[1] - planePadding, rawWaterline],
      [meshMax[0] + planePadding, meshMax[1] + planePadding, rawWaterline],
      [meshMin[0] - planePadding, meshMax[1] + planePadding, rawWaterline],
    ].map((point) => project(...point));
    context.beginPath();
    context.moveTo(...plane[0]);
    plane.slice(1).forEach((point) => context.lineTo(...point));
    context.closePath();
    context.fillStyle = "rgba(32, 182, 198, 0.09)";
    context.strokeStyle = "rgba(74, 213, 224, 0.72)";
    context.setLineDash([7, 6]);
    context.fill();
    context.stroke();
    context.setLineDash([]);

    context.beginPath();
    for (const face of geometry.faces) {
      const first = face[0] * 3;
      const start = project(geometry.vertices[first], geometry.vertices[first + 1], geometry.vertices[first + 2]);
      context.moveTo(...start);
      for (let faceIndex = 1; faceIndex < face.length; faceIndex += 1) {
        const vertexIndex = face[faceIndex] * 3;
        context.lineTo(...project(geometry.vertices[vertexIndex], geometry.vertices[vertexIndex + 1], geometry.vertices[vertexIndex + 2]));
      }
      context.closePath();
    }
    context.lineWidth = 0.78;
    context.strokeStyle = "rgba(119, 225, 231, 0.76)";
    context.stroke();

    const meshExtent = Math.max(...meshMax.map((value, axis) => value - meshMin[axis]), 1);
    const axisLength = Math.max(meshExtent * 0.32, extent * 0.12);
    const origin = project(0, 0, 0);
    const axes = [
      { label: "X forward", color: "#ff6868", end: project(axisLength, 0, 0) },
      { label: "Y port", color: "#72dc8a", end: project(0, axisLength, 0) },
      { label: "Z up", color: "#69a8ff", end: project(0, 0, axisLength) },
    ];
    for (const axis of axes) {
      context.beginPath();
      context.moveTo(...origin);
      context.lineTo(...axis.end);
      context.lineWidth = 2.2;
      context.strokeStyle = axis.color;
      context.stroke();
      context.fillStyle = axis.color;
      context.font = '600 11px "Segoe UI", sans-serif';
      context.fillText(axis.label, axis.end[0] + 6, axis.end[1] - 5);
    }
    context.beginPath();
    context.arc(origin[0], origin[1], 4, 0, Math.PI * 2);
    context.fillStyle = "#ffffff";
    context.fill();
    context.strokeStyle = "#052b46";
    context.lineWidth = 1.5;
    context.stroke();

    context.fillStyle = "rgba(222, 241, 247, 0.86)";
    context.font = '500 11px "Segoe UI", sans-serif';
    context.fillText(`Waterline z = ${compactNumber(Number(waterlineZ))} m`, 16, rect.height - 18);
  }, [geometry, rawWaterline, waterlineZ]);

  const requestDraw = useCallback(() => {
    window.cancelAnimationFrame(frameRef.current);
    frameRef.current = window.requestAnimationFrame(drawScene);
  }, [drawScene]);

  useEffect(() => {
    requestDraw();
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const observer = new ResizeObserver(requestDraw);
    observer.observe(canvas);
    return () => {
      observer.disconnect();
      window.cancelAnimationFrame(frameRef.current);
    };
  }, [requestDraw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const handleWheel = (event) => {
      event.preventDefault();
      viewRef.current.zoom = Math.max(0.35, Math.min(8, viewRef.current.zoom * Math.exp(-event.deltaY * 0.0012)));
      requestDraw();
    };
    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", handleWheel);
  }, [requestDraw]);

  const setView = (label, yaw, pitch) => {
    viewRef.current = { yaw, pitch, zoom: 1 };
    setActiveView(label);
    requestDraw();
  };

  const handlePointerDown = (event) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { x: event.clientX, y: event.clientY };
  };

  const handlePointerMove = (event) => {
    if (!dragRef.current) return;
    const dx = event.clientX - dragRef.current.x;
    const dy = event.clientY - dragRef.current.y;
    dragRef.current = { x: event.clientX, y: event.clientY };
    viewRef.current.yaw += dx * 0.009;
    viewRef.current.pitch = Math.max(-1.45, Math.min(1.45, viewRef.current.pitch + dy * 0.009));
    setActiveView("Custom");
    requestDraw();
  };

  return (
    <section className="mesh-viewer-card" aria-label="Uploaded mesh inspection">
      <header className="mesh-viewer-toolbar">
        <div className="mesh-file-title">
          <Box size={18} />
          <span><strong>{file.name}</strong><small>{formatBytes(file.size)} · parsed locally</small></span>
        </div>
        <div className="mesh-view-actions" aria-label="Mesh view orientation">
          {[
            ["Isometric", -0.72, 0.48],
            ["Front", 0, 0],
            ["Side", Math.PI / 2, 0],
            ["Top", 0, Math.PI / 2],
          ].map(([label, yaw, pitch]) => (
            <button key={label} className={activeView === label ? "active" : ""} type="button" onClick={() => setView(label, yaw, pitch)}>{label}</button>
          ))}
          <button type="button" onClick={onReplace}>Replace OBJ</button>
        </div>
      </header>
      <div className="mesh-canvas-wrap">
        <canvas
          ref={canvasRef}
          aria-label={`Interactive 3D preview of ${file.name}`}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={() => { dragRef.current = null; }}
          onPointerCancel={() => { dragRef.current = null; }}
          onDoubleClick={() => setView("Isometric", INITIAL_VIEW.yaw, INITIAL_VIEW.pitch)}
        />
        {loading ? <div className="mesh-viewer-overlay"><Rotate3D className="spin" size={25} /><strong>Reading OBJ geometry…</strong></div> : null}
        {error ? <div className="mesh-viewer-overlay error"><strong>Preview unavailable</strong><span>{error}</span></div> : null}
        {!loading && !error ? <div className="mesh-interaction-hint"><Rotate3D size={14} /> Drag to rotate · wheel to zoom · double-click to reset</div> : null}
      </div>
      {inspection.status === "ready" ? (
        <footer className="mesh-stats">
          <span><strong>{inspection.vertexCount.toLocaleString()}</strong> vertices</span>
          <span><strong>{inspection.faceCount.toLocaleString()}</strong> faces</span>
          {inspection.size.map((value, axis) => <span key={axis}><strong>{["X", "Y", "Z"][axis]}</strong> {compactNumber(value)} m</span>)}
          <span className={inspection.originInside ? "ok" : "warn"}><Crosshair size={14} /> {inspection.originInside ? "Origin inside bounds" : "Origin outside bounds"}</span>
        </footer>
      ) : null}
    </section>
  );
}
