import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { LeadMagnet } from "./proposal/LeadMagnet";
import type { ProposalData } from "./proposal/types";
import "./styles.css";

const payload = document.getElementById("lead-magnet-data")?.textContent;
if (!payload || payload.startsWith("__LEAD_")) {
  throw new Error("The lead magnet template needs report data.");
}

const data = JSON.parse(payload) as ProposalData;
createRoot(document.getElementById("root")!).render(
  <StrictMode><LeadMagnet data={data} /></StrictMode>,
);
