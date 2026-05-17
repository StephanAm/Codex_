import { useCallback, useEffect, useState } from "react";

type Status = "pending" | "ok" | "error";
interface Step { label: string; status: Status }

const LABELS = [
  "Initialising storage engine",
  "Loading tag index",
  "Resolving references",
  "Connecting to API",
  "Ready",
];

const HEALTH_URL  = "http://127.0.0.1:8765/health";
const POLL_MS     = 400;
const TIMEOUT_MS  = 5_000;

async function waitForBackend(): Promise<void> {
  const deadline = Date.now() + TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(900) });
      if (r.ok) return;
    } catch { /* not yet */ }
    await new Promise<void>(r => setTimeout(r, POLL_MS));
  }
  throw new Error("timeout");
}

interface Props { onReady: () => void }

export function SplashScreen({ onReady }: Props) {
  const [steps, setSteps]       = useState<Step[]>(LABELS.map(l => ({ label: l, status: "pending" })));
  const [progress, setProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [bootKey, setBootKey]   = useState(0);

  const mark = useCallback((i: number, s: Status) =>
    setSteps(prev => prev.map((step, idx) => idx === i ? { ...step, status: s } : step)), []);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      setSteps(LABELS.map(l => ({ label: l, status: "pending" })));
      setProgress(0);
      setErrorMsg(null);

      // Steps 0–2: cosmetic
      for (let i = 0; i < 3; i++) {
        await new Promise<void>(r => setTimeout(r, 380 + i * 80));
        if (cancelled) return;
        mark(i, "ok");
        setProgress((i + 1) * 16);
      }

      // Step 3: real backend check
      try {
        await waitForBackend();
        if (cancelled) return;
        mark(3, "ok");
        setProgress(86);
      } catch {
        if (!cancelled) {
          mark(3, "error");
          setErrorMsg("API server did not respond. Backend may have failed to start.");
        }
        return;
      }

      // Step 4: Ready
      await new Promise<void>(r => setTimeout(r, 280));
      if (cancelled) return;
      mark(4, "ok");
      setProgress(100);

      await new Promise<void>(r => setTimeout(r, 650));
      if (!cancelled) onReady();
    }

    boot();
    return () => { cancelled = true; };
  }, [bootKey, mark, onReady]);

  return (
    <div className="splash">
      <div className="splash-grid" />
      <div className="splash-scanlines" />
      <div className="splash-vignette" />

      <div className="splash-icon-wrap">
        <div className="splash-icon-glow" />
        <div className="splash-icon-box">
          <svg width="52" height="52" viewBox="0 0 52 52" xmlns="http://www.w3.org/2000/svg">
            <line x1="10" y1="8"  x2="10" y2="44" stroke="#E8E8F0" strokeWidth="5" strokeLinecap="square" />
            <line x1="42" y1="8"  x2="42" y2="44" stroke="#E8E8F0" strokeWidth="5" strokeLinecap="square" />
            <line x1="10" y1="8"  x2="26" y2="29" stroke="#E8E8F0" strokeWidth="5" strokeLinecap="square" strokeLinejoin="miter" />
            <line x1="42" y1="8"  x2="26" y2="29" stroke="#E8E8F0" strokeWidth="5" strokeLinecap="square" strokeLinejoin="miter" />
            <line x1="26.5" y1="4" x2="26.5" y2="48" stroke="#00E5FF" strokeWidth="2.5" strokeLinecap="square" />
            <rect x="23.5" y="40" width="6" height="8" fill="#00E5FF" />
          </svg>
        </div>
      </div>

      <div className="splash-wordmark">MNEMO<span>_</span></div>
      <div className="splash-tagline">Remember everything</div>

      <div className="splash-boot-lines">
        {steps.map((step) => (
          <div
            key={step.label}
            className={[
              "splash-boot-line",
              step.status !== "pending" ? "splash-boot-line--visible" : "",
              step.status === "error"   ? "splash-boot-line--error"   : "",
            ].join(" ").trim()}
          >
            {step.label}
            {step.status === "ok"    && <span className="splash-boot-suffix splash-boot-ok">  OK</span>}
            {step.status === "error" && <span className="splash-boot-suffix splash-boot-err"> FAILED</span>}
          </div>
        ))}
      </div>

      <div className="splash-progress-wrap">
        <div className="splash-progress-bar" style={{ width: `${progress}%` }} />
      </div>

      {errorMsg && (
        <div className="splash-error-block">
          <p className="splash-error-msg">{errorMsg}</p>
          <button className="splash-retry-btn" onClick={() => setBootKey(k => k + 1)}>
            Retry
          </button>
        </div>
      )}

      <div className="splash-version">v{__APP_VERSION__}</div>
    </div>
  );
}
