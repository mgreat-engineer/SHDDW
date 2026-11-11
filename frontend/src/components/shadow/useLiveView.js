import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/react";
import { API, getGroup } from "@/lib/api";

// Live view: Chrome screencast over a WebSocket (video-like). Falls back to picture polling (e.g. laptop helper).
export function useLiveView(api, onError) {
  const { getToken } = useAuth();
  const [src, setSrc] = useState(null);
  const [live, setLive] = useState(false);
  const wsRef = useRef(null);
  const sizeRef = useRef(null);
  const errRef = useRef(onError);
  errRef.current = onError;

  useEffect(() => {
    let alive = true, prev = null, timer, retry, ws, polling = false, streaming = false, fails = 0;
    const show = (blob) => {
      const u = URL.createObjectURL(blob);
      if (!alive) return URL.revokeObjectURL(u);
      setSrc(u); if (prev) URL.revokeObjectURL(prev); prev = u;
    };
    const poll = async () => {
      if (!streaming && !document.hidden) {
        try { show((await api.get("/browser/frame", { responseType: "blob" })).data); } catch {}
      }
      if (alive) timer = setTimeout(poll, 400);
    };
    const startPolling = () => { if (!polling) { polling = true; poll(); } };
    const connect = async () => {
      let t = "";
      try { t = await getToken(); } catch {}
      if (!alive) return;
      ws = new WebSocket(`${API.replace(/^http/, "ws")}/browser/stream?token=${encodeURIComponent(t || "")}&group=${getGroup()}`);
      ws.binaryType = "blob";
      wsRef.current = ws;
      ws.onopen = () => { if (sizeRef.current) ws.send(JSON.stringify({ type: "resize", ...sizeRef.current })); };
      ws.onmessage = (e) => {
        if (typeof e.data === "string") {
          const m = JSON.parse(e.data);
          if (m.type === "fallback") { ws.onclose = null; wsRef.current = null; startPolling(); }
          else if (m.type === "error") errRef.current?.(m.detail);
          return;
        }
        if (!streaming) { streaming = true; fails = 0; setLive(true); }
        show(e.data);
      };
      ws.onclose = () => {
        wsRef.current = null; streaming = false; setLive(false);
        if (++fails >= 2) startPolling();
        if (alive) retry = setTimeout(connect, Math.min(1000 * fails, 8000));
      };
    };
    connect();
    return () => {
      alive = false; clearTimeout(timer); clearTimeout(retry);
      if (ws) { ws.onclose = null; ws.close(); }
      if (prev) URL.revokeObjectURL(prev);
    };
  }, [api, getToken]);

  const sendInput = (body) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === 1) { ws.send(JSON.stringify({ type: "input", ...body })); return true; }
    return false;
  };
  const resize = (width, height) => {
    sizeRef.current = { width, height };
    const ws = wsRef.current;
    if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: "resize", width, height }));
  };
  return { src, live, sendInput, resize };
}
