import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { alertKey, highestAlertSeverity, playAlertTone, playClockTick, playMonitorBuffer } from "./audio";
import { formatTime, gaugeLevel, gaugePoint, normalizeGauge, percent, roles, title, type Station } from "./logic";

type UniverseSummary = { id: string; name: string; seed: number; universe_time_ms: number };
type Character = { id: string; name: string; backstory: string };
type SessionSummary = {
  session_id: string;
  universe_id: string;
  universe_name: string;
  characters: Character[];
  ship: { id: string; name: string; frame: string };
  provider: string;
};

type SignalLab = {
  access: "available" | "awaiting_acquisition" | "awaiting_share" | "granted" | "lost" | "archived";
  live?: boolean;
  detected_frequency_mhz?: number | null;
  tuned_frequency_mhz?: number | null;
  tuning_tolerance_khz?: number;
  guidance: string;
  recording_retained?: boolean;
  analysis_summary?: { structure_result: string | null; translation_status: string; reply_sent: boolean; processing_steps: number };
  sample_rate_hz?: number;
  times?: number[];
  channels?: number[][];
  spectrogram?: { window_size: number; hop_size: number; frequency_bin_hz: number; frames: number[][] };
  analysis?: {
    shared_with_science: boolean;
    pca_cutoff: number;
    pca_selected_side: "high_variance" | "low_variance";
    pca_configured: boolean;
    structure_result: "noise_like" | "structured_but_contaminated" | "structured_carrier" | "inconclusive" | null;
    structure_confidence: number;
    demodulation_method: "amplitude" | "frequency" | "phase_shift" | "pulse" | null;
    demodulation_confidence: number;
    symbol_preview: string;
    interpretation: string;
    interpretation_confidence: number;
    translation_status: "idle" | "rejected" | "translated";
    translation_protocol: string;
    translation_notes: string;
    reply_sent: boolean;
    reply_acknowledgment: string;
    dmaps_epsilon: number;
    dmaps_diffusion_time: number;
    dmaps_neighbors: number;
    science_classification: string | null;
    science_note: string;
    processing_log: Array<Record<string, unknown>>;
  };
  pca?: {
    eigenvalues: number[];
    explained_variance: number[];
    loadings: number[][];
    cutoff: number;
    selected_side: "high_variance" | "low_variance";
    raw_preview: number[];
    reconstructed_preview: number[];
  };
  dmaps?: {
    eigenvalues: number[];
    epsilon: number;
    diffusion_time: number;
    neighbors: number;
    embedding: Array<{ time_s: number; x: number; y: number; amplitude: number }>;
    denoised_preview: number[];
    outlier_indices: number[];
    outlier_fraction: number;
    temporal_continuity: number;
    dominant_dimensions: number;
    interpretation: string;
  };
};

