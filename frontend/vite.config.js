import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// In development, /api calls are forwarded to the FastAPI backend (no CORS problems).
export default defineConfig({ plugins: [react()], server: { port: 5173, proxy: { "/api": process.env.VITE_BACKEND || "http://127.0.0.1:8000" } } });
