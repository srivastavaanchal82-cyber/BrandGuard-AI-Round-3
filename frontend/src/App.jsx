import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard.jsx";import BrandDNA from "./pages/BrandDNA.jsx";import Prevent from "./pages/Prevent.jsx";import Results from "./pages/Results.jsx";
import Protect from "./pages/Protect.jsx";import Campaign from "./pages/Campaign.jsx";import History from "./pages/History.jsx";import Settings from "./pages/Settings.jsx";
const NAV = [["/", "▦", "Dashboard"], ["/brand", "◈", "Brand DNA"], ["/prevent", "✎", "Prevent"], ["/results", "☑", "Analysis Results"], ["/protect", "◉", "Protect"], ["/campaign", "⚑", "Campaign DNA"], ["/history", "↺", "Review History"], ["/settings", "⚙", "Settings"]];
export default function App() {
  return <div className="flex min-h-screen flex-col md:flex-row">
    <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded-lg focus:bg-brand focus:px-3 focus:py-2 focus:text-white">Skip to content</a>
    <aside className="border-line bg-[#0a1030] p-3 md:sticky md:top-0 md:h-screen md:w-56 md:shrink-0 md:border-r md:p-4">
      <div className="mb-3 flex items-center gap-2 px-2 text-lg font-extrabold md:mb-5">🛡️ <span className="bg-gradient-to-r from-brand to-sky2 bg-clip-text text-transparent">BrandGuard AI</span></div>
      <nav aria-label="Main" className="flex gap-1 overflow-x-auto pb-1 md:flex-col md:overflow-visible md:pb-0">{NAV.map(([to, i, l]) => <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => `flex gap-2 whitespace-nowrap rounded-xl px-3 py-2 text-sm ${isActive ? "bg-gradient-to-r from-brand/70 to-sky2/60 text-white" : "text-mu hover:bg-[#1a2250]"}`}><span aria-hidden>{i}</span>{l}</NavLink>)}</nav>
    </aside>
    <main id="main" className="min-w-0 max-w-5xl flex-1 p-4 md:p-7"><Routes>
      <Route path="/" element={<Dashboard />} /><Route path="/brand" element={<BrandDNA />} /><Route path="/prevent" element={<Prevent />} /><Route path="/results" element={<Results />} />
      <Route path="/protect" element={<Protect />} /><Route path="/campaign" element={<Campaign />} /><Route path="/history" element={<History />} /><Route path="/settings" element={<Settings />} />
      <Route path="*" element={<p className="text-mu">Page not found.</p>} /></Routes></main></div>;
}