type Projection = {
  universe_time_ms: number;
  time_scale: number;
  station: Station;
  event_count: number;
  ship: {
    name: string;
    frame: string;
    system_id: string;
    x_km: number;
    y_km: number;
    heading_deg: number;
    target_heading_deg: number;
    throttle: number;
    velocity_km_s: number;
    baseline_target_km: number;
    baseline_autobraking: boolean;
    hull: number;
    shields: number;
    defensive_posture: boolean;
    weapons_authorized: boolean;
    selected_weapon: "focused_energy" | "kinetic_interceptor";
    weapon_charge: number;
    weapon_cooldown_s: number;
    kinetic_ammunition: number;
    last_weapon_result: string;
    heat: number;
    power: Record<string, number>;
    scan_progress: number;
    active_scan_target: string | null;
    active_scan_instrument: string | null;
    transit_remaining_s: number;
    transit_mode: "normal" | "emergency_warp" | null;
    detected_signal_frequency_mhz: number | null;
    capabilities: Array<{ id: string; name: string; category: string; description: string; condition: number; power_mw: number; input_domains: string[]; output_domains: string[] }>;
    cargo: Array<{ id: string; name: string; description: string; installable_capability?: unknown }>;
  };
  system: {
    id: string;
    name: string;
    coordinate: [number, number];
    star_class: string;
    bodies: Array<{ id: string; name: string; kind: string; orbit_index: number; summary: string; properties: Record<string, number> }>;
    neighbors: Array<{ coordinate: [number, number]; id: string }>;
  };
  encounter: null | {
    id: string;
    family: string;
    title: string;
    target_id: string;
    status: string;
    phase: string;
    public_summary: string;
    deadline_s: number | null;
    outcome: string | null;
    salvage_available: boolean;
    requires_signal_analysis: boolean;
    signal_analysis_complete: boolean;
    npc: null | {
      name: string;
      vessel_name: string;
      disposition: number;
      intention_observed: string;
      relationship: string;
      activity: string;
      activity_reason: string;
      current_request: string;
      commitments: string[];
    };
  };
  observations: Array<{
    id: string;
    station: Station;
    source_capability: string;
    measurement: string;
    value: string | number;
    uncertainty: number | null;
    unit?: string | null;
    confidence: number;
    target: string;
  }>;
  sensor_stability: number;
  alerts: Array<{ severity: "status" | "caution" | "critical"; source: string; message: string }>;
  crew_knowledge: string[];
  messages: Array<{ time_ms: number; speaker: string; message: string }>;
  contacts: Array<{ id: string; label: string; kind: "vessel"; x_km: number; y_km: number; range_km: number; bearing_deg: number; confidence: number; status: "tracked" | "hostile" }>;
  narrative: { pressure: number; danger: number; next_decision: string };
  weapon_control: null | {
    authorized: boolean;
    selected_weapon: "focused_energy" | "kinetic_interceptor";
    display_name: string;
    charge: number;
    cooldown_s: number;
    kinetic_ammunition: number;
    required_charge: { warning: number; precision: number; full: number };
    solution: null | { range_km: number; max_range_km: number; lock_quality: number; in_range: boolean; time_of_flight_s: number };
    blockers: string[];
    last_result: string;
    target_damage: null | { estimated_shields: number; estimated_hull: number; confidence: number };
  };
  engineering_effects: null | {
    propulsion: { maximum_speed_km_s: number; turn_rate_deg_s: number };
    sensors: { stability: number; nominal_scan_rate_pct_s: number };
    communications: { transmitter_ready: boolean; allocated_mw: number };
    shields: { target_strength: number; recharge_pct_s: number };
    weapons: { firing_bus_ready: boolean; charge_rate_pct_s: number };
    cooling: { heat_removal_pct_s: number; weapon_cooldown_rate: number; net_heat_pct_s: number; trend: "cooling" | "heating" | "stable"; eta_safe_s: number | null };
  };
  objectives: {
    open_threads: Array<{ id: string; title: string; kind: string; stage: number; summary: string; origin_system_id: string; next_action: string; ready: boolean; reason: string; evidence_count: number; current_system: boolean; station_hint: string }>;
    activities: Array<{ id: string; label: string; detail: string; kind: "survey" | "thread" }>;
    primary: null | { id: string; title: string; next_action: string; ready: boolean; reason: string };
  };
  remote_channels: Array<{thread_id: string; name: string; frequency_mhz: number; messages: string[]}>;
  continuity: { valid?: boolean; issues?: Array<{ severity: string; code: string; message: string }>; counts?: Record<string, number> };
  localization: null | {
    measurements: Array<{ id: string; origin_x_km: number; origin_y_km: number; bearing_deg: number; angular_uncertainty_deg: number; confidence: number }>;
    estimated_x_km: number | null;
    estimated_y_km: number | null;
    uncertainty_radius_km: number | null;
    confidence: number;
    baseline_km: number;
    intercept_heading_deg: number | null;
    guidance: string;
  };
  signal_lab: SignalLab | null;
  workflow: null | {
    title: string;
    steps: Array<{ id: string; label: string; complete: boolean; failed?: boolean; optional?: boolean }>;
    next_action: string;
    result?: string;
    result_severity?: "status" | "caution" | "critical";
  };
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(detail.detail ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

function App() {
  const [universes, setUniverses] = useState<UniverseSummary[]>([]);
  const [session, setSession] = useState<SessionSummary | null>(null);
  const [station, setStation] = useState<Station>("integrated");
  const [characterId, setCharacterId] = useState("");
  const [newCrewName, setNewCrewName] = useState("");
  const [projection, setProjection] = useState<Projection | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("Disconnected");
  const socket = useRef<WebSocket | null>(null);
  const sequence = useRef(0);
  const reconnectTimer = useRef<number | null>(null);
  const [audioEnabled, setAudioEnabled] = useState(false);
  const [clockTickEnabled, setClockTickEnabled] = useState(true);
  const [acknowledgedAlerts, setAcknowledgedAlerts] = useState<Set<string>>(new Set());
  const audioContextRef = useRef<AudioContext | null>(null);
  const monitorSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const previousAlertKeys = useRef<Set<string>>(new Set());
  const lastTickSecond = useRef(-1);
  const lastTickWallTime = useRef(0);
  const [requestActivity, setRequestActivity] = useState<RequestActivityState | null>(null);
  const pendingRequest = useRef<{ sequence: number; label: string } | null>(null);
  const activityTimer = useRef<number | null>(null);

  function ensureAudio(): AudioContext {
    const AudioContextConstructor = window.AudioContext;
    const context = audioContextRef.current ?? new AudioContextConstructor();
    audioContextRef.current = context;
    void context.resume();
    return context;
  }

  function enableAudio() {
    const context = ensureAudio();
    setAudioEnabled(true);
    const severity = highestAlertSeverity(projection?.alerts ?? []);
    if (severity) playAlertTone(context, severity);
  }

  function muteAudio() {
    stopMonitor();
    setAudioEnabled(false);
    void audioContextRef.current?.suspend();
  }

  function stopMonitor() {
    try { monitorSourceRef.current?.stop(); } catch { /* source already ended */ }
    monitorSourceRef.current = null;
  }

  function playSignalMonitor(samples: number[], sampleRateHz: number) {
    const context = ensureAudio();
    setAudioEnabled(true);
    stopMonitor();
    monitorSourceRef.current = playMonitorBuffer(context, samples, sampleRateHz);
    if (monitorSourceRef.current) monitorSourceRef.current.onended = () => { monitorSourceRef.current = null; };
  }

  useEffect(() => () => {
    try { monitorSourceRef.current?.stop(); } catch { /* source already ended */ }
    void audioContextRef.current?.close();
  }, []);

  const alertSignature = projection?.alerts.map(alertKey).join("|") ?? "";
  useEffect(() => {
    const alerts = projection?.alerts ?? [];
    const currentKeys = new Set(alerts.map(alertKey));
    const newAlerts = alerts.filter((alert) => !previousAlertKeys.current.has(alertKey(alert)));
    previousAlertKeys.current = currentKeys;
    setAcknowledgedAlerts((current) => {
      const retained = new Set([...current].filter((key) => currentKeys.has(key)));
      return retained.size === current.size ? current : retained;
    });
    if (audioEnabled && newAlerts.length) {
      const severity = highestAlertSeverity(newAlerts);
      if (severity) playAlertTone(ensureAudio(), severity);
    }
  }, [alertSignature, audioEnabled]);

  const unacknowledgedCritical = projection?.alerts.some((alert) => alert.severity === "critical" && !acknowledgedAlerts.has(alertKey(alert))) ?? false;
  useEffect(() => {
    if (!audioEnabled || !unacknowledgedCritical) return;
    const timer = window.setInterval(() => playAlertTone(ensureAudio(), "critical"), 3500);
    return () => window.clearInterval(timer);
  }, [audioEnabled, unacknowledgedCritical]);

  useEffect(() => {
    if (!projection || !audioEnabled || !clockTickEnabled) return;
    const second = Math.floor(projection.universe_time_ms / 1000);
    const now = performance.now();
    if (second !== lastTickSecond.current && now - lastTickWallTime.current >= 350) {
      playClockTick(ensureAudio());
      lastTickSecond.current = second;
      lastTickWallTime.current = now;
    }
  }, [projection?.universe_time_ms, audioEnabled, clockTickEnabled]);

  useEffect(() => {
    api<UniverseSummary[]>("/api/v1/universes").then((items) => {
      setUniverses(items);
      const saved = sessionStorage.getItem("space-crew-connection");
      if (saved) {
        try {
          const connection = JSON.parse(saved) as { universe_id?: string };
          if (connection.universe_id && items.some((item) => item.id === connection.universe_id)) loadUniverse(connection.universe_id);
        } catch {
          sessionStorage.removeItem("space-crew-connection");
        }
      }
    }).catch((err) => setError(String(err)));
  }, []);

  useEffect(() => {
    if (!session) return;
    setCharacterId((current) => current || session.characters[0]?.id || "");
    const saved = sessionStorage.getItem("space-crew-connection");
    if (!saved || socket.current) return;
    try {
      const connection = JSON.parse(saved) as { session_id: string; path: string; station: Station; sequence: number };
      if (connection.session_id === session.session_id) {
        setStation(connection.station);
        sequence.current = connection.sequence ?? 0;
        connectSocket(connection.path, true);
      }
    } catch {
      sessionStorage.removeItem("space-crew-connection");
    }
  }, [session]);

  async function createUniverse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    try {
      const created = await api<SessionSummary>("/api/v1/universes", {
        method: "POST",
        body: JSON.stringify({
          universe_name: values.get("universe_name"),
          ship_name: values.get("ship_name"),
          character_name: values.get("character_name"),
          backstory: values.get("backstory"),
          scenario_preset: values.get("scenario_preset"),
          crew_capacity: Number(values.get("crew_capacity")),
          seed: values.get("seed") ? Number(values.get("seed")) : null,
        }),
      });
      setSession(created);
      setError("");
    } catch (err) {
      setError(String(err));
    }
  }

  async function loadUniverse(id: string) {
    try {
      setSession(await api<SessionSummary>("/api/v1/sessions", { method: "POST", body: JSON.stringify({ universe_id: id }) }));
      setError("");
    } catch (err) {
      setError(String(err));
    }
  }

  async function join() {
    if (!session) return;
    try {
      const joined = await api<{ token: string; websocket_path: string }>(`/api/v1/sessions/${session.session_id}/join`, {
        method: "POST",
        body: JSON.stringify({
          display_name: session.characters.find((character) => character.id === characterId)?.name ?? "Crew member",
          character_id: characterId,
          station,
        }),
      });
      sessionStorage.setItem("space-crew-connection", JSON.stringify({ universe_id: session.universe_id, session_id: session.session_id, path: joined.websocket_path, station, sequence: 0 }));
      sequence.current = 0;
      connectSocket(joined.websocket_path, true);
    } catch (err) {
      setError(String(err));
    }
  }

  function connectSocket(path: string, retry: boolean) {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${scheme}://${location.host}${path}`);
    socket.current = ws;
    ws.onopen = () => setStatus("Connected");
    ws.onerror = () => setStatus("Link interrupted");
    ws.onmessage = (message) => {
      const data = JSON.parse(message.data);
      if (data.type === "snapshot") setProjection(data.data);
      if (data.type === "command_error") {
        setError(data.error);
        finishRequest(data.client_sequence, true);
      }
      if (data.type === "command_result") {
        setError("");
        finishRequest(data.client_sequence, false);
      }
    };
    ws.onclose = (event) => {
      socket.current = null;
      setStatus("Reconnecting…");
      if (event.code === 4401) {
        sessionStorage.removeItem("space-crew-connection");
        setProjection(null);
        setStatus("Session credentials expired — rejoin");
      } else if (retry) {
        reconnectTimer.current = window.setTimeout(() => connectSocket(path, true), 1500);
      }
    };
  }

  async function createCrewMember() {
    if (!session || !newCrewName.trim()) return;
    try {
      const character = await api<Character>(`/api/v1/sessions/${session.session_id}/characters`, {
        method: "POST",
        body: JSON.stringify({ name: newCrewName.trim(), backstory: "Joined this expedition as a new crew member.", expertise: [] }),
      });
      setSession({ ...session, characters: [...session.characters, character] });
      setCharacterId(character.id);
      setNewCrewName("");
    } catch (err) {
      setError(String(err));
    }
  }

  function command(command_type: string, parameters: Record<string, unknown> = {}) {
    if (!socket.current || socket.current.readyState !== WebSocket.OPEN) {
      setError("Station is not connected");
      return;
    }
    sequence.current += 1;
    const activityLabels: Record<string, string> = {
      ask_computer: "SHIP COMPUTER THINKING",
      transmit: "TRANSMITTING — WAITING FOR VESSEL RESPONSE",
      send_signal_reply: "TRANSMITTING — UNIVERSAL TRANSLATOR WAITING FOR RESPONSE",
      reply_remote_contact: "REMOTE TRANSMISSION — WAITING FOR RESPONSE",
    };
    if (activityLabels[command_type]) {
      pendingRequest.current = { sequence: sequence.current, label: activityLabels[command_type] };
      setRequestActivity({ state: "waiting", label: activityLabels[command_type] });
    }
    const saved = sessionStorage.getItem("space-crew-connection");
    if (saved) {
      const connection = JSON.parse(saved);
      connection.sequence = sequence.current;
      sessionStorage.setItem("space-crew-connection", JSON.stringify(connection));
    }
    socket.current.send(JSON.stringify({ type: "command", client_sequence: sequence.current, command_type, parameters }));
  }

  function finishRequest(clientSequence: number, failed: boolean) {
    if (!pendingRequest.current || pendingRequest.current.sequence !== clientSequence) return;
    pendingRequest.current = null;
    setRequestActivity({ state: failed ? "failed" : "received", label: failed ? "REQUEST FAILED — CHECK CONSOLE MESSAGE" : "RESPONSE RECEIVED" });
    if (activityTimer.current) window.clearTimeout(activityTimer.current);
    activityTimer.current = window.setTimeout(() => setRequestActivity(null), 3500);
  }

  if (!session) {
    return <Setup universes={universes} createUniverse={createUniverse} loadUniverse={loadUniverse} error={error} />;
  }

  if (!projection) {
    return (
      <main className="setup-shell">
        <section className="setup-card">
          <p className="eyebrow">CREW ASSIGNMENT</p>
          <h1>{session.ship.name}</h1>
          <p>{session.universe_name} · {session.ship.frame} · Director: {session.provider}</p>
          <label>Character
            <select value={characterId} onChange={(event) => setCharacterId(event.target.value)}>
              {session.characters.map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}
            </select>
          </label>
          <div className="computer-query">
            <label>New crew member<input value={newCrewName} onChange={(event) => setNewCrewName(event.target.value)} placeholder="Name" /></label>
            <button onClick={createCrewMember} disabled={!newCrewName.trim()}>Create</button>
          </div>
          <label>Station
            <select value={station} onChange={(event) => setStation(event.target.value as Station)}>
              {roles.map((role) => <option key={role} value={role}>{title(role)}</option>)}
            </select>
          </label>
          <button className="primary" onClick={join} disabled={!characterId}>Join expedition</button>
          {error && <p className="error" role="alert">{error}</p>}
        </section>
      </main>
    );
  }

  const show = (role: Station) => station === "integrated" || station === role;
  return (
    <main className="console-shell">
      <header className="topbar">
        <div><span className="eyebrow">{title(station)} STATION</span><h1>{projection.ship.name}</h1></div>
        <div className="status-strip">
          <Metric label="SYSTEM" value={projection.system.name} />
          <Metric label="HULL" value={percent(projection.ship.hull)} danger={projection.ship.hull < .5} />
          <Metric label="HEAT" value={percent(projection.ship.heat)} danger={projection.ship.heat > .85} />
          <Metric label="LINK" value={status} />
        </div>
      </header>
      {error && <div className="error-banner" role="alert" onClick={() => setError("")}>{error}</div>}
      {requestActivity && <RequestActivity activity={requestActivity} />}
      <AnnunciatorPanel
        alerts={projection.alerts}
        acknowledged={acknowledgedAlerts}
        audioEnabled={audioEnabled}
        clockTickEnabled={clockTickEnabled}
        onEnableAudio={enableAudio}
        onToggleMute={muteAudio}
        onToggleTick={() => setClockTickEnabled((enabled) => !enabled)}
        onAcknowledge={() => setAcknowledgedAlerts(new Set(projection.alerts.map(alertKey)))}
      />
      <AlertStack alerts={projection.alerts} acknowledged={acknowledgedAlerts} />
      <nav className="station-nav" aria-label="Station shortcuts">
        <a href="#activities">Situation & objectives</a>
        {[["CMD", "Command", "command"], ["FLT", "Flight", "flight"], ["MAP", "Map", "flight"], ["ENG", "Engineering", "engineering"], ["SCI", "Science", "science"], ["COM", "Communications", "communications"], ["TAC", "Tactical", "tactical"]].filter(([, , role]) => show(role as Station)).map(([code, name]) => <a key={code} href={`#station-${code}`}>{name}</a>)}
        <span>{projection.ship.transit_remaining_s > 0 ? `In transit · ${projection.ship.transit_remaining_s.toFixed(0)}s` : projection.encounter?.status === "resolved" ? "Investigation resolved" : projection.encounter?.phase === "hostile" ? "Hostile contact" : projection.ship.active_scan_target && projection.ship.scan_progress < 1 ? `Scanning · ${percent(projection.ship.scan_progress)}` : "Ready"}</span>
      </nav>
      <section className="encounter-banner">
        <div>
          <span className="eyebrow">CURRENT SITUATION</span>
          <strong>{projection.encounter?.title ?? "Open navigation"}</strong>
          <p>{projection.encounter?.phase === "signal_lost" ? "The carrier has faded. No translated reply reached the source, so contact was not established." : projection.encounter?.public_summary ?? "No focused contact. Select a neighboring system to continue."}</p>
        </div>
        {projection.encounter?.deadline_s != null && <div className="deadline"><span>DEVELOPMENT IN</span>{projection.encounter.deadline_s.toFixed(0)}s</div>}
      </section>
      {projection.encounter?.npc && <ContactIntentPanel npc={projection.encounter.npc} contact={projection.contacts[0]} nextDecision={projection.narrative.next_decision} />}
      {projection.workflow && <WorkflowStatus workflow={projection.workflow} />}
      <ObjectivesPanel state={projection} command={command} />
      <section className="console-grid">
        {show("command") && <CommandPanel state={projection} command={command} />}
        {show("flight") && <FlightPanel state={projection} command={command} />}
        {(station === "integrated" || station === "command" || station === "flight" || station === "science" || station === "tactical") && <SystemMapPanel state={projection} command={command} />}
        {show("engineering") && <EngineeringPanel state={projection} command={command} />}
        {show("science") && <SciencePanel state={projection} command={command} />}
        {show("communications") && <CommunicationsPanel state={projection} command={command} audio={{ playSignalMonitor, stopMonitor }} requestActivity={requestActivity} />}
        {show("tactical") && <TacticalPanel state={projection} command={command} />}
      </section>
    </main>
  );
}

function ObjectivesPanel({ state, command }: PanelProps) {
  const primary = state.objectives.primary;
  return <section id="activities" className="objectives-panel" aria-label="Available activities and persistent objectives">
    <header><div><span className="eyebrow">EXPEDITION ACTIVITY BOARD</span><strong>{primary ? primary.title : "No unresolved threads"}</strong></div><span className={state.continuity.valid === false ? "continuity-fault" : "continuity-ok"}>{state.continuity.valid === false ? "CONTINUITY ISSUE" : "CANON CONSISTENT"}</span></header>
    <div className="activity-grid">
      {state.objectives.open_threads.map((thread) => <article key={thread.id} className={thread.current_system ? "current" : "remote"}>
        <small>{thread.kind.toUpperCase()} · STAGE {thread.stage + 1} · {thread.current_system ? "LOCAL" : "PERSISTENT"}</small>
        <strong>{thread.title}</strong>
        <span>{thread.summary}</span>
        <strong>{thread.next_action}</strong>
        {thread.kind === "consequence" ? <div className="button-row"><button onClick={() => command("choose_consequence", {thread_id: thread.id, choice: "archive"})}>Archive privately</button><button onClick={() => command("choose_consequence", {thread_id: thread.id, choice: "publish"})}>Publish findings</button></div> : thread.ready ? <FindingForm key={thread.id} state={state} command={command} thread={thread} /> : <><span>{thread.reason}</span><a href={`#station-${thread.station_hint}`}>Open {thread.station_hint === "COM" ? "Communications" : thread.station_hint === "FLT" ? "Flight" : "Science"}</a></>}
      </article>)}
    </div>
    <details><summary>Other things to do in this system</summary><ul>{state.objectives.activities.filter((activity) => activity.kind === "survey").map((activity) => <li key={activity.id}><strong>{activity.label}</strong><span>{activity.detail} Select this body as a Science scan target.</span></li>)}</ul></details>
  </section>;
}

function FindingForm({state, command, thread}: PanelProps & {thread: Projection["objectives"]["open_threads"][number]}) {
  const [note, setNote] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const evidence = state.observations.filter(obs => obs.station === "science" && obs.target === state.encounter?.target_id);
  return <form onSubmit={event => {event.preventDefault(); command("pursue_thread", {thread_id: thread.id, action: thread.next_action, note, observation_ids: selected});}}>
    <p>Review the observations. Record what they support and what remains uncertain.</p>
    {evidence.map(obs => <label key={obs.id}><input type="checkbox" checked={selected.includes(obs.id)} onChange={event => setSelected(event.target.checked ? [...selected, obs.id] : selected.filter(id => id !== obs.id))} />{obs.measurement}: {String(obs.value)} {obs.unit ?? ""} · {percent(obs.confidence)} confidence</label>)}
    <label>Evidence-backed conclusion<textarea value={note} onChange={event => setNote(event.target.value)} /></label>
    <button disabled={!note.trim() || selected.length === 0}>Record conclusion</button>
  </form>;
}

function ContactIntentPanel({ npc, contact, nextDecision }: {
  npc: NonNullable<NonNullable<Projection["encounter"]>["npc"]>;
  contact?: Projection["contacts"][number];
  nextDecision: string;
}) {
  const trust = Math.round((npc.disposition + 1) * 50);
  return <section className="contact-intent" aria-label="Observed contact behavior">
    <header><span className="eyebrow">CONTACT BEHAVIOR</span><strong>{npc.vessel_name} · {npc.relationship.toUpperCase()}</strong></header>
    <div className="contact-intent-grid">
      <div><small>OBSERVED ACTIVITY</small><strong>{npc.activity}</strong><span>{npc.activity_reason}</span></div>
      <div><small>REQUEST / COMMITMENT</small><strong>{npc.current_request || "No explicit request"}</strong><span>{npc.commitments.at(-1) || nextDecision || "No promise has been recorded."}</span></div>
      <div><small>RELATIONSHIP ESTIMATE</small><strong>{trust}% trust · {npc.intention_observed}</strong><span>{contact ? `${Math.round(contact.range_km).toLocaleString()} km · bearing ${contact.bearing_deg.toFixed(1)}°` : "Contact no longer on radar"}</span></div>
    </div>
  </section>;
}

function WorkflowStatus({ workflow }: { workflow: NonNullable<Projection["workflow"]> }) {
  return <section className="workflow-status" aria-label="Current investigation status">
    <header><span className="eyebrow">CURRENT WORKFLOW</span><strong>{workflow.title}</strong></header>
    {workflow.result && <div className={`workflow-result ${workflow.result_severity ?? "status"}`} role="alert"><strong>{workflow.result}</strong></div>}
    <ol>{workflow.steps.map((step) => <li key={step.id} className={step.failed ? "failed" : step.complete ? "complete" : "pending"}><i>{step.failed ? "×" : step.complete ? "✓" : step.optional ? "◇" : "○"}</i><span>{step.label}{step.optional ? " · optional" : ""}</span></li>)}</ol>
    <div className="localization-terminal"><strong>NEXT REQUIRED ACTION</strong><span>&gt; {workflow.next_action.toUpperCase()}</span></div>
  </section>;
}

function Setup(props: {
  universes: UniverseSummary[];
  createUniverse: (event: FormEvent<HTMLFormElement>) => void;
  loadUniverse: (id: string) => void;
  error: string;
}) {
  const [scenarioPreset, setScenarioPreset] = useState("friendly_contact_test");
  return (
    <main className="setup-shell">
      <section className="intro">
        <p className="eyebrow">SPACE SIMULATION CREW</p>
        <h1>Operate the unknown together.</h1>
        <p>Every station sees a different part of reality. Communicate, experiment, and carry your discoveries into an endless persistent universe.</p>
      </section>
      <section className="setup-card">
        <h2>Begin a universe</h2>
        <form onSubmit={props.createUniverse}>
          <label>Starting scenario<select name="scenario_preset" value={scenarioPreset} onChange={(event) => setScenarioPreset(event.target.value)}>
            <option value="friendly_contact_test">Friendly Contact Test · two-hour conversation window</option>
            <option value="random">Random Expedition · normal encounters and deadlines</option>
          </select></label>
          {scenarioPreset === "friendly_contact_test" && <p className="preset-summary"><strong>FRIENDLY CONTACT TEST</strong><span>Begins beside a friendly vessel with its carrier received and opening greeting translated. Enter the displayed frequency, send messages, and receive repeated AI-generated translated replies.</span></p>}
          <label>Universe name<input name="universe_name" defaultValue="The Far Quiet" required /></label>
          <label>Ship name<input name="ship_name" defaultValue="Lumen" required /></label>
          <label>Your character<input name="character_name" defaultValue="Commander Vale" required /></label>
          <label>Backstory<textarea name="backstory" defaultValue="A survey specialist drawn to unexplained signals beyond charted space." /></label>
          <div className="form-row">
            <label>Crew capacity<input name="crew_capacity" type="number" min="1" max="100" defaultValue="6" /></label>
            <label>Seed (optional)<input name="seed" type="number" placeholder="random" /></label>
          </div>
          <button className="primary" type="submit">Create and host</button>
        </form>
        {props.universes.length > 0 && <><h2>Continue</h2><div className="universe-list">
          {props.universes.map((universe) => <button key={universe.id} onClick={() => props.loadUniverse(universe.id)}>
            <strong>{universe.name}</strong><span>Seed {universe.seed} · {formatTime(universe.universe_time_ms)}</span>
          </button>)}
        </div></>}
        {props.error && <p className="error" role="alert">{props.error}</p>}
      </section>
    </main>
  );
}

function CommandPanel({ state, command }: PanelProps) {
  return <Panel title="Command" code="CMD">
    <div className="button-row">
      {[1, 5, 20, 100].map((scale) => <button key={scale} className={state.time_scale === scale ? "active" : ""} onClick={() => command("set_time_scale", { scale })}>{scale}×</button>)}
    </div>
    <p className="readout">Elapsed universe time <strong>{formatTime(state.universe_time_ms)}</strong></p>
    {state.encounter?.status === "active" && <div className="button-row">
      {state.encounter.npc || state.encounter.requires_signal_analysis ? <button disabled={state.ship.active_scan_target !== state.encounter.target_id || state.ship.scan_progress < .75 || (state.encounter.requires_signal_analysis && !state.encounter.signal_analysis_complete)} onClick={() => command("resolve_encounter", { method: "investigation" })}>Conclude investigation</button> : <a href="#activities">Review evidence and record conclusion</a>}
      {state.encounter.npc && <button onClick={() => command("resolve_encounter", { method: "diplomacy" })}>Accept accord</button>}
    </div>}
    {state.encounter?.salvage_available && <button className="primary" onClick={() => command("claim_salvage")}>Authorize recovery</button>}
    <button className={state.ship.weapons_authorized ? "danger active" : ""} onClick={() => command("set_weapons_authorization", { authorized: !state.ship.weapons_authorized })}>{state.ship.weapons_authorized ? "Revoke weapons release" : "Authorize weapons release"}</button>
    <button className="danger" disabled={state.ship.transit_remaining_s > 0 || state.ship.heat >= 1.15 || state.ship.power.propulsion < .12} onClick={() => command("emergency_warp")}>Authorize emergency warp out</button>
    <StationReadings state={state} station="command" />
  </Panel>;
}

function FlightPanel({ state, command }: PanelProps) {
  const [heading, setHeading] = useState(state.ship.target_heading_deg);
  const [throttle, setThrottle] = useState(state.ship.throttle);
  return <Panel title="Flight" code="FLT">
    <MetricGrid values={[
      ["HEADING", `${state.ship.heading_deg.toFixed(1)}°`],
      ["VELOCITY", `${state.ship.velocity_km_s.toFixed(1)} km/s`],
      ["TRANSIT", state.ship.transit_remaining_s ? `${state.ship.transit_mode === "emergency_warp" ? "WARP · " : ""}${state.ship.transit_remaining_s.toFixed(1)}s` : "READY"],
    ]} />
    <label>Desired heading <output>{heading.toFixed(0)}°</output><input type="range" min="0" max="359" value={heading} onChange={(event) => setHeading(Number(event.target.value))} /></label>
    <label>Throttle <output>{percent(throttle)}</output><input type="range" min="0" max="1" step=".01" value={throttle} onChange={(event) => setThrottle(Number(event.target.value))} /></label>
    <button className="primary" onClick={() => command("set_flight", { heading_deg: heading, throttle })}>Commit maneuver</button>
    <h3>Neighboring systems</h3>
    <div className="button-row wrap">{state.system.neighbors.map((neighbor) => <button key={neighbor.id} disabled={state.ship.transit_remaining_s > 0} onClick={() => command("begin_transit", { coordinate: neighbor.coordinate })}>Vector {neighbor.coordinate.join(", ")}</button>)}</div>
    <div className="emergency-warp-control">
      <strong>EMERGENCY WARP</strong><span>Immediate escape to the first neighboring system. Adds 18% heat and drops the defensive field.</span>
      <button className="danger" disabled={state.ship.transit_remaining_s > 0 || state.ship.heat >= 1.15 || state.ship.power.propulsion < .12} onClick={() => command("emergency_warp")}>Initiate emergency warp out</button>
    </div>
    <StationReadings state={state} station="flight" />
  </Panel>;
}

function EngineeringPanel({ state, command }: PanelProps) {
  const [power, setPower] = useState(state.ship.power);
  const authoritativePower = Object.values(state.ship.power).join(":");
  // A snapshot arrives ten times per second. Synchronize only when authoritative values actually
  // change, otherwise an in-progress drag would rubber-band to its starting position.
  useEffect(() => setPower(state.ship.power), [authoritativePower]);
  const total = Object.values(power).reduce((sum, value) => sum + value, 0);
  return <Panel title="Engineering" code="ENG">
    <div className="gauge-bank">
      <AnalogGauge label="Reactor load" value={total} maximum={1.2} nominal={1} warning={1} critical={1.1} />
      <AnalogGauge label="Thermal index" value={state.ship.heat} maximum={1.5} nominal={.75} warning={.75} critical={1} />
      <AnalogGauge label="Hull integrity" value={state.ship.hull} maximum={1} nominal={.75} warning={.7} critical={.4} dangerWhen="low" />
    </div>
    {Object.entries(power).map(([key, value]) => <label key={key} htmlFor={`power-${key}`}>{title(key)} <output>{percent(value)}</output>
      <input id={`power-${key}`} aria-label={title(key)} type="range" min="0" max=".5" step=".01" value={value} onChange={(event) => setPower({ ...power, [key]: Number(event.target.value) })} />
    </label>)}
    <button className="primary" disabled={total > 1.0001} onClick={() => command("set_power", power)}>Route power · {percent(total)}</button>
    {state.engineering_effects && <div className="power-effects" aria-label="Power allocation effects">
      <article><small>PROPULSION</small><strong>{state.engineering_effects.propulsion.maximum_speed_km_s} km/s maximum</strong><span>{state.engineering_effects.propulsion.turn_rate_deg_s}°/s turn rate</span></article>
      <article><small>SENSORS</small><strong>{percent(state.engineering_effects.sensors.stability)} stability</strong><span>{state.engineering_effects.sensors.nominal_scan_rate_pct_s}%/s nominal scan rate</span></article>
      <article className={state.engineering_effects.communications.transmitter_ready ? "ready" : "blocked"}><small>COMMUNICATIONS</small><strong>{state.engineering_effects.communications.transmitter_ready ? "TRANSMITTER READY" : "TRANSMITTER OFFLINE"}</strong><span>{state.engineering_effects.communications.allocated_mw} MW · minimum allocation 3%</span></article>
      <article><small>DEFENSIVE FIELD</small><strong>{percent(state.engineering_effects.shields.target_strength)} sustainable strength</strong><span>{state.engineering_effects.shields.recharge_pct_s}%/s recharge</span></article>
      <article className={state.engineering_effects.weapons.firing_bus_ready ? "ready" : "blocked"}><small>WEAPONS</small><strong>{state.engineering_effects.weapons.firing_bus_ready ? "FIRING BUS READY" : "FIRING BUS OFFLINE"}</strong><span>{state.engineering_effects.weapons.charge_rate_pct_s}%/s charge · minimum allocation 4%</span></article>
      <article className={state.engineering_effects.cooling.trend === "heating" ? "blocked" : "ready"}><small>COOLING · NET THERMAL FLOW</small><strong>{state.engineering_effects.cooling.net_heat_pct_s > 0 ? "+" : ""}{state.engineering_effects.cooling.net_heat_pct_s}%/s · {state.engineering_effects.cooling.trend.toUpperCase()}</strong><span>{state.engineering_effects.cooling.heat_removal_pct_s}%/s removed · {state.engineering_effects.cooling.weapon_cooldown_rate}× weapon recovery{state.engineering_effects.cooling.eta_safe_s != null && state.engineering_effects.cooling.eta_safe_s > 0 ? ` · safe in ${state.engineering_effects.cooling.eta_safe_s.toFixed(0)}s` : ""}</span></article>
    </div>}
    {state.ship.hull < .999 && <button disabled={state.ship.velocity_km_s > 1 || state.ship.heat >= .75} onClick={() => command("field_repair")}>Conduct field repair · restore up to 10%</button>}
    {state.ship.cargo.map((item) => <button key={item.id} onClick={() => command("install_cargo", { cargo_id: item.id })}>Install {item.name}</button>)}
    <StationReadings state={state} station="engineering" />
  </Panel>;
}

function scanPurposeGuidance(name: string): { use: string; target: string; results: string } {
  const guidance: Record<string, { use: string; target: string; results: string }> = {
    "Composition and Temperature Scan": {
      use: "Find out what something is made of and how hot it is.",
      target: "Planet, moon, structure, debris, anomaly, or vessel.",
      results: "Material signatures, temperature, broad emissions, and evidence of non-natural composition.",
    },
    "Radiation Hazard Scan": {
      use: "Determine whether local radiation or energetic particles can damage the ship.",
      target: "Any body, region, anomaly, or focused encounter target.",
      results: "Radiation level, pulse period, particle variation, and hazard confidence.",
    },
    "Signal Direction Scan": {
      use: "Measure where an encounter signal is coming from. Move and repeat it to triangulate position.",
      target: "The focused encounter signal only.",
      results: "Bearing, angular uncertainty, signal stability, and—after a second baseline—source position.",
    },
    "Vessel Systems and Weapons Scan": {
      use: "Estimate what another vessel can do and whether it appears armed.",
      target: "A detected vessel only.",
      results: "Radar profile, propulsion and power activity, defensive systems, and weapon-system likelihood.",
    },
  };
  return guidance[name] ?? { use: "Collect physical measurements from the selected target.", target: "Any compatible focused target.", results: "Instrument-specific measurements with confidence and uncertainty." };
}

function SciencePanel({ state, command }: PanelProps) {
  const defaultTarget = state.encounter?.target_id ?? state.system.bodies[0]?.id;
  const [target, setTarget] = useState(defaultTarget);
  const scienceInstruments = state.ship.capabilities.filter((capability) => capability.category === "hardware" && capability.output_domains.some((domain) => ["composition", "temperature", "signal", "flux", "periodicity", "hazard", "gradient", "coherence", "phase", "vessel_systems", "weapons", "defenses"].includes(domain)));
  const defaultInstrument = state.ship.active_scan_instrument ?? scienceInstruments[0]?.id ?? "";
  const [instrumentId, setInstrumentId] = useState(defaultInstrument);
  useEffect(() => setTarget(defaultTarget), [defaultTarget]);
  useEffect(() => setInstrumentId(defaultInstrument), [state.ship.system_id]);
  useEffect(() => {
    if (!scienceInstruments.some((instrument) => instrument.id === instrumentId)) setInstrumentId(defaultInstrument);
  }, [defaultInstrument, instrumentId, scienceInstruments]);
  const instrument = scienceInstruments.find((candidate) => candidate.id === instrumentId);
  const guidance = instrument ? scanPurposeGuidance(instrument.name) : null;
  return <Panel title="Science" code="SCI">
    <p className="role-boundary"><strong>CHOOSE THE QUESTION YOU WANT ANSWERED</strong><span>Select a purpose-named scan, aim it at a valid target, and review the measurements it promises to produce.</span></p>
    <label>Measurement target<select value={target} onChange={(event) => setTarget(event.target.value)}>
      {state.system.bodies.map((body) => <option key={body.id} value={body.id}>{body.id === state.encounter?.target_id ? state.encounter?.npc ? `VESSEL: ${state.encounter.npc.vessel_name}` : state.encounter?.family === "artificial_signal" ? `SIGNAL SOURCE near ${body.name}` : `ENCOUNTER TARGET near ${body.name}` : `${body.name} · ${body.kind}`}</option>)}
    </select></label>
    <label>Scan purpose<select value={instrumentId} onChange={(event) => setInstrumentId(event.target.value)}>
      {scienceInstruments.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name} · {Math.round(candidate.condition * 100)}%</option>)}
    </select></label>
    {instrument && guidance && <div className="scan-purpose-card"><strong>{instrument.name}</strong><span><b>USE IT FOR</b>{guidance.use}</span><span><b>VALID TARGET</b>{guidance.target}</span><span><b>RESULTS</b>{guidance.results}</span><small>{instrument.power_mw} MW · instrument condition {Math.round(instrument.condition * 100)}%</small></div>}
    <div className="progress"><span style={{ width: `${state.ship.scan_progress * 100}%` }} /></div>
    <div className="gauge-bank two">
      <AnalogGauge label="Evidence depth" value={state.ship.scan_progress} maximum={1} nominal={.75} variation={state.ship.scan_progress > 0 && state.ship.scan_progress < 1 ? .006 : 0} sampleTimeMs={state.universe_time_ms} />
      <AnalogGauge label="Sensor stability" value={state.sensor_stability} maximum={1} nominal={.7} warning={.6} critical={.35} dangerWhen="low" variation={Math.max(.006, (1 - state.sensor_stability) * .04)} sampleTimeMs={state.universe_time_ms} />
    </div>
    <button className="primary" disabled={!target || !instrumentId} onClick={() => command("start_scan", { target_id: target, instrument_id: instrumentId })}>Run {instrument?.name ?? "selected scan"}</button>
    {state.ship.active_scan_target === state.encounter?.target_id && state.ship.scan_progress >= .75 && state.encounter?.status === "active" && <div className="next-action">
      <strong>{state.ship.scan_progress >= 1 ? "SURVEY COMPLETE" : "SUFFICIENT EVIDENCE"}</strong>
      <span>{state.encounter.requires_signal_analysis ? "Physical scan evidence is sufficient. Communications must now classify, demodulate, and interpret the carrier." : "Review the station readings, report correlations, then conclude the investigation."}</span>
      {state.encounter.npc || state.encounter.requires_signal_analysis ? <button className="primary" disabled={state.encounter.requires_signal_analysis && !state.encounter.signal_analysis_complete} onClick={() => command("resolve_encounter", { method: "investigation" })}>Conclude investigation</button> : <a href="#activities">Review observations and record conclusion</a>}
    </div>}
    {state.encounter?.status === "resolved" && <div className="next-action"><strong>SITUATION RESOLVED</strong><span>Recover available material, then Flight can select a neighboring system.</span></div>}
    <ScienceSignalWorkbench lab={state.signal_lab} command={command} />
    <StationReadings state={state} station="science" />
  </Panel>;
}

