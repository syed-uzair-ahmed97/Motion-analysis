function colorFor(value, maximum) {
  if (!(value > 0) || !(maximum > 0)) return "#fbfdff";
  const ratio = Math.min(1, Math.sqrt(value / maximum));
  const lightness = 97 - ratio * 53;
  const saturation = 35 + ratio * 36;
  return `hsl(188 ${saturation}% ${lightness}%)`;
}

function label(low, high) {
  return `${Number(low.toFixed(2))}–${Number(high.toFixed(2))}`;
}

export default function ScatterHeatmap({ result, mode, selected, onSelect }) {
  const matrix = mode === "count" ? result.counts : result.probabilities;
  const flattened = matrix.flat();
  const maximum = Math.max(...flattened, 0);
  const columns = result.tp_edges.length - 1;
  const rows = result.hs_edges.length - 1;
  const rowIndexes = Array.from({ length: rows }, (_, index) => rows - index - 1);
  return (
    <div className="heatmap-scroll" role="region" aria-label="Hs and Tp scatter diagram">
      <div className="heatmap-with-axis">
        <span className="heatmap-y-title">Significant wave height, Hs [m]</span>
        <div className="heatmap-grid" style={{ gridTemplateColumns: `82px repeat(${columns}, minmax(43px, 1fr))` }}>
          {rowIndexes.map((hsIndex) => (
            <div className="heatmap-row" style={{ gridColumn: `1 / span ${columns + 1}`, gridTemplateColumns: `82px repeat(${columns}, minmax(43px, 1fr))` }} key={hsIndex}>
              <span className="heatmap-row-label">{label(result.hs_edges[hsIndex], result.hs_edges[hsIndex + 1])}</span>
              {Array.from({ length: columns }, (_, tpIndex) => {
                const value = matrix[hsIndex][tpIndex];
                const active = selected?.hs_index === hsIndex && selected?.tp_index === tpIndex;
                return (
                  <button
                    key={`${hsIndex}-${tpIndex}`}
                    type="button"
                    className={`heatmap-cell${active ? " selected" : ""}${value > 0 ? " populated" : ""}`}
                    style={{ background: colorFor(value, maximum), color: value / (maximum || 1) > 0.5 ? "#fff" : "#173149" }}
                    onClick={() => value > 0 && onSelect({
                      hs_index: hsIndex,
                      tp_index: tpIndex,
                      hs_low: result.hs_edges[hsIndex],
                      hs_high: result.hs_edges[hsIndex + 1],
                      tp_low: result.tp_edges[tpIndex],
                      tp_high: result.tp_edges[tpIndex + 1],
                      hs: (result.hs_edges[hsIndex] + result.hs_edges[hsIndex + 1]) / 2,
                      tp: (result.tp_edges[tpIndex] + result.tp_edges[tpIndex + 1]) / 2,
                      count: result.counts[hsIndex][tpIndex],
                      probability: result.probabilities[hsIndex][tpIndex],
                    })}
                    aria-label={`Hs ${label(result.hs_edges[hsIndex], result.hs_edges[hsIndex + 1])} metres, Tp ${label(result.tp_edges[tpIndex], result.tp_edges[tpIndex + 1])} seconds, ${mode === "count" ? `${value} observations` : `${value.toFixed(3)} percent`}`}
                    disabled={value <= 0}
                  >
                    {mode === "count" ? value.toLocaleString() : value >= 0.005 ? value.toFixed(value >= 10 ? 1 : 2) : "0%"}
                  </button>
                );
              })}
            </div>
          ))}
          <span />
          {Array.from({ length: columns }, (_, index) => <span className="heatmap-column-label" key={index}>{label(result.tp_edges[index], result.tp_edges[index + 1])}</span>)}
        </div>
        <span className="heatmap-x-title">Peak period, Tp [s]</span>
      </div>
    </div>
  );
}
