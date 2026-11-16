"use client";

import { useEffect, useState } from "react";
import "./sensenova-studio.css";

type Status = { installed:boolean; model:string; files:{name:string;size:number}[]; experimental:boolean };

export default function LLaDAStudio({onClose}:{onClose:()=>void}) {
  const [status,setStatus]=useState<Status|null>(null);
  const [prompt,setPrompt]=useState("A small bronze robot sitting on a wooden chair, turquoise studio background, warm soft light, detailed product photography.");
  const [size,setSize]=useState("512x512");
  const [steps,setSteps]=useState(1);
  const [job,setJob]=useState("");
  const [state,setState]=useState("Checking the quantized model…");
  const [result,setResult]=useState("");
  const [zoom,setZoom]=useState(false);

  useEffect(()=>{fetch("/api/llada/status").then(r=>r.json()).then(data=>{setStatus(data);setState(data.installed?"Quantized model ready":"Installation incomplete");}).catch(()=>setState("Status check failed"));},[]);
  useEffect(()=>{
    if(!job)return;
    const timer=window.setInterval(async()=>{
      try {
        const response=await fetch(`/api/llada/jobs/${job}`); const data=await response.json();
        if(data.status==="complete"&&data.image){setResult(`${data.image}&t=${Date.now()}`);setState("Complete");setJob("");clearInterval(timer);}
        else if(data.status==="failed"||data.status==="missing"){console.error("LLaDA generation details:",data.error);setState("Generation stopped. Froja saved the technical details in its logs.");setJob("");clearInterval(timer);}
        else setState("Generating locally… keep Froja open. The Q4 encoder is slow on 12 GB VRAM.");
      } catch { setState("Waiting for the local LLaDA process…"); }
    },3000);
    return()=>clearInterval(timer);
  },[job]);

  const generate=async()=>{
    if(!prompt.trim()||job)return;
    const [width,height]=size.split("x").map(Number); setResult(""); setState("Starting isolated LLaDA engine…");
    try {
      const response=await fetch("/api/llada/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt,width,height,steps})});
      const data=await response.json(); if(!response.ok)throw new Error(data.error||"Could not start LLaDA.");
      setJob(data.job_id); setState("Generation started");
    } catch(error){setState(error instanceof Error?error.message:"Generation failed");}
  };
  const disk=status?.files?.reduce((sum,file)=>sum+file.size,0)||0;

  return <div className="sn-overlay" onClick={onClose}>
    <section className="sn-studio" onClick={event=>event.stopPropagation()}>
      <header><div><h2>◈ Froja LLaDA Studio</h2><p>Quantized local image generation · separate from Krea checkpoints</p></div><button className="sn-close" onClick={onClose}>×</button></header>
      <div className="sn-warning"><b>Experimental · INT8 transformer + Q4 encoder</b><span>Validated on your RTX 4070 Ti. One 512px test took about 3 minutes. Four steps improve quality but take longer.</span></div>
      <main>
        <div className="sn-controls">
          <div className="sn-workflow"><b>Simple workflow</b><span>1. Describe the image → 2. Choose the canvas → 3. Choose quality → 4. Generate and review</span></div>
          <label><span>Prompt</span><textarea value={prompt} onChange={e=>setPrompt(e.target.value)} maxLength={2000}/></label>
          <div className="sn-grid">
            <label><span>Image size</span><select value={size} onChange={e=>setSize(e.target.value)}><option value="512x512">512 × 512 · Recommended test</option><option value="768x768">768 × 768 · Slower</option><option value="1024x1024">1024 × 1024 · Experimental</option><option value="768x512">768 × 512 · Landscape</option><option value="512x768">512 × 768 · Portrait</option></select></label>
            <label><span>Quality / render passes</span><select value={steps} onChange={e=>setSteps(Number(e.target.value))}><option value={1}>1 pass · Quick compatibility test</option><option value={2}>2 passes · Draft</option><option value={3}>3 passes · Balanced</option><option value={4}>4 passes · Best intended quality</option></select></label>
          </div>
          <article className="sn-model"><div><b>{status?.model||"LLaDA-Image Turbo"}</b><small>{disk?`${(disk/1073741824).toFixed(1)} GB local files`:"Model files not found"} · model CPU offload · tiled VAE</small></div><i className={status?.installed?"ready":"missing"}>{status?.installed?"Ready":"Missing"}</i></article>
          <div className="sn-action"><div><b>{job?"LLaDA is working":state}</b><small>{job?`Job ${job.slice(0,8)}… · this can take several minutes`:"The final image returns to this window."}</small></div><button disabled={!status?.installed||!prompt.trim()||!!job} onClick={generate}>{job?"Generating…":"Generate with LLaDA"}</button></div>
        </div>
        <aside className="sn-preview">
          <div className="sn-preview-head"><div><b>Result Preview</b><small>{size}</small></div>{result&&<button onClick={()=>setZoom(true)}>Zoom</button>}</div>
          <div className="sn-frame">{result?<img src={result} alt="LLaDA generated result" onDoubleClick={()=>setZoom(true)}/>:<div><span>◈</span><b>Your LLaDA image will appear here</b><small>It will not disappear directly into the output folder.</small></div>}</div>
          {result&&<div className="sn-result-actions"><a href={result} download>Download image</a><button onClick={()=>setZoom(true)}>Inspect full size</button></div>}
          <p>{state}</p>
        </aside>
      </main>
    </section>
    {zoom&&result&&<div className="sn-zoom" onClick={()=>setZoom(false)}><button>×</button><img src={result} alt="Full-size LLaDA result"/></div>}
  </div>;
}