function CommunicationsSignalWorkbench({ lab, command, audio }: { lab: SignalLab | null; command: PanelProps["command"]; audio?: AudioControls }) {
  const [pcaOpen, setPcaOpen] = useState(false);
  useEffect(() => {
    if (lab?.analysis?.structure_result === "structured_but_contaminated" && !lab.analysis.pca_configured) setPcaOpen(true);
  }, [lab?.analysis?.structure_result, lab?.analysis?.pca_configured]);
  if (!lab) return null;
  if (lab.access === "archived") return <section className="signal-workbench archived-signal">
    <div className="contact-failure" role="status"><strong>LIVE SIGNAL ENDED · WORKSPACE RESET</strong><span>The waveform, PCA, demodulation, and translation panels were closed so retained data cannot be mistaken for a live carrier.</span></div>
    <div className="analysis-diagnostics">
      <Metric label="RECORDING" value={lab.recording_retained ? "RETAINED" : "NONE"} />
      <Metric label="LAST STRUCTURE" value={title(lab.analysis_summary?.structure_result ?? "not tested")} />
      <Metric label="PROCESSING LOG" value={`${lab.analysis_summary?.processing_steps ?? 0} steps`} />
    </div>
    <div className="button-row wrap">
      <button className="primary" disabled={!lab.recording_retained} onClick={() => command("open_signal_recording")}>Open retained recording</button>
      <button onClick={() => command("clear_signal_workspace")}>Keep data panels cleared</button>
    </div>
    <div className="localization-terminal"><strong>RECEIVER STATUS</strong><span>&gt; {lab.guidance}</span></div>
  </section>;
  if (lab.access !== "granted") return <div className="signal-workbench">
    <div className="localization-terminal"><strong>WIDEBAND RECEIVER</strong><span>&gt; {lab.guidance}</span></div>
    {lab.detected_frequency_mhz != null && <div className="frequency-readout locked"><span>SIGNAL AUTOMATICALLY RECEIVED</span><strong>{lab.detected_frequency_mhz.toFixed(3)} MHz</strong><small>The receiver has already locked and recorded this carrier.</small></div>}
    {lab.access === "available" && <button className="primary" onClick={() => command("acquire_signal")}>Activate automatic receiver</button>}
  </div>;
  const pca = lab.pca!;
  return <section className="signal-workbench">
    <h3>Received signal · {lab.detected_frequency_mhz?.toFixed(3)} MHz center · {lab.sample_rate_hz} samples/s baseband</h3>
    <div className="frequency-readout locked"><span>SIGNAL AUTOMATICALLY RECEIVED</span><strong>{lab.tuned_frequency_mhz?.toFixed(3)} MHz</strong><small>Carrier locked and recorded. Manual tuning is required only when transmitting.</small></div>
    {!lab.live && <div className="contact-failure" role="alert"><strong>LIVE CARRIER LOST</strong><span>This is a retained receiver recording. It can still be analyzed, but a reply can no longer establish contact.</span></div>}
    <div className="receiver-monitor">
      <div>
        <strong>AUDIBLE RECEIVER MONITOR</strong>
        <span>Baseband is frequency-shifted into hearing range. Compare raw and processed audio; this is not decoded speech.</span>
      </div>
      <div className="button-row wrap">
        <button onClick={() => audio?.playSignalMonitor(pca.raw_preview, lab.sample_rate_hz ?? 64)}>▶ Play raw signal</button>
        <button disabled={!lab.analysis?.pca_configured} onClick={() => audio?.playSignalMonitor(pca.reconstructed_preview, lab.sample_rate_hz ?? 64)}>▶ Play PCA selection</button>
        <button onClick={() => audio?.stopMonitor()}>■ Stop</button>
      </div>
    </div>
    <SignalAnnunciators analysis={lab.analysis} />
    <SpectrogramView data={lab.spectrogram!} />
    <WaveformView label="Raw channel 1" values={pca.raw_preview} />
    <div className="signal-stage">
      <header><span>1</span><strong>Test for repeatable structure</strong></header>
      <button onClick={() => command("test_signal_structure")}>Run periodicity and cyclostationary tests</button>
      {lab.analysis?.structure_result && <p className={`stage-result ${lab.analysis.structure_result}`}><strong>{title(lab.analysis.structure_result)}</strong><span>{percent(lab.analysis.structure_confidence)} confidence</span></p>}
    </div>
    <details className="advanced-analysis" open={pcaOpen} onToggle={(event) => setPcaOpen(event.currentTarget.open)}>
      <summary>PCA correlated-component separation {lab.analysis?.pca_configured ? "· configured" : "· optional"}</summary>
      <p className="muted">Use this only when the structure test reports correlated contamination. Click a gap, reconstruct one side, then rerun the structure test. Large variance is not automatically noise.</p>
      <PcaPartitionPlot values={pca.explained_variance} cutoff={pca.cutoff} selectedSide={pca.selected_side} onCutoff={(cutoff) => command("configure_pca", { cutoff, selected_side: pca.selected_side })} />
      <div className="loading-grid">{pca.loadings.map((loading, index) => <div key={index}><strong>PC{index + 1}</strong><span>{loading.map((value) => value.toFixed(2)).join(" · ")}</span></div>)}</div>
      <div className="pca-side-choice">
        <button className={pca.selected_side === "high_variance" ? "active" : ""} onClick={() => command("configure_pca", { cutoff: pca.cutoff, selected_side: "high_variance" })}>Reconstruct left · λ1–λ{pca.cutoff}<small>Higher-variance components</small></button>
        <button className={pca.selected_side === "low_variance" ? "active" : ""} onClick={() => command("configure_pca", { cutoff: pca.cutoff, selected_side: "low_variance" })}>Reconstruct right · λ{pca.cutoff + 1}–λ4<small>Lower-variance components</small></button>
      </div>
      {lab.analysis?.pca_configured && <button onClick={() => command("reset_pca")}>↶ Return to raw signal · undo PCA processing</button>}
      <WaveformView label={`Selected ${pca.selected_side.replace("_", "-")} PCA reconstruction`} values={pca.reconstructed_preview} />
      <button disabled={lab.analysis?.shared_with_science} onClick={() => command("share_signal_with_science")}>{lab.analysis?.shared_with_science ? "Derived dataset routed to Science" : "Route selected reconstruction to Science for optional physical analysis"}</button>
    </details>
    <div className="signal-stage">
      <header><span>2</span><strong>Choose a demodulator</strong></header>
      <p className="muted">Try a method and inspect frame confidence. A wrong method produces unstable symbols rather than a message.</p>
      <div className="button-row wrap">{(["amplitude", "frequency", "phase_shift", "pulse"] as const).map((method) => <button key={method} disabled={!lab.analysis?.structure_result || lab.analysis.structure_result === "noise_like"} className={lab.analysis?.demodulation_method === method ? "active" : ""} onClick={() => command("attempt_demodulation", { method })}>{title(method)}</button>)}</div>
      {lab.analysis?.demodulation_method && <p className={`stage-result ${lab.analysis.demodulation_confidence >= .55 ? "success" : "failure"}`}><strong>{lab.analysis.demodulation_confidence >= .55 ? "Stable frame" : "Frame lock failed"}</strong><span>{percent(lab.analysis.demodulation_confidence)} confidence</span></p>}
      {lab.analysis?.symbol_preview && <pre className="symbol-preview">{lab.analysis.symbol_preview}</pre>}
    </div>
    <div className="signal-stage">
      <header><span>3</span><strong>Universal Translator</strong></header>
      <p className="muted">The translator accepts recovered symbols—not receiver audio. It identifies framing and syntax, applies the ship’s language corpus and encounter context, then renders a plain-language meaning with confidence.</p>
      <button disabled={!lab.analysis?.demodulation_method} onClick={() => command("run_universal_translator")}>Run Universal Translator</button>
      {lab.analysis?.translation_status !== "idle" && <div className="translator-diagnostics">
        <Metric label="INPUT" value={(lab.analysis?.demodulation_confidence ?? 0) >= .55 ? "STABLE FRAME" : "REJECTED"} />
        <Metric label="PROTOCOL" value={lab.analysis?.translation_protocol || "UNRESOLVED"} />
        <Metric label="CONFIDENCE" value={percent(lab.analysis?.interpretation_confidence ?? 0)} />
      </div>}
      {lab.analysis?.interpretation && <blockquote className={lab.analysis.interpretation_confidence >= .55 ? "interpreted-message" : "nonsense-message"}><strong>{lab.analysis.interpretation_confidence >= .55 ? "PLAIN-LANGUAGE RENDERING" : "TRANSLATION REJECTED"} · {percent(lab.analysis.interpretation_confidence)} confidence</strong>{lab.analysis.interpretation}<small>{lab.analysis.translation_notes}</small></blockquote>}
    </div>
    {lab.live && lab.analysis?.reply_acknowledgment && <p className="stage-result success"><strong>Contact established</strong><span>{lab.analysis.reply_acknowledgment}</span></p>}
    <div className="localization-terminal"><strong>ANALYSIS GUIDANCE</strong><span>&gt; {lab.guidance}</span></div>
    {lab.analysis?.science_note && <p className="readout">Science note <strong>{lab.analysis.science_note}</strong></p>}
  </section>;
}

