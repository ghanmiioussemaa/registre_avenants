import React from "react";
import { useFlashMessages } from "../FlashContext.jsx";

export default function FlashMessages() {
  const { messages, dismiss } = useFlashMessages();
  if (messages.length === 0) return null;

  return (
    <>
      {messages.map((m) => (
        <div key={m.id} className={`flash ${m.category}`} onClick={() => dismiss(m.id)}>
          {m.message}
        </div>
      ))}
    </>
  );
}
