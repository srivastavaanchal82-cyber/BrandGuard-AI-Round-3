import axios from "axios";
export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || "", timeout: 40000 });
export const BRAND_ID = "default";
export const API_BASE = import.meta.env.VITE_API_URL || "";
export function errMsg(e) {
  if (e?.code === "ERR_CANCELED") return "Cancelled.";
  const st = e?.response?.status, d = e?.response?.data?.detail;
  if (d) return typeof d === "string" ? d : d.map?.((x) => x.msg).join("; ") || JSON.stringify(d);
  // A proxy error (Render 502/503/504) returns HTML, not JSON, so there is no `detail`: explain it instead of showing nothing.
  if (st === 502 || st === 503 || st === 504) return `The server is unavailable (HTTP ${st}). It may be waking up from sleep or restarting after running out of memory. Wait about a minute and try again, or use a smaller image.`;
  if (e?.code === "ECONNABORTED" || /timeout/i.test(e?.message || "")) return "The request took too long and was stopped. The server may be waking up (free hosting sleeps when idle). Please try again.";
  if (e?.code === "ERR_NETWORK" || e?.message === "Network Error")
    return API_BASE ? `Cannot reach the backend at ${API_BASE}. It may be starting up (wait a minute and retry), have crashed (check the Render logs), or be blocking this site (add this site's URL to CORS_ORIGINS).`
      : "Cannot reach the backend. Make sure it is running on port 8000.";
  return e?.message || "Something went wrong.";
}
export const saveBrand = (b) => api.put(`/api/brand/${BRAND_ID}`, b).then((r) => r.data);
export const getBrand = () => api.get(`/api/brand/${BRAND_ID}`).then((r) => r.data);
export const analyse = (text) => api.post("/api/prevent/analyse", { text, brand_id: BRAND_ID }).then((r) => r.data);
export const compare = (c) => api.post("/api/protect/campaign-compare", c).then((r) => r.data);
export const review = (analysis_id, decision, review_type) => api.post("/api/reviews", { analysis_id, decision, review_type }).then((r) => r.data);
export const getReviews = () => api.get("/api/reviews").then((r) => r.data);
export const getStats = () => api.get("/api/stats").then((r) => r.data);
export const getHealth = () => api.get("/api/health").then((r) => r.data);
// opts.signal (AbortController) lets the UI cancel. The timeout guarantees the request can never load forever.
export const analyseImage = (file, approved_discount, approved_website, opts = {}) => {
  const f = new FormData(); f.append("file", file); f.append("approved_discount", approved_discount); f.append("approved_website", approved_website); f.append("brand_id", BRAND_ID);
  return api.post("/api/protect/analyse-image", f, { timeout: 120000, signal: opts.signal }).then((r) => r.data);
};
export const getLogos = () => api.get(`/api/brand/${BRAND_ID}/logos`).then((r) => r.data);
export const addLogo = (file, name) => { const f = new FormData(); f.append("file", file); f.append("name", name || ""); return api.post(`/api/brand/${BRAND_ID}/logos`, f, { timeout: 60000 }).then((r) => r.data); };
export const deleteLogo = (id) => api.delete(`/api/brand/${BRAND_ID}/logos/${id}`).then((r) => r.data);
