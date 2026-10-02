"use client";

import { useEffect, useRef, useState } from "react";
import { CarFront, Home, Video } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
  clipUrl,
  withWindow,
  type AlertItem,
  type Camera,
  type FeedSummary,
  type TimeFilter,
} from "@/lib/api";

const WINDOWS: { id: TimeFilter; label: string }[] = [
  { id: "1h", label: "1h" },
  { id: "24h", label: "24h" },
  { id: "7d", label: "7d" },
  { id: "all", label: "All" },
];

const CAM_META: Record<string, { icon: typeof Home; blurb: string }> = {
  indoor: { icon: Video, blurb: "Ceiling — display only" },
  dashcam: { icon: CarFront, blurb: "In the car" },
  house: { icon: Home, blurb: "Outside the house" },
};

function fmtTime(sec: number): string {
  const s = Math.max(0, Math.floor(Number(sec) || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function kindVariant(kind: string): "house" | "car" | "indoor" | "default" {
  if (kind === "house") return "house";
  if (kind === "car") return "car";
  if (kind === "indoor") return "indoor";
  return "default";
}

export function Board() {
  const [team, setTeam] = useState("team");
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[] | null>(null);
  const [summaries, setSummaries] = useState<FeedSummary[]>([]);
  const [selectedId, setSelectedId] = useState("house");
  const [activeAlert, setActiveAlert] = useState<string | null>(null);
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("7d");
  const [date, setDate] = useState("");
  const [error, setError] = useState("");
  const [player, setPlayer] = useState<{ source: string; start: number } | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const selected = cameras.find((c) => c.id === selectedId) || cameras[0];

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setAlerts(null);
      setError("");
      setPlayer(null);
      try {
        const cams = await fetch(withWindow("/api/cameras", timeFilter, date)).then((r) => r.json());
        if (cancelled) return;
        setTeam(cams.team || "team");
        setHealthy(!!cams.healthy);
        const list: Camera[] = cams.cameras || [];
        setCameras(list);
        const first = list.find((c) => c.id === "house") || list[0];
        setPlayer((cur) => {
          if (cur) return cur;
          if (first?.source) return { source: first.source, start: first.start_sec || 0 };
          return cur;
        });
      } catch {
        if (!cancelled) {
          setHealthy(false);
          setError("Could not load cameras.");
        }
      }
      try {
        const data = await fetch(withWindow("/api/alerts", timeFilter, date)).then((r) => r.json());
        if (cancelled) return;
        setAlerts(data.alerts || []);
        setSummaries(data.summaries || []);
      } catch {
        if (!cancelled) {
          setAlerts([]);
          setSummaries([]);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [timeFilter, date]);

  function playClip(source: string, startSec: number) {
    if (!source) return;
    setPlayer({ source, start: startSec });
  }

  function selectCamera(id: string, playDefault = true) {
    setSelectedId(id);
    setActiveAlert(null);
    const cam = cameras.find((c) => c.id === id);
    if (playDefault && cam?.source) playClip(cam.source, cam.start_sec || 0);
  }

  function onAlert(a: AlertItem) {
    setSelectedId(a.card_id);
    setActiveAlert(a.id);
    playClip(a.source, a.start_sec);
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border bg-card/80 px-4 py-3 backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold tracking-wide">Home Watch</div>
            <p className="mt-1 max-w-xl text-xs text-muted-foreground">
              Don&apos;t scrub three feeds. This board ranks house and dashcam moments that need a
              look, then jumps you to the clip.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline">{team}</Badge>
            <Badge variant={healthy ? "house" : "car"}>
              {healthy === null ? "checking" : healthy ? "healthy" : "degraded"}
            </Badge>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[11px] uppercase tracking-wide text-muted-foreground">Window</span>
          {WINDOWS.map((w) => (
            <Button
              key={w.id}
              size="sm"
              variant={!date && timeFilter === w.id ? "default" : "outline"}
              onClick={() => {
                setDate("");
                setTimeFilter(w.id);
              }}
            >
              {w.label}
            </Button>
          ))}
          <Input
            type="date"
            className="w-[10.5rem]"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
      </header>

      <div className="grid flex-1 grid-cols-1 lg:grid-cols-[220px_minmax(0,1fr)_minmax(320px,400px)]">
        <aside className="border-b border-border p-3 lg:border-b-0 lg:border-r">
          <div className="mb-2 text-[11px] uppercase tracking-wide text-muted-foreground">
            Cameras
          </div>
          <div className="flex gap-2 lg:flex-col">
            {(cameras.length ? cameras : [{ id: "house", label: "House exterior", camera_id: "" }]).map(
              (cam) => {
                const meta = CAM_META[cam.id] || CAM_META.house;
                const Icon = meta.icon;
                const on = selectedId === cam.id;
                return (
                  <Button
                    key={cam.id}
                    variant={on ? "default" : "outline"}
                    className="h-auto w-full justify-start py-2"
                    onClick={() => selectCamera(cam.id)}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="flex flex-col items-start text-left">
                      <span>{cam.label}</span>
                      <span className="text-[10px] font-normal opacity-80">{meta.blurb}</span>
                    </span>
                  </Button>
                );
              }
            )}
          </div>
        </aside>

        <section className="min-w-0 p-3">
          <div className="sticky top-0 z-10 space-y-2 bg-background/95 pb-2 backdrop-blur">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">{selected?.label || "Camera"}</h2>
              <span className="font-mono text-[10px] text-muted-foreground">
                {selected?.camera_id}
              </span>
            </div>
            <Card className="overflow-hidden">
              {player?.source ? (
                <video
                  ref={videoRef}
                  className="aspect-video w-full bg-black"
                  muted
                  controls
                  playsInline
                  preload="metadata"
                  src={clipUrl(player.source)}
                  onLoadedMetadata={(e) => {
                    const v = e.currentTarget;
                    const t = player.start || 0;
                    if (t > 0 && t < (v.duration || t + 1)) v.currentTime = t;
                    v.play().catch(() => undefined);
                  }}
                />
              ) : (
                <div className="flex aspect-video items-center justify-center text-sm text-muted-foreground">
                  {error || "No indexed clip for this camera."}
                </div>
              )}
            </Card>
            {selected?.reasoning ? (
              <Card>
                <CardHeader>
                  <CardTitle className="text-muted-foreground">Camera summary</CardTitle>
                </CardHeader>
                <CardContent className="text-sm leading-relaxed">{selected.reasoning}</CardContent>
              </Card>
            ) : null}
          </div>
        </section>

        <aside className="border-t border-border lg:border-l lg:border-t-0">
          <div className="p-3">
            <h3 className="text-[11px] uppercase tracking-wide text-muted-foreground">
              Needs attention
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              House presence and dashcam hazards in this window. Indoor is watch-only.
            </p>
          </div>
          <Separator />
          <ScrollArea className="h-[calc(100vh-11rem)]">
            <div className="space-y-3 p-3">
              {summaries.map((s) => (
                <Card key={s.kind}>
                  <CardHeader className="flex-row items-center justify-between space-y-0">
                    <CardTitle>{s.label} summary</CardTitle>
                    <Badge variant={kindVariant(s.kind)}>{s.label}</Badge>
                  </CardHeader>
                  <CardContent className="text-sm leading-relaxed text-muted-foreground">
                    {s.text || "No synthesis for this window."}
                  </CardContent>
                </Card>
              ))}
              {alerts === null ? (
                <p className="text-sm text-muted-foreground">Loading alerts…</p>
              ) : alerts.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nothing ranked in this window for house or dashcam.
                </p>
              ) : (
                alerts.map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => onAlert(a)}
                    className={cn(
                      "w-full rounded-lg border border-border bg-card p-3 text-left transition-colors hover:border-primary",
                      activeAlert === a.id && "border-primary"
                    )}
                  >
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <Badge variant={kindVariant(a.kind)}>{a.label}</Badge>
                      <span className="text-[11px] text-muted-foreground">
                        {fmtTime(a.start_sec)} · clip
                      </span>
                    </div>
                    <div className="text-sm leading-snug">{a.summary}</div>
                  </button>
                ))
              )}
            </div>
          </ScrollArea>
        </aside>
      </div>
    </div>
  );
}
