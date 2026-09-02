import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createHashRouter, RouterProvider } from "react-router-dom";
import { AppShell, ErrorBoundary } from "./App";
import Overview from "./views/Overview";
import Incidents from "./views/Incidents";
import IncidentDetail from "./views/IncidentDetail";
import Services from "./views/Services";
import Topology from "./views/Topology";
import Logs from "./views/Logs";
import Metrics from "./views/Metrics";
import Deployments from "./views/Deployments";
import Investigator from "./views/Investigator";
import Postmortems from "./views/Postmortems";
import Evaluations from "./views/Evaluations";
import Settings from "./views/Settings";
import "./styles.css";

const router = createHashRouter([
  {
    path: "/",
    element: <AppShell />,
    errorElement: <ErrorBoundary />,
    children: [
      { index: true, element: <Overview /> },
      { path: "overview", element: <Overview /> },
      { path: "incidents", element: <Incidents /> },
      { path: "incidents/:id", element: <IncidentDetailWrapper /> },
      { path: "services", element: <Services /> },
      { path: "topology", element: <Topology /> },
      { path: "logs", element: <Logs /> },
      { path: "metrics", element: <Metrics /> },
      { path: "deployments", element: <Deployments /> },
      { path: "investigator", element: <Investigator /> },
      { path: "postmortems", element: <Postmortems /> },
      { path: "evaluations", element: <Evaluations /> },
      { path: "settings", element: <Settings /> },
    ],
  },
]);

function IncidentDetailWrapper() {
  const { id } = useParamsOrThrow();
  return <IncidentDetail incidentId={id} />;
}

import { useParams } from "react-router-dom";
function useParamsOrThrow(): { id: string } {
  const params = useParams();
  if (!params.id) throw new Error("incident id missing");
  return params as { id: string };
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
