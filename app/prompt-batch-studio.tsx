"use client";

import { useEffect, useRef, useState } from "react";
import "./prompt-batch-studio.css";

type JobState = "waiting" | "queued" | "running" | "complete" | "failed" | "cancelled";
type BatchJob = { id: string; title: string; prompt: string; state: JobState; image: string; error: string };
type Props = { onClose:()=>void; checkpoint:string; architecture?:string; negative:string; steps:number; cfg:number; width:number; height:number; sampler:string; stylePrompt:string; loras:{relative:string;strength:number}[] };

const starters = [
  ["Enormous Coin Medallion", "Circular coin medallion entirely constructed from open gold and silver filigree wirework, every element built from fine twisted wire with visible negative space, studio product photography."],
  ["Character Reference Sheet", "Professional reference sheet of the same adult woman in multiple natural seated poses, warm contemporary room, consistent identity, clothing and jewellery."],
  ["Sketch to Dimensional Room", "Transform an architectural room sketch into a believable dimensional environment while preserving the original layout and camera, realistic materials, lighting and spatial relationships."],
  ["Reference Scene Composition", "Combine the supplied room, chair, person and decorative object into one integrated image with correct scale, contact shadows, perspective and unified lighting."],
  ["Wild Adventure Manga", "Wild adventure manga close-up, huge readable expression, elastic facial anatomy, thick energetic ink contours, angular costume shapes, warm hand-painted cel colour and fiery background."],
] as const;

const makeJobs=():BatchJob[]=>starters.map(([title,prompt])=>({id:crypto.randomUUID(),title,prompt,state:"waiting",image:"",error:""}));
const delay=(ms:number)=>new Promise(resolve=>window.setTimeout(resolve,ms));

