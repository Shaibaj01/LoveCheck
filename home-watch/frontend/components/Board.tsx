"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Play, RotateCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  clipUrl,
  withWindow,
  type AlertItem,
  type Camera,
  type TimeFilter,
} from "@/lib/api";

const WINDOWS: { id: TimeFilter; label: string }[] = [
  { id: "1h", label: "1h" },
  { id: "24h", label: "24h" },
  { id: "7d", label: "7d" },
  { id: "all", label: "All" },
];

type Tab = "all" | "indoor" | "house" | "dashcam" | "rejected";

function fmtClock(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function severity(score: number): "high" | "medium" {
  return score >= 0.28 ? "high" : "medium";
}

function fmtReviewed(sec: number): string {
  if (!sec) return "—";
  if (sec < 60) return `${Math.round(sec)} sec`;
  if (sec < 3600) return `${(sec / 60).toFixed(sec < 600 ? 1 : 0)} min`;
  return `${(sec / 3600).toFixed(1)} hrs`;
}

function titleCaseSite(cardId: string, fallback: string): string {
  if (cardId === "indoor") return "Workplace";
  if (cardId === "house") return "Surroundings";
  if (cardId === "dashcam") return "Traffic";
  return fallback;
}

function ClipCell({
  source,
  start,
  label,
  active,
  onPick,
}: {
  source: string;
  start: number;
  label: string;
  active: boolean;
  onPick: () => void;
}) {
  const ref = useRef<HTMLVideoElement | null>(null);
  return (
    <button
      type="button"
      onClick={() => {
        onPick();
        ref.current?.play().catch(() => undefined);
      }}
      className={cn(
        "relative overflow-hidden rounded-md bg-zinc-800 text-left",
        active && "ring-2 ring-red-500"
      )}
    >
      <video
        ref={ref}
        className="h-28 w-full object-cover"
        muted
        playsInline
        preload="metadata"
        src={clipUrl(source)}
        onLoadedMetadata={(e) => {
          const v = e.currentTarget;
          const t = Math.max(0, start);
          if (t < (v.duration || t + 1)) v.currentTime = t;
        }}
      />
      {active ? (
        <span className="absolute left-3 top-3 h-10 w-7 rounded-sm border-2 border-yellow-400" />
      ) : null}
      <span className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-white">
        <Play className="h-7 w-7 fill-white/90" />
        <span className="text-xs">{label}</span>
      </span>
    </button>
  );
}

export function Board() {
  const [team, setTeam] = useState("team");
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[] | null>(null);
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("7d");
  const [date, setDate] = useState("");
  const [ask, setAsk] = useState("");
  const [askApplied, setAskApplied] = useState("");
  const [tab, setTab] = useState<Tab>("all");
  const [openId, setOpenId] = useState<string | null>(null);
  const [seek, setSeek] = useState<"before" | "event" | "after">("event");
  const [rejected, setRejected] = useState<string[]>([]);
  const [scan, setScan] = useState(0);
  const [error, setError] = useState("");
  const playerRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setAlerts(null);
      setError("");
      try {
        const cams = await fetch(withWindow("/api/cameras", timeFilter, date)).then((r) => r.json());
        if (cancelled) return;
        setTeam(cams.team || "team");
        setCameras(cams.cameras || []);
        if (cams.healthy === false) {
          setError("Cosmos video search was unreachable. Run scan again in a few seconds.");
        }
      } catch {
        if (!cancelled) setError("Could not load cameras.");
      }
      try {
        const data = await fetch(withWindow("/api/alerts", timeFilter, date, askApplied)).then(
          (r) => r.json()
        );
        if (cancelled) return;
        const list: AlertItem[] = data.alerts || [];
        setAlerts(list);
        const first = list.find((a) => !rejected.includes(a.id));
        setOpenId(first?.id ?? null);
        setSeek("event");
      } catch {
        if (!cancelled) setAlerts([]);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [timeFilter, date, askApplied, scan]);

  const live = (alerts || []).filter((a) => !rejected.includes(a.id));
  const rejectedItems = (alerts || []).filter((a) => rejected.includes(a.id));
  const visible = useMemo(() => {
    if (tab === "rejected") return rejectedItems;
    if (tab === "all") return live;
    return live.filter((a) => a.card_id === tab);
  }, [tab, live, rejectedItems]);

  const reviewedSec = cameras.reduce(
    (n, c) => n + (c.window_duration_sec || c.duration_sec || 0),
    0
  );
  const open = visible.find((a) => a.id === openId) || visible[0] || null;

  function clockLabel(a: AlertItem): string {
    const t = fmtClock(a.upload_timestamp);
    return t ? `${titleCaseSite(a.card_id, a.site)} — ${a.camera_label} — ${t}` : `${titleCaseSite(a.card_id, a.site)} — ${a.camera_label}`;
  }

  function playOffset(which: "before" | "event" | "after") {
    if (!open) return;
    setSeek(which);
    const v = playerRef.current;
    const base = open.start_sec || 0;
    const t = which === "before" ? Math.max(0, base - 5) : which === "after" ? base + 5 : base;
    if (v && v.readyState >= 1) {
      v.currentTime = t;
      v.play().catch(() => undefined);
    }
  }

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: "all", label: "All alerts", count: live.length },
    { id: "indoor", label: "Workplace", count: live.filter((a) => a.card_id === "indoor").length },
    { id: "house", label: "Surroundings", count: live.filter((a) => a.card_id === "house").length },
    { id: "dashcam", label: "Traffic", count: live.filter((a) => a.card_id === "dashcam").length },
    { id: "rejected", label: "Rejected", count: rejectedItems.length },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-5">
      <header className="flex items-center justify-between rounded-xl bg-zinc-900 px-5 py-3 text-white">
        <div className="flex items-baseline gap-3">
          <span className="text-xl font-bold text-yellow-400">LoveCheck</span>
          <span className="hidden text-sm text-zinc-300 sm:inline">
            Watching over people at work, on the street, and on the road
          </span>
        </div>
        <div className="flex items-center gap-2">
          {WINDOWS.map((w) => (
            <Button
              key={w.id}
              size="sm"
              variant={!date && timeFilter === w.id ? "default" : "ghost"}
              className={cn(
                "h-8 text-xs",
                !date && timeFilter === w.id
                  ? "bg-yellow-400 text-zinc-900 hover:bg-yellow-300"
                  : "text-zinc-200 hover:bg-zinc-800 hover:text-white"
              )}
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
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="h-8 w-[9.5rem] border-zinc-700 bg-zinc-800 text-xs text-white"
          />
          <Button
            className="bg-yellow-400 text-zinc-900 hover:bg-yellow-300"
            onClick={() => setScan((n) => n + 1)}
          >
            <RotateCw className="h-4 w-4" />
            Run scan
          </Button>
        </div>
      </header>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card className="p-4">
          <div className="text-xs text-muted-foreground">Video reviewed</div>
          <div className="mt-1 text-3xl font-semibold">
            {fmtReviewed(reviewedSec)}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground">Cameras, all sites</div>
          <div className="mt-1 text-3xl font-semibold">{cameras.length || 3}</div>
        </Card>
        <Card className="border-l-4 border-l-red-500 p-4">
          <div className="text-xs text-muted-foreground">Real incidents</div>
          <div className="mt-1 text-3xl font-semibold text-red-600">{live.length}</div>
        </Card>
        <Card className="border-l-4 border-l-emerald-500 p-4">
          <div className="text-xs text-muted-foreground">False alarms filtered</div>
          <div className="mt-1 text-3xl font-semibold text-emerald-600">{rejectedItems.length}</div>
        </Card>
      </div>

      <form
        className="mt-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setAskApplied(ask.trim());
          setTab("all");
        }}
      >
        <Input
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          placeholder='Ask: "Has anyone been near a moving forklift today?"'
          className="h-11 bg-white"
        />
        <Button type="submit" className="h-11 bg-zinc-900 px-5 text-white hover:bg-zinc-800">
          Ask
        </Button>
      </form>

      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 border-b border-border text-sm">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => {
              setTab(t.id);
              setOpenId(null);
            }}
            className={cn(
              "pb-2 font-medium text-muted-foreground",
              tab === t.id && "border-b-2 border-zinc-900 text-zinc-900"
            )}
          >
            {t.label} ({t.count})
          </button>
        ))}
      </div>

      <div className="mt-3 space-y-3">
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        {alerts === null ? (
          <p className="text-sm text-muted-foreground">Scanning this window…</p>
        ) : visible.length === 0 ? (
          <Card className="p-6 text-sm text-muted-foreground">
            {tab === "rejected"
              ? "No rejected clips yet. Open an alert and mark it as not a risk."
              : "Nothing in this time window for this tab."}
          </Card>
        ) : (
          visible.map((a) => {
            const isOpen = open?.id === a.id && tab !== "rejected";
            const sev = severity(a.score);
            if (tab === "rejected") {
              return (
                <Card key={a.id} className="p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="safe">Not a risk</Badge>
                    <span className="font-semibold">{a.title}</span>
                  </div>
                  <p className="mt-2 text-sm">{a.why || a.summary}</p>
                </Card>
              );
            }
            if (!isOpen) {
              return (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => {
                    setOpenId(a.id);
                    setSeek("event");
                  }}
                  className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-white px-4 py-3 text-left"
                >
                  <span className="min-w-0">
                    <span className="flex items-center gap-2">
                      <Badge variant={sev}>{sev.toUpperCase()}</Badge>
                      <span className="font-semibold">{a.title}</span>
                    </span>
                    <span className="mt-1 block text-sm text-muted-foreground">
                      {a.why || a.summary}
                    </span>
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">{clockLabel(a)}</span>
                </button>
              );
            }
            const base = a.start_sec || 0;
            return (
              <Card key={a.id} className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge variant={sev}>{sev.toUpperCase()}</Badge>
                    <h2 className="text-lg font-semibold">{a.title}</h2>
                  </div>
                  <div className="text-xs text-muted-foreground">{clockLabel(a)}</div>
                </div>
                <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
                  <ClipCell
                    source={a.source}
                    start={Math.max(0, base - 5)}
                    label="Before (−5 s)"
                    active={seek === "before"}
                    onPick={() => playOffset("before")}
                  />
                  <ClipCell
                    source={a.source}
                    start={base}
                    label="Event"
                    active={seek === "event"}
                    onPick={() => playOffset("event")}
                  />
                  <ClipCell
                    source={a.source}
                    start={base + 5}
                    label="After (+5 s)"
                    active={seek === "after"}
                    onPick={() => playOffset("after")}
                  />
                </div>
                <video
                  ref={playerRef}
                  className="mt-3 hidden"
                  src={clipUrl(a.source)}
                  muted
                  playsInline
                />
                <p className="mt-3 text-sm">
                  <span className="font-medium">Why flagged:</span> {a.why || a.summary}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Cosmos caption: {a.summary}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Recommended action: review this clip on {titleCaseSite(a.card_id, a.site).toLowerCase()}{" "}
                  and confirm whether anyone is at risk.
                </p>
                <div className="mt-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setRejected((ids) => [...ids, a.id]);
                      setOpenId(null);
                    }}
                  >
                    Not a risk
                  </Button>
                </div>
              </Card>
            );
          })
        )}
      </div>
      <p className="mt-6 text-center text-[11px] text-muted-foreground">{team}</p>
    </div>
  );
}
