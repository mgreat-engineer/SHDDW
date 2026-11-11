import axios from "axios";
import { useMemo } from "react";
import { useAuth } from "@clerk/react";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

let currentGroup = new URLSearchParams(window.location.search).get("group") || "1";
export const getGroup = () => currentGroup;
export const setGroup = (g) => { currentGroup = String(g); };

export function useApi() {
  const { getToken } = useAuth();
  return useMemo(() => {
    const c = axios.create({ baseURL: API });
    c.interceptors.request.use(async (cfg) => {
      const t = await getToken();
      if (t) cfg.headers.Authorization = `Bearer ${t}`;
      cfg.params = { group: currentGroup, ...(cfg.params || {}) };
      return cfg;
    });
    return c;
  }, [getToken]);
}

export const errMsg = (e) => e?.response?.data?.detail || e?.message || "Something went wrong";

export const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "");

export const fmtSize = (n) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : n > 1024 ? `${Math.round(n / 1024)} KB` : `${n || 0} B`);

export async function saveBlob(api, url, name) {
  const r = await api.get(url, { responseType: "blob" });
  const href = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(href), 2000);
}
