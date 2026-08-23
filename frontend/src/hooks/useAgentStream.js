import { useRef, useState, useCallback } from "react";

const BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function loadHistoryDurations(track) {
  try {
    const raw = localStorage.getItem(`agent_durations_${track}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveHistoryDuration(track, seconds) {
  const durations = loadHistoryDurations(track);
  durations.push(seconds);
  const trimmed = durations.slice(-10); // keep last 10 real runs
  localStorage.setItem(`agent_durations_${track}`, JSON.stringify(trimmed));
}

export function getEstimatedSeconds(track) {
  const durations = loadHistoryDurations(track);
  if (durations.length === 0) return null;
  const avg = durations.reduce((a, b) => a + b, 0) / durations.length;
  return Math.round(avg);
}

/**
 * Streams an agent run via SSE, exposing live steps, plan, specialist
 * progress (Track C), elapsed time, and abort support.
 *
 * track: "A" | "B" | "C" -- used to store/read real historical durations
 * for the "usually takes ~Xs" estimate (never a fabricated number).
 */
export function useAgentStream(endpoint, track) {
  const [steps, setSteps] = useState([]);
  const [plan, setPlan] = useState(null);
  const [specialists, setSpecialists] = useState({}); // { agentName: "pending"|"running"|"done" }
  const [status, setStatus] = useState("idle"); // idle | running | done | error | cancelled
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const abortControllerRef = useRef(null);
  const timerRef = useRef(null);
  const startTimeRef = useRef(null);

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const start = useCallback(async (body, specialistNames = null) => {
    setSteps([]);
    setPlan(null);
    setResult(null);
    setError(null);
    setStatus("running");
    setElapsedSeconds(0);

    if (specialistNames) {
      const initial = {};
      specialistNames.forEach((n) => (initial[n] = "pending"));
      setSpecialists(initial);
    } else {
      setSpecialists({});
    }

    startTimeRef.current = performance.now();
    timerRef.current = setInterval(() => {
      setElapsedSeconds(((performance.now() - startTimeRef.current) / 1000).toFixed(1));
    }, 200);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await fetch(`${BASE_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const events = buffer.split("\n\n");
        buffer = events.pop(); // last (possibly incomplete) chunk stays in buffer

        for (const raw of events) {
          if (!raw.trim() || raw.startsWith(":")) continue;
          const eventMatch = raw.match(/^event: (.+)$/m);
          const dataMatch = raw.match(/^data: (.+)$/m);
          if (!eventMatch || !dataMatch) continue;

          const eventType = eventMatch[1];
          let data;
          try {
            data = JSON.parse(dataMatch[1]);
          } catch (parseErr) {
            console.warn("Skipped malformed SSE event:", parseErr, dataMatch[1].slice(0, 200));
            continue; // skip this one event, keep the stream alive
          }

          if (eventType === "step") {
            setSteps((prev) => [...prev, data]);
            if (data.agent_role) {
              setSpecialists((prev) =>
                prev[data.agent_role] !== undefined
                  ? { ...prev, [data.agent_role]: "running" }
                  : prev
              );
            }
          } else if (eventType === "plan") {
            setPlan(data.plan);
          } else if (eventType === "specialist_done") {
            setSpecialists((prev) => ({ ...prev, [data.agent]: "done" }));
          } else if (eventType === "done") {
            setResult(data);
            setStatus(data.stopped_reason === "cancelled" ? "cancelled" : "done");
            const secs = (performance.now() - startTimeRef.current) / 1000;
            if (data.stopped_reason !== "cancelled") {
              saveHistoryDuration(track, secs);
            }
          } else if (eventType === "error") {
            setError(data.error);
            setStatus("error");
          }
        }
      }
    } catch (e) {
      if (e.name === "AbortError") {
        setStatus("cancelled");
      } else {
        setError(e.message);
        setStatus("error");
      }
    } finally {
      stopTimer();
    }
  }, [endpoint, track]);

  const abort = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    stopTimer();
    setStatus("cancelled");
  }, []);

  return { steps, plan, specialists, status, result, error, elapsedSeconds, start, abort };
}