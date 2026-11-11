import { useCallback, useState } from "react";
import HydrodynamicsWorkspace from "./components/HydrodynamicsWorkspace";
import OverviewWorkspace from "./components/OverviewWorkspace";
import ProductShell from "./components/ProductShell";
import ResponseWorkspace from "./components/ResponseWorkspace";
import SeaStateWorkspace from "./components/SeaStateWorkspace";

export default function App() {
  const [activeModule, setActiveModule] = useState("overview");
  const [selectedSeaState, setSelectedSeaState] = useState(null);
  const [hydrodynamicJob, setHydrodynamicJob] = useState(null);

  const handleHydrodynamicJob = useCallback((job) => setHydrodynamicJob(job), []);
  const useHydrodynamicJob = useCallback((job) => {
    setHydrodynamicJob(job);
    setActiveModule("response");
  }, []);

  let workspace = <OverviewWorkspace seaState={selectedSeaState} hydrodynamicJob={hydrodynamicJob} onNavigate={setActiveModule} />;
  if (activeModule === "sea-states") workspace = <SeaStateWorkspace selectedSeaState={selectedSeaState} onSelectSeaState={setSelectedSeaState} onOpenResponse={() => setActiveModule("response")} />;
  if (activeModule === "hydrodynamics") workspace = <HydrodynamicsWorkspace onJobChange={handleHydrodynamicJob} onUseInResponse={useHydrodynamicJob} />;
  if (activeModule === "response") workspace = <ResponseWorkspace selectedSeaState={selectedSeaState} hydrodynamicJob={hydrodynamicJob} onOpenHydrodynamics={() => setActiveModule("hydrodynamics")} />;

  return <ProductShell activeModule={activeModule} onSelectModule={setActiveModule}>{workspace}</ProductShell>;
}
