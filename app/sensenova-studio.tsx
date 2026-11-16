"use client";

import { useEffect, useState } from "react";
import "./sensenova-studio.css";

type Status = { ready:boolean; installed:boolean; model:string; gguf_size:number; experimental:boolean; minimum_resolution:string };

export default function SenseNovaStudio({onClose}:{onClose:()=>void}) {
  const [status,setStatus]=useState<Status|null>(null);
  const [prompt,setPrompt]=useState("A cinematic portrait of an ancient bronze guardian inside a vast dark temple, turquoise crystal details, dramatic volumetric light, realistic metal, highly detailed, centered composition.");
  const [profile,setProfile]=useState("draft");
  const [resolution,setResolution]=useState("2048x2048|1:1");
  const [seed,setSeed]=useState(-1);
  const [job,setJob]=useState("");
  const [state,setState]=useState("Checking the local installation…");
  const [result,setResult]=useState("");
  const [zoom,setZoom]=useState(false);

  useEffect(()=>{fetch("/api/sensenova/status").then(r=>r.json()).then(data=>{setStatus(data);setState(data.ready?"Engine ready":data.installed?"Installed · starts when you generate":"Installation incomplete");}).catch(()=>setState("Status check failed"));},[]);
  useEffect(()=>{
    if(!job)return;
    const timer=window.setInterval(async()=>{
      try{
        const response=await fetch(`/api/sensenova/jobs/${job}`); const data=await response.json();
        if(data.status==="complete"&&data.images?.[0]){setResult(data.images[0]);setState("Complete");setJob("");clearInterval(timer);}
        else if(data.status==="failed"||data.status==="error"){setState(data.error||"Generation failed");setJob("");clearInterval(timer);}
        else setState("Generating locally… SenseNova native images are large, so please keep Froja open.");
      }catch{setState("Waiting for the local engine…");}
    },2500);
    return()=>clearInterval(timer);
  },[job]);

  const generate=async()=>{
    if(!prompt.trim()||job)return;
    setResult("");setState(status?.ready?"Submitting workflow…":"Starting isolated SenseNova engine…");
    try{
      const response=await fetch("/api/sensenova/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt,profile,resolution,seed})});
      const data=await response.json(); if(!response.ok)throw new Error(data.error||"Could not start SenseNova.");
      setJob(data.prompt_id);setState("Generation started");
    }catch(error){setState(error instanceof Error?error.message:"Generation failed");}
  };
  const size=status?.gguf_size?`${(status.gguf_size/1073741824).toFixed(2)} GB`:"Not found";

  return <div className="sn-overlay" onClick={onClose}>
    <section className="sn-studio" onClick={event=>event.stopPropagation()}>
      <header><div><h2>✦ Froja SenseNova Studio</h2><p>Unified local image generation · isolated from checkpoints and LoRAs</p></div><button className="sn-close" onClick={onClose}>×</button></header>
      <div className="sn-warning"><b>Experimental Q4 Preview · 12 GB profile</b><span>This is the small community Preview quantization, not the 50 GB final model. Your existing models remain untouched.</span></div>
      <main>
        <div className="sn-controls">
          <label><span>Prompt</span><textarea value={prompt} onChange={e=>setPrompt(e.target.value)} /></label>
          <div className="sn-grid">
            <label><span>Quality profile</span><select value={profile} onChange={e=>setProfile(e.target.value)}><option value="smoke">Compatibility · 1 step</option><option value="draft">Draft · 8 steps</option><option value="quality">Quality · 24 steps (slow)</option></select></label>
            <label><span>Image size</span><select value={resolution} onChange={e=>setResolution(e.target.value)}><option value="2048x2048|1:1">2048 × 2048 · Square</option><option value="2304x1728|4:3">2304 × 1728 · Landscape</option><option value="1728x2304|3:4">1728 × 2304 · Portrait</option><option value="2560x1440|16:9">2560 × 1440 · Wide</option><option value="1440x2560|9:16">1440 × 2560 · Tall</option></select></label>
            <label><span>Seed (-1 random)</span><input type="number" value={seed} onChange={e=>setSeed(Number(e.target.value))} /></label>
          </div>
          <article className="sn-model"><div><b>{status?.model||"SenseNova U1.5 Q4"}</b><small>{size} · CUDA bfloat16 · SDPA · balanced VRAM</small></div><i className={status?.ready?"ready":status?.installed?"installed":"missing"}>{status?.ready?"Ready":status?.installed?"Installed":"Missing"}</i></article>
          <div className="sn-action"><div><b>{job?"SenseNova is working":state}</b><small>{job?`Job ${job.slice(0,8)}…`:"Results return to Froja automatically."}</small></div><button disabled={!status?.installed||!prompt.trim()||!!job} onClick={generate}>{job?"Generating…":"Generate with SenseNova"}</button></div>
        </div>
        <aside className="sn-preview">
          <div className="sn-preview-head"><div><b>Result Preview</b><small>{resolution.split("|")[0]}</small></div>{result&&<button onClick={()=>setZoom(true)}>Zoom</button>}</div>
          <div className="sn-frame">{result?<img src={result} alt="SenseNova generated result" onDoubleClick={()=>setZoom(true)} />:<div><span>✦</span><b>Your SenseNova image will appear here</b><small>It will not disappear directly into the output folder.</small></div>}</div>
          {result&&<div className="sn-result-actions"><a href={result} download>Download image</a><button onClick={()=>setZoom(true)}>Inspect full size</button></div>}
          <p>{state}</p>
        </aside>
      </main>
    </section>
    {zoom&&result&&<div className="sn-zoom" onClick={()=>setZoom(false)}><button>×</button><img src={result} alt="Full-size SenseNova result" /></div>}
  </div>;
}
