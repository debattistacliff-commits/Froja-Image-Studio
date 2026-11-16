"use client";

import { useEffect, useState } from "react";
import "./sensenova-studio.css";

type Status = {
  ready: boolean;
  installed: boolean;
  model: string;
  files: Record<string, { found: boolean; size: number }>;
};

export default function KreaFastStudio({
  onClose,
  initialPrompt,
}: {
  onClose: () => void;
  initialPrompt: string;
}) {
  const [status, setStatus] = useState<Status | null>(null);
  const [prompt, setPrompt] = useState(
    initialPrompt ||
      "A handcrafted gold and silver filigree medallion, open wire lace construction, museum jewelry photography, soft studio light, highly detailed.",
  );
  const [size, setSize] = useState("768x768");
  const [seed, setSeed] = useState(-1);
  const [job, setJob] = useState("");
  const [state, setState] = useState("Checking the local Krea installation…");
  const [result, setResult] = useState("");
  const [zoom, setZoom] = useState(false);

  useEffect(() => {
    fetch("/api/krea-fast/status")
      .then((response) => response.json())
      .then((data) => {
        setStatus(data);
        setState(
          data.installed
            ? data.ready
              ? "Engine ready"
              : "Installed · engine starts when you generate"
            : "Installation incomplete",
        );
      })
      .catch(() => setState("Status check failed"));
  }, []);

  useEffect(() => {
    if (!job) return;
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch("/api/jobs/" + job);
        const data = await response.json();
        if (data.status === "complete" && data.images?.[0]) {
          setResult(data.images[0]);
          setState("Complete · four-step image returned to Froja");
          setJob("");
          clearInterval(timer);
        } else if (data.status === "failed" || data.status === "error") {
          setState(typeof data.error === "string" ? data.error : "Generation failed");
          setJob("");
          clearInterval(timer);
        } else {
          setState("Generating locally in four steps…");
        }
      } catch {
        setState("Waiting for ComfyUI…");
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [job]);

  const generate = async () => {
    if (!prompt.trim() || job) return;
    const [width, height] = size.split("x").map(Number);
    setResult("");
    setState("Submitting the pinned four-step workflow…");
    try {
      const response = await fetch("/api/krea-fast/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, width, height, seed }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not start Krea Fast.");
      setJob(data.prompt_id);
      setState("Generation started");
    } catch (error) {
      setState(error instanceof Error ? error.message : "Generation failed");
    }
  };

  const loraSize = status?.files?.lora?.size
    ? (status.files.lora.size / 1048576).toFixed(0) + " MB"
    : "Missing";

  return (
    <div className="sn-overlay" onClick={onClose}>
      <section className="sn-studio" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <h2>⚡ Froja Krea Fast Studio</h2>
            <p>Krea 2 Turbo Q4 · pinned four-step distillation experiment</p>
          </div>
          <button className="sn-close" onClick={onClose}>×</button>
        </header>
        <div className="sn-warning">
          <b>Experimental and isolated</b>
          <span>Your normal eight-step Krea workflow and existing models remain unchanged.</span>
        </div>
        <main>
          <div className="sn-controls">
            <label>
              <span>Prompt</span>
              <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} />
            </label>
            <div className="sn-grid">
              <label>
                <span>Image size</span>
                <select value={size} onChange={(event) => setSize(event.target.value)}>
                  <option value="768x768">768 × 768 · Safe test</option>
                  <option value="1024x1024">1024 × 1024 · Square</option>
                  <option value="1024x768">1024 × 768 · Landscape</option>
                  <option value="768x1024">768 × 1024 · Portrait</option>
                </select>
              </label>
              <label>
                <span>Seed (-1 random)</span>
                <input type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} />
              </label>
              <label>
                <span>Fixed recipe</span>
                <input value="4 steps · CFG 1 · Euler / Simple" readOnly />
              </label>
            </div>
            <article className="sn-model">
              <div>
                <b>{status?.model || "Krea 2 Turbo · Fast 4-Step"}</b>
                <small>{loraSize} adapter · Q4 base · FP8 text encoder</small>
              </div>
              <i className={status?.installed ? "ready" : "missing"}>
                {status?.installed ? "Installed" : "Missing"}
              </i>
            </article>
            <div className="sn-action">
              <div>
                <b>{job ? "Krea Fast is working" : state}</b>
                <small>{job ? "Job " + job.slice(0, 8) + "…" : "Result returns here; normal Krea remains available."}</small>
              </div>
              <button disabled={!status?.installed || !prompt.trim() || !!job} onClick={generate}>
                {job ? "Generating…" : "Generate 4-Step Test"}
              </button>
            </div>
          </div>
          <aside className="sn-preview">
            <div className="sn-preview-head">
              <div><b>Experimental Result</b><small>{size.replace("x", " × ")}</small></div>
              {result && <button onClick={() => setZoom(true)}>Zoom</button>}
            </div>
            <div className="sn-frame">
              {result ? (
                <img src={result} alt="Krea Fast result" onDoubleClick={() => setZoom(true)} />
              ) : (
                <div><span>⚡</span><b>Your four-step image will appear here</b><small>Saved under output/Froja/KreaFast4Step.</small></div>
              )}
            </div>
            {result && <div className="sn-result-actions"><a href={result} download>Download image</a><button onClick={() => setZoom(true)}>Inspect full size</button></div>}
            <p>{state}</p>
          </aside>
        </main>
      </section>
      {zoom && result && <div className="sn-zoom" onClick={() => setZoom(false)}><button>×</button><img src={result} alt="Full-size Krea Fast result" /></div>}
    </div>
  );
}
