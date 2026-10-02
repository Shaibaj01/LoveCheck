"use client";

import { useEffect, useRef, useState } from "react";
import { apiUrl, clipUrl, type AlertItem, type Camera } from "@/lib/api";

function fmtTime(sec: number): string {
  const s = Math.max(0, Math.floor(Number(sec) || 0));
  const m = Math.floor(s / 60);
  const r = String(s % 60).padStart(2, "0");
  return `${m}:${r}`;
}

export function Board() {
  const [team, setTeam] = useState("team");
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[] | null>(null);
  const [activeAlert, setActiveAlert] = useState<string | null>(null);
  const [error, setError] = useState("");
  const videos = useRef<Record<string, HTMLVideoElement | null>>({});

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const h = await fetch(apiUrl("/api/health")).then((r) => r.json());
        if (!cancelled) {
          setTeam(h.team || "team");
          setHealthy(true);
        }
      } catch {
        if (!cancelled) setHealthy(false);
      }
      try {
        const cams = await fetch(apiUrl("/api/cameras")).then((r) => r.json());
        if (!cancelled) {
          setTeam(cams.team || "team");
          setHealthy(!!cams.healthy);
          setCameras(cams.cameras || []);
        }
      } catch {
        if (!cancelled) {
          setHealthy(false);
          setError("Could not load cameras.");
        }
      }
      try {
        const data = await fetch(apiUrl("/api/alerts")).then((r) => r.json());
        if (!cancelled) setAlerts(data.alerts || []);
      } catch {
        if (!cancelled) setAlerts([]);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  function playOnCard(cardId: string, source: string, startSec: number) {
    const v = videos.current[cardId];
    if (!v) return;
    v.hidden = false;
    const empty = v.parentElement?.querySelector(".empty");
    if (empty) (empty as HTMLElement).style.display = "none";
    const url = clipUrl(source);
    const seek = () => {
      if (startSec > 0 && startSec < (v.duration || startSec + 1)) {
        v.currentTime = startSec;
      }
      v.play().catch(() => undefined);
    };
    if (v.getAttribute("src") === url) {
      seek();
      return;
    }
    v.src = url;
    v.addEventListener("loadedmetadata", seek, { once: true });
  }

  return (
    <>
      <header>
        <div className="brand">Home Watch</div>
        <div className="meta">
          <span className="pill">{team}</span>
          <span className="pill">
            <span className={`dot ${healthy ? "ok" : "bad"}`} />
            <span>
              {healthy === null ? "checking" : healthy ? "healthy" : "degraded"}
            </span>
          </span>
        </div>
      </header>
      <section className="grid">
        {error ? <div className="status">{error}</div> : null}
        {cameras.map((cam) => (
          <article className="card" key={cam.id}>
            <h2>
              <span>{cam.label}</span>
              <span className="id">{cam.camera_id}</span>
            </h2>
            {cam.source ? (
              <video
                ref={(el) => {
                  videos.current[cam.id] = el;
                }}
                muted
                controls
                playsInline
                preload="metadata"
                src={clipUrl(cam.source)}
                onLoadedMetadata={(e) => {
                  const v = e.currentTarget;
                  const t = cam.start_sec || 0;
                  if (t > 0 && t < (v.duration || t + 1)) v.currentTime = t;
                }}
              />
            ) : (
              <>
                <div className="empty">No indexed clip</div>
                <video
                  ref={(el) => {
                    videos.current[cam.id] = el;
                  }}
                  muted
                  controls
                  playsInline
                  preload="metadata"
                  hidden
                />
              </>
            )}
          </article>
        ))}
      </section>
      <section className="feed">
        <h3>Needs attention</h3>
        {alerts === null ? (
          <div className="status">Loading alerts…</div>
        ) : alerts.length === 0 ? (
          <div className="status">No attention items from house or dashcam search.</div>
        ) : (
          alerts.map((a) => (
            <button
              type="button"
              key={a.id}
              className={`alert${activeAlert === a.id ? " active" : ""}`}
              onClick={() => {
                setActiveAlert(a.id);
                playOnCard(a.card_id, a.source, a.start_sec);
              }}
            >
              <div className={`tag ${a.kind}`}>{a.label}</div>
              <div className="sum">{a.summary}</div>
              <div className="when">{fmtTime(a.start_sec)} · clip</div>
            </button>
          ))
        )}
      </section>
    </>
  );
}