function ScienceSignalWorkbench({ lab, command }: { lab: SignalLab | null; command: PanelProps["command"] }) {
  const [epsilon, setEpsilon] = useState(lab?.analysis?.dmaps_epsilon ?? 1);
  const [diffusionTime, setDiffusionTime] = useState(lab?.analysis?.dmaps_diffusion_time ?? 1);
  const [neighbors, setNeighbors] = useState(lab?.analysis?.dmaps_neighbors ?? 5);
  const [note, setNote] = useState("");
  useEffect(() => setEpsilon(lab?.analysis?.dmaps_epsilon ?? 1), [lab?.analysis?.dmaps_epsilon]);
  useEffect(() => setDiffusionTime(lab?.analysis?.dmaps_diffusion_time ?? 1), [lab?.analysis?.dmaps_diffusion_time]);
  useEffect(() => setNeighbors(lab?.analysis?.dmaps_neighbors ?? 5), [lab?.analysis?.dmaps_neighbors]);
  if (lab?.access === "archived") return <p className="muted">The live carrier ended and Science data panels were reset. Communications can reopen the retained recording and route a new derived dataset if further analysis is useful.</p>;
  if (!lab || lab.access !== "granted") return <p className="muted">Communications owns signal decoding. Optional derived physical-analysis data will appear here only when Communications routes it.</p>;
  const dmaps = lab.dmaps!;
  return <details className="advanced-analysis science-advanced"><summary>Advanced residual-state analysis · optional</summary><section className="signal-workbench">
    <h3>Routed reconstruction · diffusion maps</h3>
    <p className="analysis-interpretation"><strong>When to use this:</strong> Communications has isolated a residual but needs Science to determine whether recurring states follow a physical manifold, instrument response, or isolated impulses. It does not decode messages.</p>
    <p className="muted">These are signal states, not physical positions. Nearby points have similar four-channel measurements; the connecting line shows time order. Red points are statistically isolated candidates—not automatically artifacts.</p>
    <DiffusionMapView points={dmaps.embedding} outliers={dmaps.outlier_indices} />
    <div className="analysis-diagnostics">
      <Metric label="ISOLATED" value={percent(dmaps.outlier_fraction)} />
      <Metric label="TIME CONTINUITY" value={percent(dmaps.temporal_continuity)} />
      <Metric label="DIMENSIONS" value={String(dmaps.dominant_dimensions)} />
    </div>
    <p className="analysis-interpretation">{dmaps.interpretation}</p>
    <EigenvalueView values={dmaps.eigenvalues.map((value) => Math.max(0, value))} label="Diffusion eigenvalues" />
    <div className="analysis-controls">
      <label>Kernel bandwidth ε <output>{epsilon.toFixed(1)}</output><input type="range" min=".1" max="4" step=".1" value={epsilon} onChange={(event) => setEpsilon(Number(event.target.value))} /></label>
      <label>Diffusion time <output>{diffusionTime}</output><input type="range" min="1" max="8" step="1" value={diffusionTime} onChange={(event) => setDiffusionTime(Number(event.target.value))} /></label>
      <label>Reconstruction neighbors <output>{neighbors}</output><input type="range" min="2" max="12" step="1" value={neighbors} onChange={(event) => setNeighbors(Number(event.target.value))} /></label>
    </div>
    <button onClick={() => command("configure_dmaps", { epsilon, diffusion_time: diffusionTime, neighbors })}>Recompute embedding</button>
    <WaveformView label="Manifold-neighbor reconstruction" values={dmaps.denoised_preview} />
    <label>Physical interpretation note<textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="State what the geometry supports and what remains uncertain." /></label>
    <div className="button-row wrap">
      {["natural_contamination", "instrument_artifact", "structured_residual", "inconclusive"].map((classification) => <button key={classification} className={lab.analysis?.science_classification === classification ? "active" : ""} onClick={() => command("classify_signal", { classification, note })}>{title(classification)}</button>)}
    </div>
    <div className="localization-terminal"><strong>ANALYSIS GUIDANCE</strong><span>&gt; {lab.guidance}</span></div>
  </section></details>;
}

