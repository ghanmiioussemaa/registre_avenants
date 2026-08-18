import React, { createContext, useCallback, useContext, useState } from "react";

const FlashContext = createContext(null);

let nextId = 1;

export function FlashProvider({ children }) {
  const [messages, setMessages] = useState([]);

  const flash = useCallback((message, category = "success") => {
    const id = nextId++;
    setMessages((prev) => [...prev, { id, message, category }]);
    setTimeout(() => {
      setMessages((prev) => prev.filter((m) => m.id !== id));
    }, 5000);
  }, []);

  const dismiss = useCallback((id) => {
    setMessages((prev) => prev.filter((m) => m.id !== id));
  }, []);

  return (
    <FlashContext.Provider value={{ messages, flash, dismiss }}>
      {children}
    </FlashContext.Provider>
  );
}

export function useFlash() {
  const ctx = useContext(FlashContext);
  if (!ctx) throw new Error("useFlash doit être utilisé dans un FlashProvider");
  return ctx.flash;
}

export function useFlashMessages() {
  const ctx = useContext(FlashContext);
  if (!ctx) throw new Error("useFlashMessages doit être utilisé dans un FlashProvider");
  return ctx;
}
