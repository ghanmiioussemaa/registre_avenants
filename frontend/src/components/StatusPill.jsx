import React from "react";
import { statusLabel } from "../useAgentStatus.js";

export default function StatusPill({ state }) {
  return <span className={`status-pill ${state}`}>{statusLabel(state)}</span>;
}