function WaveformView({ label, values }: { label: string; values: number[] }) {
  const width = 640;
  const height = 120;
  const maximum = Math.max(.001, ...values.map((value) => Math.abs(value)));
  const path = values.map((value, index) => `${index ? "L" : "M"} ${(index / Math.max(1, values.length - 1)) * width} ${height / 2 - value / maximum * height * .42}`).join(" ");
  return <figure className="analysis-plot"><figcaption>{label}</figcaption><svg viewBox={`0 0 ${width} ${height}`}><line x1="0" y1={height / 2} x2={width} y2={height / 2} /><path d={path} /></svg></figure>;
}

function SpectrogramView({ data }: { data: NonNullable<SignalLab["spectrogram"]> }) {
  const bins = data.frames[0]?.length ?? 1;
  return <figure className="analysis-plot spectrogram"><figcaption>Spectrogram · Hann {data.window_size} · Δf {data.frequency_bin_hz.toFixed(1)} Hz</figcaption><svg viewBox={`0 0 ${Math.max(1, data.frames.length)} ${bins}`} preserveAspectRatio="none">
    {data.frames.flatMap((frame, x) => frame.map((value, bin) => <rect key={`${x}-${bin}`} x={x} y={bins - bin - 1} width="1.05" height="1.05" style={{ opacity: Math.max(.04, value) }} />))}
  </svg></figure>;
}

