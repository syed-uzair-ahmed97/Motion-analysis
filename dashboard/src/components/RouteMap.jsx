import worldText from "../assets/world-110m.geojson?raw";

const WORLD = JSON.parse(worldText);
const WIDTH = 960;
const HEIGHT = 480;
const project = ([longitude, latitude]) => [((Number(longitude) + 180) / 360) * WIDTH, ((90 - Number(latitude)) / 180) * HEIGHT];
const polygonPath = (ring) => ring.map((point, index) => `${index ? "L" : "M"}${project(point).join(" ")}`).join(" ") + "Z";

function featurePath(feature) {
  const { type, coordinates } = feature.geometry || {};
  if (type === "Polygon") return coordinates.map(polygonPath).join(" ");
  if (type === "MultiPolygon") return coordinates.flatMap((polygon) => polygon.map(polygonPath)).join(" ");
  return "";
}

function routeSegments(coordinates) {
  const segments = [];
  let current = [];
  coordinates.forEach((point, index) => {
    if (index && Math.abs(Number(point[0]) - Number(coordinates[index - 1][0])) > 180) {
      if (current.length > 1) segments.push(current);
      current = [];
    }
    current.push(project(point));
  });
  if (current.length > 1) segments.push(current);
  return segments;
}

export default function RouteMap({ coordinates = [], gridPoints = [], stopover = null }) {
  const segments = routeSegments(coordinates);
  const origin = coordinates.length ? project(coordinates[0]) : null;
  const destination = coordinates.length ? project(coordinates[coordinates.length - 1]) : null;
  const stop = stopover ? project([stopover.longitude, stopover.latitude]) : null;
  return (
    <figure className="route-map world-route-map">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Global maritime route and matched ERA5 grid cells">
        <title>Global maritime route and matched ERA5 grid cells</title>
        <rect width={WIDTH} height={HEIGHT} className="world-ocean" />
        {[-60, -30, 0, 30, 60].map((latitude) => { const [, y] = project([0, latitude]); return <line key={`lat-${latitude}`} x1="0" y1={y} x2={WIDTH} y2={y} className="world-graticule" />; })}
        {[-120, -60, 0, 60, 120].map((longitude) => { const [x] = project([longitude, 0]); return <line key={`lon-${longitude}`} x1={x} y1="0" x2={x} y2={HEIGHT} className="world-graticule" />; })}
        <g className="world-land">{WORLD.features.map((feature, index) => <path key={feature.properties?.ADM0_A3 || index} d={featurePath(feature)} />)}</g>
        {segments.map((segment, index) => <polyline key={index} points={segment.map((point) => point.join(",")).join(" ")} className="route-line" />)}
        {gridPoints.map((point, index) => { const [x, y] = project([point.longitude, point.latitude]); const radius = 3 + Math.min(6, Number(point.weight_percent || 0) / 8); return <circle key={`${point.latitude}-${point.longitude}-${index}`} cx={x} cy={y} r={radius} className="route-grid-point" />; })}
        {origin ? <circle cx={origin[0]} cy={origin[1]} r="7" className="route-terminal origin" /> : null}
        {stop ? <circle cx={stop[0]} cy={stop[1]} r="7" className="route-terminal stopover" /> : null}
        {destination ? <circle cx={destination[0]} cy={destination[1]} r="7" className="route-terminal destination" /> : null}
      </svg>
      <figcaption><span><i className="route-key route-key-line" />SeaRoute path</span><span><i className="route-key route-key-point" />Matched ERA5 cell</span><small>Natural Earth public-domain basemap · route is not for navigation</small></figcaption>
    </figure>
  );
}