export default function PromptBatchStudio(props:Props){
  const [jobs,setJobs]=useState<BatchJob[]>(()=>{try{const saved=JSON.parse(localStorage.getItem("froja-prompt-batch")||"null");return Array.isArray(saved)&&saved.length?saved.map((j:BatchJob)=>({...j,state:"waiting",error:""})):makeJobs();}catch{return makeJobs();}});
  const [active,setActive]=useState(false); const [pauseRequested,setPauseRequested]=useState(false); const [message,setMessage]=useState("Ready to generate this queue."); const stopRef=useRef(false); const pauseRef=useRef(false);
  useEffect(()=>{localStorage.setItem("froja-prompt-batch",JSON.stringify(jobs.map(j=>({...j,state:"waiting",error:""}))));},[jobs]);
  const complete=jobs.filter(j=>j.state==="complete").length; const percent=jobs.length?Math.round(complete/jobs.length*100):0;
  const update=(id:string,patch:Partial<BatchJob>)=>setJobs(items=>items.map(item=>item.id===id?{...item,...patch}:item));
  async function runOne(snapshot:BatchJob,index:number){
    update(snapshot.id,{state:"running",error:""}); setMessage(`Generating ${snapshot.title} (${index+1} of ${jobs.length})…`);
    try{
      const response=await fetch("/api/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({checkpoint:props.checkpoint,architecture:props.architecture,prompt:[snapshot.prompt.trim(),props.stylePrompt].filter(Boolean).join(", "),negative_prompt:props.negative,steps:props.steps,cfg:props.cfg,seed:Math.floor(Math.random()*4294967295),width:props.width,height:props.height,sampler:props.sampler,scheduler:"normal",loras:props.loras.map(l=>({name:l.relative,strength:l.strength}))})});
      const data=await response.json(); if(!response.ok)throw new Error(data.error||"Generation could not start.");
      for(;;){await delay(1500);const check=await fetch(`/api/jobs/${data.prompt_id}`).then(r=>r.json());if(check.status==="complete"&&check.images?.[0]){update(snapshot.id,{state:"complete",image:check.images[0]});return;}if(check.status==="failed"||check.status==="error")throw new Error(check.error||"Generation failed.");}
    }catch(error){update(snapshot.id,{state:"failed",error:error instanceof Error?error.message:"Generation failed."});}
  }
  async function generateAll(){
    if(active)return;if(!props.checkpoint){setMessage("Choose a checkpoint in Text to Image first.");return;}stopRef.current=false;pauseRef.current=false;setPauseRequested(false);setActive(true);
    const queue=jobs.map(j=>j.state==="complete"?j:{...j,state:"queued" as JobState});setJobs(queue);
    for(let index=0;index<queue.length;index++){const item=queue[index];if(item.state==="complete")continue;if(stopRef.current){setJobs(all=>all.map(j=>j.state==="queued"?{...j,state:"cancelled"}:j));break;}await runOne(item,index);if(pauseRef.current){setMessage("Paused after the current image.");break;}}
    setActive(false);if(!stopRef.current&&!pauseRef.current)setMessage("Batch finished. Review the results below.");
  }
  const change=(id:string,key:"title"|"prompt",value:string)=>update(id,{[key]:value} as Partial<BatchJob>);
  const statusLabel=(state:JobState)=>({waiting:"Waiting",queued:"Queued",running:"Generating",complete:"Completed",failed:"Failed",cancelled:"Stopped"}[state]);
  return <div className="pbs-overlay" onClick={props.onClose}><div className="pbs-studio" onClick={e=>e.stopPropagation()}>
    <header><div><h2>Froja Prompt Batch Studio</h2><p>Independent prompts · one safe sequential GPU queue</p></div><nav><button onClick={()=>setJobs(items=>[...items,{id:crypto.randomUUID(),title:`Prompt ${items.length+1}`,prompt:"",state:"waiting",image:"",error:""}])}>＋ Add prompt</button><button disabled={!active} onClick={()=>{pauseRef.current=true;setPauseRequested(true);}}>Ⅱ {pauseRequested?"Pausing after current":"Pause after current"}</button><button disabled={!active} onClick={()=>{stopRef.current=true;setMessage("Stopping after the current image…");}}>■ Stop</button><button className="pbs-run" disabled={active||!jobs.some(j=>j.prompt.trim()&&j.state!=="complete")} onClick={generateAll}>▶ Generate all</button><button className="pbs-close" onClick={props.onClose}>×</button></nav></header>
    <section className="pbs-summary"><div><b>{message}</b><small>{complete} / {jobs.length} complete · jobs run one at a time to protect VRAM</small><i><span style={{width:`${percent}%`}}/></i></div><em>{percent}%</em></section>
    <main>{jobs.map((job,index)=><article key={job.id} className={`pbs-job ${job.state}`}><strong className="pbs-number">{index+1}</strong><section><div className="pbs-title"><input aria-label={`Title ${index+1}`} value={job.title} onChange={e=>change(job.id,"title",e.target.value)}/><span>{statusLabel(job.state)}</span></div><textarea aria-label={`Prompt ${index+1}`} value={job.prompt} onChange={e=>change(job.id,"prompt",e.target.value)}/><footer><span>{props.width} × {props.height}</span><span>{props.steps} steps</span><span>CFG {props.cfg}</span><button disabled={active||!job.prompt.trim()} onClick={async()=>{setActive(true);await runOne(job,index);setActive(false);}}>Generate this</button><button disabled={active} onClick={()=>setJobs(items=>items.filter(item=>item.id!==job.id))}>Remove</button></footer>{job.error&&<p className="pbs-error">{job.error}</p>}</section><aside>{job.image?<><img src={job.image} alt={`${job.title} result`}/><a href={job.image} target="_blank" rel="noreferrer">Zoom / save result</a></>:<div className={job.state==="running"?"working":""}><b>{job.state==="running"?"◌":"▧"}</b><span>{statusLabel(job.state)}</span></div>}</aside></article>)}</main>
    <footer className="pbs-bottom"><span>Using current Froja model: <b>{props.checkpoint||"No checkpoint selected"}</b></span><button disabled={active} onClick={()=>{setJobs(makeJobs());setMessage("Five example prompts restored.");}}>Reset examples</button></footer>
  </div></div>;
}