function EigenvalueView({ values, label = "PCA explained variance" }: { values: number[]; label?: string }) {
  const maximum = Math.max(.001, ...values);
  return <figure className="eigenvalue-plot"><figcaption>{label}</figcaption><div>{values.map((value, index) => <span key={index} style={{ height: `${Math.max(3, value / maximum * 100)}%` }}><i>λ{index + 1}</i><b>{(value * 100).toFixed(1)}%</b></span>)}</div></figure>;
}

function PcaPartitionPlot({ values, cutoff, selectedSide, onCutoff }: { values: number[]; cutoff: number; selectedSide: "high_variance" | "low_variance"; onCutoff: (cutoff: number) => void }) {
  const width = 560;
  const height = 190;
  const left = 45;
  const right = width - 25;
  const top = 20;
  const bottom = height - 35;
  const maximum = Math.max(.001, ...values);
  const locations = values.map((value, index) => ({ x: left + index / Math.max(1, values.length - 1) * (right - left), y: bottom - value / maximum * (bottom - top) }));
  const curve = locations.map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`).join(" ");
  const dividerX = (locations[cutoff - 1].x + locations[cutoff].x) / 2;
  return <figure className="pca-partition"><figcaption>PCA scree curve · click a gap</figcaption><svg viewBox={`0 0 ${width} ${height}`}>
    <rect className={selectedSide === "high_variance" ? "selected-region" : "partition-region"} x={left - 18} y={top - 8} width={dividerX - left + 18} height={bottom - top + 18} />
    <rect className={selectedSide === "low_variance" ? "selected-region" : "partition-region"} x={dividerX} y={top - 8} width={right - dividerX + 18} height={bottom - top + 18} />
    <line className="partition-divider" x1={dividerX} y1={top - 8} x2={dividerX} y2={bottom + 10} />
    <path d={curve} />
    {locations.map((point, index) => <g key={index}><circle cx={point.x} cy={point.y} r="6" /><text x={point.x} y={bottom + 25} textAnchor="middle">λ{index + 1}</text><text x={point.x} y={point.y - 11} textAnchor="middle">{percent(values[index])}</text></g>)}
    {[1, 2, 3].map((gap) => {
      const x1 = locations[gap - 1].x;
      const x2 = locations[gap].x;
      return <rect key={gap} className="gap-target" x={x1 + 8} y={top - 8} width={x2 - x1 - 16} height={bottom - top + 18} onClick={() => onCutoff(gap)}><title>Partition between λ{gap} and λ{gap + 1}</title></rect>;
    })}
  </svg><small>Cutoff between λ{cutoff} and λ{cutoff + 1}</small></figure>;
}

function DiffusionMapView({ points, outliers }: { points: NonNullable<SignalLab["dmaps"]>["embedding"]; outliers: number[] }) {
  const extent = Math.max(.00001, ...points.flatMap((point) => [Math.abs(point.x), Math.abs(point.y)]));
  const plotted = points.map((point) => ({ x: 200 + point.x / extent * 180, y: 130 - point.y / extent * 110 }));
  return <figure className="analysis-plot diffusion-map"><figcaption>Diffusion coordinates ψ₁ / ψ₂</figcaption><svg viewBox="0 0 400 260">
    <line x1="200" y1="0" x2="200" y2="260" /><line x1="0" y1="130" x2="400" y2="130" />
    <polyline points={plotted.map((point) => `${point.x},${point.y}`).join(" ")} />
    {points.map((point, index) => <circle key={index} className={outliers.includes(index) ? "outlier" : "main-state"} cx={plotted[index].x} cy={plotted[index].y} r={outliers.includes(index) ? 5.5 : 3.5} style={{ opacity: .45 + index / Math.max(1, points.length) * .55 }}><title>t={point.time_s}s · amplitude {point.amplitude} · {outliers.includes(index) ? "isolated candidate" : "main trajectory"}</title></circle>)}
  </svg></figure>;
}

function SystemMapPanel({ state, command }: PanelProps) {
  const [scale, setScale] = useState<"local" | "system">("local");
  const localization = state.localization;
  const ship = state.ship;
  const width = 800;
  const height = 500;
  const centerX = width / 2;
  const centerY = height / 2;
  const bodyPositions = state.system.bodies.map((body) => {
    const fallbackAngle = [...body.id].reduce((sum, character) => sum + character.charCodeAt(0), 0) % 360;
    const fallbackRadius = body.orbit_index * 35_000_000;
    return {
      ...body,
      x: Number(body.properties.x_km ?? Math.cos(fallbackAngle * Math.PI / 180) * fallbackRadius),
      y: Number(body.properties.y_km ?? Math.sin(fallbackAngle * Math.PI / 180) * fallbackRadius),
    };
  });
  const systemExtent = Math.max(1, ...bodyPositions.flatMap((body) => [Math.abs(body.x), Math.abs(body.y)])) * 1.12;
  const estimateRange = localization?.estimated_x_km != null && localization.estimated_y_km != null
    ? Math.hypot(localization.estimated_x_km - ship.x_km, localization.estimated_y_km - ship.y_km) + (localization.uncertainty_radius_km ?? 0)
    : 0;
  const firstBearing = localization?.measurements[0];
  const baselineView = scale === "local" && localization?.measurements.length === 1 && firstBearing;
  const extent = scale === "system" ? systemExtent : baselineView ? 5_000 : Math.max(120_000, estimateRange * 1.18);
  const originX = scale === "system" ? 0 : baselineView ? firstBearing.origin_x_km : ship.x_km;
  const originY = scale === "system" ? 0 : baselineView ? firstBearing.origin_y_km : ship.y_km;
  const plotScale = Math.min(width, height) * .44 / extent;
  const point = (x: number, y: number): [number, number] => [centerX + (x - originX) * plotScale, centerY - (y - originY) * plotScale];
  const [shipX, shipY] = point(ship.x_km, ship.y_km);
  const baselineHeading = firstBearing ? (firstBearing.bearing_deg + 90) % 360 : null;
  const canFly = state.station === "integrated" || state.station === "flight" || state.station === "command";
  return <Panel title="System position model" code="MAP" wide>
    <div className="map-toolbar">
      <div className="button-row">
        <button className={scale === "local" ? "active" : ""} onClick={() => setScale("local")}>Local geometry</button>
        <button className={scale === "system" ? "active" : ""} onClick={() => setScale("system")}>System model</button>
      </div>
      <span>{baselineView ? "FIXED BASELINE FRAME" : scale === "local" ? "SHIP-CENTERED LOCAL FRAME" : "SYSTEM FRAME"} · {scale === "local" ? `±${Math.round(extent).toLocaleString()} km` : `±${(extent / 149_597_870.7).toFixed(2)} AU`}</span>
    </div>
    <svg className="system-map" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Position model showing the ship, known bodies, measured bearings, and source probability region">
      <defs>
        <pattern id="map-grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M 40 0 L 0 0 0 40" /></pattern>
        <filter id="probability-blur"><feGaussianBlur stdDeviation="12" /></filter>
      </defs>
      <rect width={width} height={height} className="map-background" />
      <rect width={width} height={height} fill="url(#map-grid)" className="map-grid" />
      {[.25, .5, .75, 1].map((fraction) => <circle key={fraction} cx={centerX} cy={centerY} r={Math.min(width, height) * .44 * fraction} className="range-ring" />)}
      {bodyPositions.map((body) => {
        const [x, y] = point(body.x, body.y);
        if (x < -20 || x > width + 20 || y < -20 || y > height + 20) return null;
        return <g key={body.id} className={`map-body ${body.kind}`} transform={`translate(${x} ${y})`}>
          <circle r={body.kind === "star" ? 8 : body.kind === "belt" ? 4 : 5} />
          <text x="9" y="-7">{body.name}</text>
        </g>;
      })}
      {state.contacts.map((contact) => {
        const [x, y] = point(contact.x_km, contact.y_km);
        if (x < -20 || x > width + 20 || y < -20 || y > height + 20) return null;
        return <g key={contact.id} className={`radar-contact ${contact.status}`} transform={`translate(${x} ${y})`}>
          <circle className="contact-pulse" r="13" /><circle className="contact-dot" r="5" />
          <text x="11" y="-9">{contact.label} · {Math.round(contact.range_km).toLocaleString()} km</text>
        </g>;
      })}
      {localization?.measurements.map((measurement) => {
        const [x1, y1] = point(measurement.origin_x_km, measurement.origin_y_km);
        const angle = measurement.bearing_deg * Math.PI / 180;
        const spread = measurement.angular_uncertainty_deg * Math.PI / 180;
        const rayLength = extent * 1.8 * plotScale;
        return <g key={measurement.id} className="bearing-line">
          <polygon className="bearing-cone" points={`${x1},${y1} ${x1 + Math.cos(angle - spread) * rayLength},${y1 - Math.sin(angle - spread) * rayLength} ${x1 + Math.cos(angle + spread) * rayLength},${y1 - Math.sin(angle + spread) * rayLength}`} />
          <circle cx={x1} cy={y1} r="3" />
          <line x1={x1} y1={y1} x2={x1 + Math.cos(angle) * rayLength} y2={y1 - Math.sin(angle) * rayLength} />
          <text x={x1 + 7} y={y1 + 14}>{measurement.bearing_deg.toFixed(2)}° ±{measurement.angular_uncertainty_deg.toFixed(2)}°</text>
        </g>;
      })}
      {localization?.estimated_x_km != null && localization.estimated_y_km != null && (() => {
        const [x, y] = point(localization.estimated_x_km, localization.estimated_y_km);
        const radius = Math.max(8, Math.min(130, (localization.uncertainty_radius_km ?? 500) * plotScale));
        return <g className="probability-region">
          <circle cx={x} cy={y} r={radius} filter="url(#probability-blur)" />
          <ellipse cx={x} cy={y} rx={radius * 1.25} ry={radius * .72} />
          <circle cx={x} cy={y} r="5" />
          <text x={x + 10} y={y - radius - 5}>SOURCE REGION · {percent(localization.confidence)}</text>
        </g>;
      })()}
      <g className="ship-marker" transform={`translate(${shipX} ${shipY}) rotate(${90 - ship.heading_deg})`}>
        <path d="M 0 -11 L 8 9 L 0 5 L -8 9 Z" />
        <circle r="15" />
      </g>
      <text x={shipX + 18} y={shipY + 5} className="ship-label">{ship.name}</text>
    </svg>
    <div className="map-legend"><span className="ship-key">SHIP</span><span className="contact-key">TRACKED VESSEL</span><span className="source-key">SOURCE PROBABILITY</span><span className="bearing-key">MEASURED BEARING</span></div>
    <div className="localization-terminal" role="status">
      <strong>LOCALIZATION COMPUTER</strong>
      <span>&gt; {localization?.guidance ?? "NO ACTIVE SOURCE."}</span>
      <span>&gt; BEARINGS {localization?.measurements.length ?? 0} · BASELINE {(localization?.baseline_km ?? 0).toLocaleString()} KM · CONFIDENCE {percent(localization?.confidence ?? 0)}</span>
      <span>&gt; POSITION X {ship.x_km.toFixed(0)} KM · Y {ship.y_km.toFixed(0)} KM · SPEED {ship.velocity_km_s.toFixed(1)} KM/S</span>
      {state.contacts.map((contact) => <span key={contact.id}>&gt; RADAR {contact.label.toUpperCase()} · BEARING {contact.bearing_deg.toFixed(1)}° · RANGE {Math.round(contact.range_km).toLocaleString()} KM · {contact.status.toUpperCase()}</span>)}
      {ship.baseline_target_km > 0 && <span>&gt; AUTOPILOT {ship.baseline_autobraking ? "BRAKING" : "ACCELERATING"} · PLANNED BASELINE {ship.baseline_target_km.toLocaleString()} KM</span>}
    </div>
    {canFly && <div className="button-row wrap">
      {baselineHeading != null && (localization?.measurements.length ?? 0) === 1 && <button disabled={ship.baseline_target_km > 0} onClick={() => command("set_flight", { heading_deg: baselineHeading, throttle: 1, baseline_distance_km: 2_000 })}>{ship.baseline_target_km > 0 ? "Measurement maneuver active" : `Execute 2,000 km baseline · ${baselineHeading.toFixed(0)}°`}</button>}
      {localization?.intercept_heading_deg != null && <button className="primary" onClick={() => command("set_flight", { heading_deg: localization.intercept_heading_deg, throttle: .25 })}>Set estimated intercept · {localization.intercept_heading_deg.toFixed(1)}°</button>}
    </div>}
  </Panel>;
}

function CommunicationsPanel({ state, command, audio, requestActivity }: PanelProps) {
  const [message, setMessage] = useState("");
  const [question, setQuestion] = useState("");
  const [contactFrequency, setContactFrequency] = useState("");
  const [channelId, setChannelId] = useState("local");
  const localAvailable = state.encounter?.status === "active" && Boolean(state.encounter.npc || state.signal_lab?.live);
  const remote = (state.remote_channels ?? []).find(channel => channel.thread_id === channelId);
  const translated = Boolean(state.signal_lab?.live && (state.signal_lab.analysis?.interpretation_confidence ?? 0) >= .55);
  useEffect(() => {setChannelId(localAvailable ? "local" : state.remote_channels?.[0]?.thread_id ?? "local"); setContactFrequency("");}, [state.ship.system_id]);
  const frequency = remote?.frequency_mhz ?? state.ship.detected_signal_frequency_mhz;
  const canSend = Boolean(remote || (localAvailable && (state.encounter?.npc || translated)));
  return <Panel title="Communications" code="COM">
    <p className="role-boundary"><strong>INFORMATION CHANNEL</strong><span>Acquire carriers, separate mixed components, recover symbols, and route physical questions to Science.</span></p>
    {state.ship.detected_signal_frequency_mhz != null && <div className="frequency-readout locked"><span>INCOMING TRANSMISSION AUTOMATICALLY RECEIVED</span><strong>{state.ship.detected_signal_frequency_mhz.toFixed(3)} MHz</strong><small>{state.encounter?.npc?.vessel_name ?? "Unidentified source"}</small></div>}
    {requestActivity && <RequestActivity activity={requestActivity} compact />}
    <form aria-label="Message transmitter" onSubmit={event => {event.preventDefault(); command(remote ? "reply_remote_contact" : translated ? "send_signal_reply" : "transmit", {message, frequency_mhz: Number(contactFrequency), ...(remote ? {thread_id: remote.thread_id} : {})});}}>
      <label>Conversation channel<select value={channelId} onChange={event => {setChannelId(event.target.value); setContactFrequency("");}}><option value="local">{localAvailable ? state.encounter?.npc?.vessel_name ?? "Local signal" : "No live local contact"}</option>{(state.remote_channels ?? []).map(channel => <option key={channel.thread_id} value={channel.thread_id}>Remote · {channel.name}</option>)}</select></label>
      <p>{remote ? "Remote radio channel · replies remain in the conversation history." : "Local channel"} · {frequency?.toFixed(3) ?? "—"} MHz</p>
      {remote && <details open><summary>Remote conversation history</summary>{remote.messages.map((text, index) => <p key={index}>{text}</p>)}</details>}
      <label>Transmit frequency · MHz<input inputMode="decimal" value={contactFrequency} onChange={event => setContactFrequency(event.target.value)} placeholder="Enter displayed channel frequency" /></label>
      <label>Plain-language reply<textarea value={message} onChange={event => setMessage(event.target.value)} placeholder="State your purpose or ask a question…" /></label>
      <button className="primary" disabled={!canSend || !message.trim() || !contactFrequency.trim() || requestActivity?.state === "waiting"}>Transmit and wait for response</button>
      {!canSend && <p>Receive and translate a local signal, or select a remote contact above.</p>}
    </form>
    <CommunicationsSignalWorkbench lab={state.signal_lab} command={command} audio={audio} />
    {state.encounter?.npc && <p className="contact"><strong>{state.encounter.npc.vessel_name} · {state.encounter.npc.relationship}</strong><span>{state.encounter.npc.activity}</span><span>{state.encounter.npc.current_request || "No explicit request"}</span></p>}
    <div className="transcript" aria-live="polite">{state.messages.map((entry, index) => <p key={`${entry.time_ms}-${index}`}><strong>{entry.speaker}</strong>{entry.message}</p>)}</div>
    <form className="computer-query" onSubmit={(event) => { event.preventDefault(); command("ask_computer", { question }); setQuestion(""); }}>
      <label>Ask Ship Computer<input value={question} onChange={(event) => setQuestion(event.target.value)} /></label>
      <button disabled={!question.trim() || requestActivity?.state === "waiting"}>Ask</button>
    </form>
    <StationReadings state={state} station="communications" />
  </Panel>;
}

function TacticalPanel({ state, command }: PanelProps) {
  const control = state.weapon_control;
  const commonBlocked = !control?.solution || !control.solution.in_range || state.ship.power.weapons < .04 || state.ship.weapon_cooldown_s > 0;
  const canWarning = Boolean(control && !commonBlocked && control.charge >= control.required_charge.warning);
  const canPrecision = Boolean(control && !commonBlocked && control.authorized && (control.solution?.lock_quality ?? 0) >= .25 && control.charge >= control.required_charge.precision && (control.selected_weapon !== "kinetic_interceptor" || control.kinetic_ammunition > 0));
  const canFull = Boolean(control && !commonBlocked && control.authorized && (control.solution?.lock_quality ?? 0) >= .25 && control.charge >= control.required_charge.full && (control.selected_weapon !== "kinetic_interceptor" || control.kinetic_ammunition > 0));
  return <Panel title="Tactical" code="TAC">
    <div className="gauge-bank two">
      <AnalogGauge label="Defensive field" value={state.ship.shields} maximum={1} nominal={.8} warning={.5} critical={.2} dangerWhen="low" variation={state.ship.defensive_posture ? .004 : 0} sampleTimeMs={state.universe_time_ms} />
      <AnalogGauge label="Hull integrity" value={state.ship.hull} maximum={1} nominal={.75} warning={.7} critical={.4} dangerWhen="low" />
    </div>
    <p className="readout">Contact posture <strong>{state.encounter?.phase.toUpperCase() ?? "NONE"}</strong></p>
    {control && <section className="weapon-console">
      <header><strong>FIRE CONTROL</strong><span className={control.authorized ? "authorized" : "safe"}>{control.authorized ? "RELEASE AUTHORIZED" : "WEAPONS SAFE"}</span></header>
      <div className="gauge-bank two">
        <AnalogGauge label="Weapon charge" value={control.charge} maximum={1} nominal={.8} warning={.3} critical={.15} dangerWhen="low" />
        <AnalogGauge label="Target lock" value={control.solution?.lock_quality ?? 0} maximum={1} nominal={.7} warning={.4} critical={.25} dangerWhen="low" variation={.008} sampleTimeMs={state.universe_time_ms} />
      </div>
      <label>Installed weapon<select value={control.selected_weapon} onChange={(event) => command("configure_weapon", { weapon: event.target.value })}>
        <option value="focused_energy">Focused Energy Projector · rechargeable · 125,000 km</option>
        <option value="kinetic_interceptor">Kinetic Interceptor · {control.kinetic_ammunition} rounds · 70,000 km</option>
      </select></label>
      <div className="fire-solution">
        <span>RANGE <strong>{control.solution ? `${Math.round(control.solution.range_km).toLocaleString()} km` : "NO TARGET"}</strong></span>
        <span>MAX RANGE <strong>{control.solution ? `${control.solution.max_range_km.toLocaleString()} km` : "—"}</strong></span>
        <span>TIME OF FLIGHT <strong>{control.solution ? `${control.solution.time_of_flight_s.toFixed(1)}s` : "—"}</strong></span>
        <span>COOLDOWN <strong>{control.cooldown_s.toFixed(1)}s</strong></span>
      </div>
      {state.station === "integrated" && <button className={control.authorized ? "danger active" : ""} onClick={() => command("set_weapons_authorization", { authorized: !control.authorized })}>{control.authorized ? "Revoke weapons release" : "Authorize weapons release"}</button>}
      {control.blockers.length > 0 && <div className="weapon-blockers"><strong>FIRING PREREQUISITES</strong>{control.blockers.map((blocker) => <span key={blocker}>× {blocker}</span>)}</div>}
      <div className="button-row wrap">
        <button disabled={!canWarning} onClick={() => command("fire_weapon", { mode: "warning" })}>Warning discharge · 15%</button>
        <button className="danger" disabled={!canPrecision} onClick={() => command("fire_weapon", { mode: "precision" })}>Precision fire · 45%</button>
        <button className="danger" disabled={!canFull} onClick={() => command("fire_weapon", { mode: "full" })}>Full discharge · 80%</button>
      </div>
      <p className="readout">Last result <strong>{control.last_result}</strong></p>
      {control.target_damage && <p className="readout">Estimated target condition <strong>field {percent(control.target_damage.estimated_shields)} · hull {percent(control.target_damage.estimated_hull)} · {percent(control.target_damage.confidence)} confidence</strong></p>}
    </section>}
    <div className="button-row">
      <button className={state.ship.defensive_posture ? "active" : "primary"} onClick={() => command("raise_shields", { level: state.ship.defensive_posture ? 0 : 1 })}>{state.ship.defensive_posture ? "Defensive field active" : "Raise defensive field"}</button>
    </div>
    <p className="muted">Direct fire requires Command authorization. Weapon power controls charge rate and shot strength; Sensors controls lock quality; Cooling controls recovery and firing heat.</p>
    <StationReadings state={state} station="tactical" />
  </Panel>;
}

function StationReadings({ state, station }: { state: Projection; station: Station }) {
  const readings = station === "command"
    ? state.observations
    : state.observations.filter((observation) => observation.station === station);
  return <section className="station-readings">
    <h3>{station === "command" ? "Verified crew data" : `${title(station)} sensor readings`}</h3>
    {readings.length === 0 ? <p className="muted">No qualified readings yet.</p> : <div className="observation-list">
      {readings.slice().reverse().map((observation) => <article key={observation.id}>
        <span>{title(observation.station)} · {percent(observation.confidence)} confidence</span>
        <strong>{observation.measurement}</strong>
        <output>{displayObservation(observation, state.universe_time_ms, state.sensor_stability)}</output>
        {observation.measurement === "weapon system likelihood" && <small>Estimated evidence of weapons, not proof of hostile intent. Compare with the contact's actions and other readings.</small>}
        {observation.measurement.includes("propulsion confidence") && <small>Evidence of active power and propulsion; this does not measure maximum speed or weapon strength.</small>}
      </article>)}
    </div>}
    {state.crew_knowledge.length > 0 && <><h3>Crew knowledge</h3><ul>{state.crew_knowledge.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
  </section>;
}

function SignalAnnunciators({ analysis }: { analysis: SignalLab["analysis"] }) {
  const structured = analysis?.structure_result && analysis.structure_result !== "noise_like" && analysis.structure_result !== "inconclusive";
  const frameAttempted = Boolean(analysis?.demodulation_method);
  const frameLocked = (analysis?.demodulation_confidence ?? 0) >= .55;
  const interpreted = (analysis?.interpretation_confidence ?? 0) >= .55;
  return <div className="signal-annunciators" aria-label="Receiver status lights">
    <span className="annunciator on"><i />CARRIER</span>
    <span className={`annunciator ${structured ? "on" : analysis?.structure_result ? "fault" : ""}`}><i />STRUCTURE</span>
    <span className={`annunciator ${frameLocked ? "on" : frameAttempted ? "fault flash" : ""}`}><i />FRAME LOCK</span>
    <span className={`annunciator ${interpreted ? "on" : ""}`}><i />MESSAGE</span>
  </div>;
}

function AnnunciatorPanel(props: {
  alerts: Projection["alerts"];
  acknowledged: Set<string>;
  audioEnabled: boolean;
  clockTickEnabled: boolean;
  onEnableAudio: () => void;
  onToggleMute: () => void;
  onToggleTick: () => void;
  onAcknowledge: () => void;
}) {
  const caution = props.alerts.some((alert) => alert.severity === "caution" && !props.acknowledged.has(alertKey(alert)));
  const critical = props.alerts.some((alert) => alert.severity === "critical" && !props.acknowledged.has(alertKey(alert)));
  return <section className="annunciator-panel" aria-label="Master alert and audio controls">
    <button className={`master-lamp caution ${caution ? "lit" : ""}`} onClick={props.onAcknowledge} aria-pressed={caution}><i />MASTER CAUTION</button>
    <button className={`master-lamp warning ${critical ? "lit" : ""}`} onClick={props.onAcknowledge} aria-pressed={critical}><i />MASTER WARNING</button>
    <button className={props.audioEnabled ? "audio-toggle active" : "audio-toggle"} onClick={props.audioEnabled ? props.onToggleMute : props.onEnableAudio}>{props.audioEnabled ? "🔊 Console audio on" : "🔇 Enable console audio"}</button>
    <button className={props.clockTickEnabled ? "audio-toggle active" : "audio-toggle"} onClick={props.onToggleTick}>Clock tick {props.clockTickEnabled ? "on" : "off"}</button>
    <button disabled={!caution && !critical} onClick={props.onAcknowledge}>Acknowledge</button>
  </section>;
}

function AlertStack({ alerts, acknowledged }: { alerts: Projection["alerts"]; acknowledged: Set<string> }) {
  if (!alerts.length) return null;
  return <section className="alert-stack" aria-live="assertive">
    {alerts.map((alert, index) => <div key={`${alert.source}-${alert.message}-${index}`} className={`ship-alert ${alert.severity} ${acknowledged.has(alertKey(alert)) ? "acknowledged" : ""}`} role={alert.severity === "critical" ? "alert" : "status"}>
      <i aria-hidden="true" /><span>{alert.source}</span><strong>{alert.message}</strong>
    </div>)}
  </section>;
}

type AnalogGaugeProps = {
  label: string;
  value: number;
  minimum?: number;
  maximum: number;
  nominal: number;
  warning?: number;
  critical?: number;
  dangerWhen?: "high" | "low";
  variation?: number;
  sampleTimeMs?: number;
};

function AnalogGauge({ label, value, minimum = 0, maximum, nominal, warning, critical, dangerWhen = "high", variation = 0, sampleTimeMs = 0 }: AnalogGaugeProps) {
  const labelPhase = [...label].reduce((sum, character) => sum + character.charCodeAt(0), 0);
  const indicatedValue = Math.min(maximum, Math.max(minimum, value + Math.sin(sampleTimeMs / 390 + labelPhase) * variation));
  const fraction = normalizeGauge(indicatedValue, minimum, maximum);
  const nominalFraction = normalizeGauge(nominal, minimum, maximum);
  const level = gaugeLevel(indicatedValue, warning, critical, dangerWhen);
  const [needleX, needleY] = gaugePoint(fraction, 66);
  const [markerOuterX, markerOuterY] = gaugePoint(nominalFraction, 83);
  const [markerInnerX, markerInnerY] = gaugePoint(nominalFraction, 71);
  const formatValue = `${Math.round(indicatedValue * 100)}%`;
  const arcPath = "M 18 100 A 82 82 0 0 1 182 100";
  return <figure className={`analog-gauge ${level}`} aria-label={`${label}: ${formatValue}; nominal limit ${Math.round(nominal * 100)} percent; status ${level}`}>
    <div className="gauge-lamp" aria-hidden="true" />
    <svg viewBox="0 0 200 122" role="img" aria-hidden="true">
      <path className="gauge-track" d={arcPath} pathLength="100" />
      <path className="gauge-zone nominal-zone" d={arcPath} pathLength="100" strokeDasharray={`${nominalFraction * 100} 100`} />
      {dangerWhen === "high" && warning !== undefined && <path className="gauge-zone caution-zone high" d={arcPath} pathLength="100" strokeDasharray={`${(1 - normalizeGauge(warning, minimum, maximum)) * 100} 100`} strokeDashoffset={`${-normalizeGauge(warning, minimum, maximum) * 100}`} />}
      {dangerWhen === "low" && warning !== undefined && <path className="gauge-zone caution-zone" d={arcPath} pathLength="100" strokeDasharray={`${normalizeGauge(warning, minimum, maximum) * 100} 100`} />}
      {dangerWhen === "high" && critical !== undefined && <path className="gauge-zone critical-zone high" d={arcPath} pathLength="100" strokeDasharray={`${(1 - normalizeGauge(critical, minimum, maximum)) * 100} 100`} strokeDashoffset={`${-normalizeGauge(critical, minimum, maximum) * 100}`} />}
      {dangerWhen === "low" && critical !== undefined && <path className="gauge-zone critical-zone" d={arcPath} pathLength="100" strokeDasharray={`${normalizeGauge(critical, minimum, maximum) * 100} 100`} />}
      <line className="nominal-marker" x1={markerInnerX} y1={markerInnerY} x2={markerOuterX} y2={markerOuterY} />
      <line className="gauge-needle" x1="100" y1="100" x2={needleX} y2={needleY} />
      <circle className="gauge-pivot" cx="100" cy="100" r="6" />
      <text className="gauge-min" x="18" y="117">{Math.round(minimum * 100)}</text>
      <text className="gauge-max" x="182" y="117" textAnchor="end">{Math.round(maximum * 100)}</text>
    </svg>
    <figcaption><span>{label}</span><strong>{formatValue}</strong><small>Nominal line {Math.round(nominal * 100)}%</small></figcaption>
  </figure>;
}

function displayObservation(observation: Projection["observations"][number], universeTimeMs: number, stability: number): string {
  if (typeof observation.value !== "number") return String(observation.value);
  const hash = [...observation.id].reduce((sum, character) => sum + character.charCodeAt(0), 0);
  const amplitude = Math.max(Math.abs(observation.value), 1) * (1 - stability) * .035;
  const phase = universeTimeMs / 420 + hash;
  const displayed = observation.value + Math.sin(phase) * amplitude;
  if (/likelihood|confidence|completeness/.test(observation.measurement)) return percent(Math.min(1, Math.max(0, displayed)));
  return `${displayed.toFixed(3)}${observation.unit ? ` ${observation.unit}` : ""}`;
}

type AudioControls = { playSignalMonitor: (samples: number[], sampleRateHz: number) => void; stopMonitor: () => void };
type RequestActivityState = { state: "waiting" | "received" | "failed"; label: string };
type PanelProps = { state: Projection; command: (type: string, parameters?: Record<string, unknown>) => void; audio?: AudioControls; requestActivity?: RequestActivityState | null };

function RequestActivity({ activity, compact = false }: { activity: RequestActivityState; compact?: boolean }) {
  return <div className={`request-activity ${activity.state} ${compact ? "compact" : ""}`} role="status" aria-live="polite"><i aria-hidden="true" /><strong>{activity.label}</strong>{activity.state === "waiting" && <span>Please wait; your request was received and is being processed.</span>}</div>;
}

function Panel({ title: panelTitle, code, wide = false, children }: { title: string; code: string; wide?: boolean; children: React.ReactNode }) {
  return <section id={`station-${code}`} className={`panel ${wide ? "wide" : ""}`}><header><span>{code}</span><h2>{panelTitle}</h2></header><div className="panel-body">{children}</div></section>;
}

function Metric({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) {
  return <div className={danger ? "metric danger-text" : "metric"}><span>{label}</span><strong>{value}</strong></div>;
}

function MetricGrid({ values }: { values: Array<[string, string]> }) {
  return <div className="metric-grid">{values.map(([label, value]) => <Metric key={label} label={label} value={value} />)}</div>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
