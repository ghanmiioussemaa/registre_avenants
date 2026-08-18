import React from "react";

export default function StampBadge({ ok, okLabel = "Conforme", koLabel = "Rejeté" }) {
  return <span className={`stamp ${ok ? "ok" : "ko"}`}>{ok ? okLabel : koLabel}</span>;
}
