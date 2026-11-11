import { useMemo } from "react";

function finiteExtent(values, fallback = [0, 1]) {
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return fallback;
  const minimum = Math.min(...finite);
  const maximum = Math.max(...finite);
  return minimum === maximum ? [minimum, minimum + 1] : [minimum, maximum];
}

function tickLabel(value, logScale = false) {
  if (logScale) return `1e${Math.round(value)}`;
  if (Math.abs(value) >= 1000 || (Math.abs(value) > 0 && Math.abs(value) < 0.01)) return value.toExponential(1);
  return Number(value.toFixed(value < 10 ? 2 : 1)).toString();
}

export default function ScientificLineChart({ title, x, series, xLabel, yLabel, logY = false, compact = false }) {
  const geometry = useMemo(() => {
    const width = compact ? 430 : 820;
    const height = compact ? 220 : 410;
    const margin = compact ? { left: 52, right: 18, top: 18, bottom: 38 } : { left: 72, right: 28, top: 22, bottom: 55 };
    const xValues = (x || []).map(Number);
    const [xMin, xMax] = finiteExtent(xValues);
    const allY = series.flatMap((item) => item.values || []).map(Number).filter((value) => Number.isFinite(value) && value >= 0);
    const positive = allY.filter((value) => value > 0);
    const rawMin = logY ? Math.log10(Math.min(...(positive.length ? positive : [1e-8]))) : Math.min(...(allY.length ? allY : [0]));
    const rawMax = logY ? Math.log10(Math.max(...(positive.length ? positive : [1]))) : Math.max(...(allY.length ? allY : [1]));
    const yMin = logY ? Math.floor(rawMin) : Math.min(0, rawMin);
    const yMax = logY ? Math.ceil(rawMax) : rawMax === yMin ? yMin + 1 : rawMax * 1.06;
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const xScale = (value) => margin.left + ((value - xMin) / (xMax - xMin || 1)) * plotWidth;
    const yScale = (value) => {
      const transformed = logY ? Math.log10(Math.max(value, 10 ** yMin)) : value;
      return margin.top + (1 - (transformed - yMin) / (yMax - yMin || 1)) * plotHeight;
    };
    const order = xValues.map((value, index) => ({ value, index })).filter((item) => Number.isFinite(item.value)).sort((a, b) => a.value - b.value);
    const paths = series.map((item) => {
      let started = false;
      const path = order.map(({ value, index }) => {
        const yValue = Number(item.values?.[index]);
        if (!Number.isFinite(yValue) || (logY && yValue <= 0)) return null;
        const command = started ? "L" : "M";
        started = true;
        return `${command}${xScale(value).toFixed(2)},${yScale(yValue).toFixed(2)}`;
      }).filter(Boolean).join(" ");
      return { ...item, path };
    });
    const xTicks = Array.from({ length: 6 }, (_, index) => xMin + (index / 5) * (xMax - xMin));
    const yTicks = Array.from({ length: 5 }, (_, index) => yMin + (index / 4) * (yMax - yMin));
    return { width, height, margin, plotWidth, plotHeight, xScale, yScale, paths, xTicks, yTicks, logY };
  }, [x, series, logY, compact]);

  return (
    <div className={`scientific-chart${compact ? " compact" : ""}`}>
      {title ? <h3>{title}</h3> : null}
      <div className="scientific-chart-body">
        <svg viewBox={`0 0 ${geometry.width} ${geometry.height}`} role="img" aria-label={title || yLabel}>
          <rect x={geometry.margin.left} y={geometry.margin.top} width={geometry.plotWidth} height={geometry.plotHeight} className="chart-field" />
          {geometry.yTicks.map((tick) => (
            <g key={`y-${tick}`}>
              <line x1={geometry.margin.left} x2={geometry.margin.left + geometry.plotWidth} y1={geometry.yScale(geometry.logY ? 10 ** tick : tick)} y2={geometry.yScale(geometry.logY ? 10 ** tick : tick)} className="chart-gridline" />
              <text x={geometry.margin.left - 9} y={geometry.yScale(geometry.logY ? 10 ** tick : tick) + 4} textAnchor="end" className="chart-tick">{tickLabel(tick, geometry.logY)}</text>
            </g>
          ))}
          {geometry.xTicks.map((tick) => (
            <g key={`x-${tick}`}>
              <line x1={geometry.xScale(tick)} x2={geometry.xScale(tick)} y1={geometry.margin.top} y2={geometry.margin.top + geometry.plotHeight} className="chart-gridline" />
              <text x={geometry.xScale(tick)} y={geometry.margin.top + geometry.plotHeight + 20} textAnchor="middle" className="chart-tick">{tickLabel(tick)}</text>
            </g>
          ))}
          {geometry.paths.map((item) => <path key={item.key || item.label} d={item.path} fill="none" stroke={item.color} strokeWidth={compact ? 2 : 2.4} vectorEffect="non-scaling-stroke" />)}
          <text x={geometry.margin.left + geometry.plotWidth / 2} y={geometry.height - 10} textAnchor="middle" className="chart-axis-label">{xLabel}</text>
          <text transform={`translate(16 ${geometry.margin.top + geometry.plotHeight / 2}) rotate(-90)`} textAnchor="middle" className="chart-axis-label">{yLabel}</text>
        </svg>
        <div className="chart-legend">
          {series.map((item) => <span key={item.key || item.label}><i style={{ background: item.color }} />{item.label}</span>)}
        </div>
      </div>
    </div>
  );
}
