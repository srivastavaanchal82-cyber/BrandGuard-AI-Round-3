import { createContext, useContext, useState } from "react";
const C = createContext();
export const useApp = () => useContext(C);
export function AppProvider({ children }) {
  const [last, setL] = useState(() => { try { return JSON.parse(sessionStorage.getItem("bg_last")); } catch { return null; } });
  const [draft, setDraft] = useState("");
  const setLast = (v) => { setL(v); try { sessionStorage.setItem("bg_last", JSON.stringify(v)); } catch {} };
  return <C.Provider value={{ last, setLast, draft, setDraft }}>{children}</C.Provider>;
}
