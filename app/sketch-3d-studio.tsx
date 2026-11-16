"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

type Props = { onClose: () => void };
type Result = { id: string; image: string; label: string; prompt: string };
type RenderMode = "pencil" | "concept" | "render3d" | "realistic";

const views = [
  ["Hero", "three-quarter hero view"], ["Front", "orthographic front view"],
  ["Side", "orthographic side view"], ["Back", "orthographic rear view"],
  ["Top", "top-down view"], ["Detail", "macro construction detail"],
  ["Clay", "neutral grey clay render"], ["Environment", "wide environmental presentation"],
] as const;
const materials = ["Original", "Clay", "Aged Bronze", "Brushed Steel", "Mahogany", "Stone", "Glass", "Painted Plastic"];
const renderModes: {id:RenderMode;label:string;description:string;prompt:string}[] = [
  {id:"pencil",label:"Clean Pencil",description:"Refine the drawing without redesigning it",prompt:"professional clean pencil concept sketch, precise confident linework, subtle construction shading, white drawing paper, retain the original drawing and exact design"},
  {id:"concept",label:"Concept Art",description:"Finished painted design sheet",prompt:"finished professional concept art, clear readable forms, refined materials, controlled studio lighting, production design presentation"},
  {id:"render3d",label:"3D Visualization",description:"Realistic CGI-style dimensional render",prompt:"high-end realistic 3D visualization, physically based materials, global illumination, ambient occlusion, realistic dimensional depth, production-quality CGI render"},
  {id:"realistic",label:"Realistic Image",description:"Turn the sketch into a believable photograph",prompt:"photorealistic finished image, believable real-world construction, physically accurate materials, natural lighting, realistic scale and depth, professional architectural or product photography"},
];

function dataUrl(file?: File) {
  return new Promise<string>((resolve, reject) => {
    if (!file) return reject(new Error("Choose a sketch first."));
    const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(reader.error); reader.readAsDataURL(file);
  });
}

async function imageUrlToDataUrl(url: string) {
  if (url.startsWith("data:")) return url;
  const response = await fetch(url);
  if (!response.ok) throw new Error("Froja could not prepare the generated render for 3D reconstruction.");
  const blob = await response.blob();
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function CloseIcon() {
  return <span className="sketch3d-close-icon" aria-hidden="true" />;
}

function MeshViewer({ url }: { url: string }) {
  const mount = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const host = mount.current;
    if (!host || !url) return;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x081116);
    const camera = new THREE.PerspectiveCamera(38, 1, 0.01, 100);
    camera.position.set(2.8, 1.8, 3.2);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.1;
    scene.add(new THREE.HemisphereLight(0xdff8ff, 0x1a2730, 2.4));
    const key = new THREE.DirectionalLight(0xffffff, 3.2); key.position.set(3, 4, 5); scene.add(key);
    const rim = new THREE.DirectionalLight(0x27e1dd, 2); rim.position.set(-4, 2, -3); scene.add(rim);
    const grid = new THREE.GridHelper(4, 20, 0x1b8584, 0x16323a); grid.position.y = -1.05; scene.add(grid);
    let disposed = false;
    const showObject = (object: THREE.Object3D) => {
      if (disposed) return;
      const box = new THREE.Box3().setFromObject(object);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      object.position.sub(center);
      const scale = 2 / Math.max(size.x, size.y, size.z, 0.001);
      object.scale.setScalar(scale);
      object.traverse(child => {
        if (child instanceof THREE.Mesh && !child.material) child.material = new THREE.MeshStandardMaterial({ color: 0xa8bbc4, roughness: 0.62, metalness: 0.15, side: THREE.DoubleSide });
      });
      scene.add(object);
    };
    if (/\.glb(?:$|[?&])/i.test(url) || /filename=[^&]*\.glb/i.test(url)) {
      new GLTFLoader().load(url, gltf => showObject(gltf.scene));
    } else {
      new OBJLoader().load(url, object => {
        object.traverse(child => {
          if (child instanceof THREE.Mesh) child.material = new THREE.MeshStandardMaterial({ color: 0xa8bbc4, roughness: 0.62, metalness: 0.15, side: THREE.DoubleSide });
        });
        showObject(object);
      });
    }
    const resize = () => { const w=host.clientWidth||640,h=host.clientHeight||420; renderer.setSize(w,h,false); camera.aspect=w/h; camera.updateProjectionMatrix(); };
    resize(); const observer=new ResizeObserver(resize); observer.observe(host);
    let frame=0; const animate=()=>{frame=requestAnimationFrame(animate);controls.update();renderer.render(scene,camera);}; animate();
    return () => { disposed=true; cancelAnimationFrame(frame); observer.disconnect(); controls.dispose(); renderer.dispose(); renderer.domElement.remove(); scene.traverse(item=>{if(item instanceof THREE.Mesh){item.geometry.dispose(); const mats=Array.isArray(item.material)?item.material:[item.material];mats.forEach(mat=>mat.dispose());}}); };
  }, [url]);
  return <div className="sketch3d-mesh-viewer" ref={mount} />;
}
export default function Sketch3DStudio({ onClose }: Props) {
  const [source, setSource] = useState("");
  const [prompt, setPrompt] = useState("Preserve the exact silhouette, proportions and construction of the uploaded sketch. Convert it into a coherent professional 3D design render.");
  const [material, setMaterial] = useState("Clay");
  const [structure, setStructure] = useState("canny");
  const [renderMode, setRenderMode] = useState<RenderMode>("render3d");
  const [sourceSize, setSourceSize] = useState({width:768,height:768});
  const [strength, setStrength] = useState(0.82);
  const [selectedViews, setSelectedViews] = useState<string[]>(["Hero"]);
  const [results, setResults] = useState<Result[]>([]);
  const [job, setJob] = useState("");
  const [pending, setPending] = useState<{label:string;prompt:string} | null>(null);
  const [queue, setQueue] = useState<{label:string;prompt:string}[]>([]);
  const [status, setStatus] = useState("Ready");
  const [inspect, setInspect] = useState("");
  const [meshStatus, setMeshStatus] = useState<{ready:boolean;engine:string;model:string}>({ready:false,engine:"Checking",model:"Not installed"});
  const [meshJob, setMeshJob] = useState("");
  const [meshUrl, setMeshUrl] = useState("");

  useEffect(() => { fetch("/api/sketch3d/status").then(r=>r.json()).then(setMeshStatus).catch(()=>setMeshStatus({ready:false,engine:"Offline",model:"Unavailable"})); }, []);
  useEffect(() => {
    if (!meshJob) return;
    const timer=setInterval(async()=>{
      try {
        const result=await fetch(`/api/sketch3d/jobs/${meshJob}`).then(r=>r.json());
        if(result.status==="complete"&&result.meshes?.[0]){setMeshUrl(result.meshes[0]);setMeshJob("");setStatus("Rotatable 3D mesh ready.");}
        else if(["failed","error"].includes(result.status)){setMeshJob("");setStatus(result.error||"Mesh reconstruction failed.");}
        else setStatus("Building geometry locally...");
      } catch(error){setMeshJob("");setStatus(error instanceof Error?error.message:"Mesh status failed.");}
    },1600);
    return()=>clearInterval(timer);
  },[meshJob]);
  useEffect(() => {
    if (!job) return;
    const timer = setInterval(async () => {
      const result = await fetch(`/api/extension-jobs/${job}`).then(r=>r.json());
      setStatus(result.status || "Running");
      if (result.status === "complete" && result.images?.[0] && pending) {
        setResults(items => [...items, {id:`${Date.now()}-${pending.label}`, image:result.images[0], label:pending.label, prompt:pending.prompt}]);
        setJob(""); setPending(null);
      } else if (["failed","error"].includes(result.status)) { setStatus(result.error || "Generation failed"); setJob(""); setPending(null); setQueue([]); }
    }, 1400);
    return () => clearInterval(timer);
  }, [job, pending]);
  const materialPrompt = useMemo(() => material === "Original" ? "retain the materials suggested by the sketch" : `${material.toLowerCase()} material, physically believable surface response`, [material]);
  const outputSize = useMemo(() => {
    const longest=1024, ratio=Math.max(0.25,Math.min(4,sourceSize.width/Math.max(1,sourceSize.height)));
    const snap=(value:number)=>Math.max(256,Math.round(value/64)*64);
    return ratio>=1?{width:longest,height:snap(longest/ratio)}:{width:snap(longest*ratio),height:longest};
  },[sourceSize]);
  const runTask = useCallback(async (task:{label:string;prompt:string}) => {
    if (!source) return setStatus("Choose or drop a sketch first.");
    setPending(task); setStatus(`Generating ${task.label}...`);
    try {
      const response = await fetch("/api/image-tool", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
        mode:renderMode === "pencil" ? "img2img" : "controlnet", control_mode:structure === "depth" ? "depth" : "canny", source_image:source, width:outputSize.width, height:outputSize.height, seed:-1,
        strength:renderMode === "pencil" ? 0.32 : strength, control_strength:strength, prompt:task.prompt,
      })});
      const result=await response.json(); if(!response.ok||!result.prompt_id) throw new Error(result.error||"Workflow could not start."); setJob(result.prompt_id);
    } catch(error) { setStatus(error instanceof Error?error.message:"Workflow failed"); setPending(null); setQueue([]); }
  }, [outputSize.height, outputSize.width, renderMode, source, strength, structure]);
  useEffect(() => {
    if (job || pending) return;
    const timer = window.setTimeout(() => {
      if (queue.length) {
        const [next, ...rest] = queue;
        setQueue(rest);
        void runTask(next);
      } else if (status === "Running") {
        setStatus("Complete");
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [job, pending, queue, runTask, status]);
  function generateSelected() {
    if (!source) return setStatus("Choose or drop a sketch first.");
    const finish=renderModes.find(item=>item.id===renderMode) || renderModes[2];
    const tasks=views.filter(([label])=>selectedViews.includes(label)).map(([label,view])=>({label:`${finish.label} | ${label}`,prompt:`Use the uploaded sketch as the strict structural reference. ${prompt} ${view}. ${finish.prompt}. ${materialPrompt}. Preserve the exact silhouette, proportions, placement, camera angle and recognizable design from the drawing. Do not add unrelated objects. no text, no labels, no watermark.`}));
    setResults([]); setQueue(tasks); setStatus("Preparing controlled views...");
  }
  async function requestMesh() {
    if(!source) return setStatus("Choose a clean isolated sketch or render first.");
    if(!meshStatus.ready) return setStatus("The real mesh engine is not installed yet. Render a clean Hero or Clay view first; Froja will use it as the mesh source after installation.");
    const preferred = [...results].reverse().find(item => /3D Visualization|Realistic Image|Concept Art/.test(item.label));
    setStatus(preferred ? "Preparing the generated dimensional render for mesh reconstruction..." : "Starting mesh reconstruction from the uploaded source...");
    try {
      const meshSource = preferred ? await imageUrlToDataUrl(preferred.image) : source;
      const response=await fetch("/api/sketch3d/mesh",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source_image:meshSource,foreground_ratio:0.85})});
      const result=await response.json();
      if(!response.ok||!result.prompt_id) throw new Error(result.error||"Mesh job could not start.");
      setMeshUrl(""); setMeshJob(result.prompt_id);
      setStatus(result.message||`Mesh job started from ${preferred ? "the generated dimensional render" : "the uploaded source"}.`);
    } catch(error){setStatus(error instanceof Error?error.message:"Mesh generation failed");}
  }

  return <div className="sketch3d-modal" onClick={onClose}><section className="sketch3d-studio" onClick={e=>e.stopPropagation()}>
    <header><div><h2>Froja Sketch &amp; 3D Studio</h2><p>Turn sketches into controlled dimensional renders, concept views and real 3D assets.</p></div><button className="sketch3d-close" aria-label="Close Sketch and 3D Studio" title="Close" onClick={onClose}><CloseIcon /></button></header>
    <div className="sketch3d-grid">
      <main>
        <label className="sketch3d-upload">{source?<img src={source} alt="Uploaded sketch"/>:<><b>Drop or choose a sketch</b><small>PNG, JPEG or WebP | concept art, object, creature, furniture or architecture</small></>}<input type="file" accept="image/png,image/jpeg,image/webp" onChange={async e=>{try{const value=await dataUrl(e.target.files?.[0]);setSource(value);const image=new Image();image.onload=()=>setSourceSize({width:image.naturalWidth,height:image.naturalHeight});image.src=value;setStatus("Sketch loaded. Original aspect ratio will be preserved.");}catch(error){setStatus(String(error));}}}/></label>
        <label className="sketch3d-prompt"><b>Design instruction</b><textarea value={prompt} onChange={e=>setPrompt(e.target.value)}/></label>
        <section><h3>Choose the finished result</h3><div className="sketch3d-output-modes">{renderModes.map(item=><button key={item.id} className={renderMode===item.id?"selected":""} onClick={()=>setRenderMode(item.id)}><b>{item.label}</b><small>{item.description}</small></button>)}</div><p className="sketch3d-size-note">Output follows the sketch: {outputSize.width} x {outputSize.height}</p></section>
        <section><h3>Structural guidance</h3><div className="sketch3d-options">{[["lineart","Line art"],["depth","Depth"],["canny","Sketch lock"]].map(([id,label],i)=><button key={`${id}-${i}`} className={structure===id?"selected":""} onClick={()=>setStructure(id)}>{label}</button>)}</div><label className="sketch3d-range">Preserve geometry <b>{Math.round(strength*100)}%</b><input type="range" min="0.45" max="1" step="0.01" value={strength} onChange={e=>setStrength(+e.target.value)}/></label></section>
        <section><h3>Views and concept sheet</h3><div className="sketch3d-views">{views.map(([label,description])=><button key={label} className={selectedViews.includes(label)?"selected":""} onClick={()=>setSelectedViews(items=>items.includes(label)?items.filter(x=>x!==label):[...items,label])}><b>{label}</b><small>{description}</small></button>)}</div></section>
      </main>
      <aside><section><h3>Surface material</h3><div className="sketch3d-materials">{materials.map(name=><button key={name} className={material===name?"selected":""} onClick={()=>setMaterial(name)}><i className={`material-${name.toLowerCase().replace(/\s/g,"-")}`}/><span>{name}</span></button>)}</div></section>
        <section className="sketch3d-engine"><h3>Real 3D mesh</h3><div className={meshStatus.ready?"ready":"pending"}><i/><span><b>{meshStatus.engine}</b><small>{meshStatus.model}</small></span></div><p>Creates a rotatable mesh for Blender or other 3D software. Best results use one isolated object on a simple background.</p><button onClick={requestMesh}>{meshStatus.ready?"Generate Rotatable 3D Mesh":"Mesh Engine Setup Required"}</button><small>{results.some(item=>/3D Visualization|Realistic Image|Concept Art/.test(item.label)) ? "Mesh source: latest generated dimensional render (recommended)" : "Mesh source: uploaded sketch - generate a dimensional render first"}</small></section>
      </aside>
    </div>
    <div className="sketch3d-run"><span><b>{status}</b><small>{job?"GPU job running":queue.length?`${queue.length} views remaining`:results.length?`${results.length} results ready`:"12 GB safety profile"}</small></span><button disabled={!source||!!job||!!pending||!selectedViews.length} onClick={generateSelected}>Generate Selected Views</button></div>
    {meshUrl&&<section className="sketch3d-mesh-result"><header><div><h3>Rotatable 3D Asset</h3><p>Drag to orbit | scroll to zoom | right-click to pan</p></div><a href={meshUrl} download="Froja-Sketch3D.glb">Download 3D Model</a></header><MeshViewer url={meshUrl}/></section>}
    <section className="sketch3d-gallery"><header><h3>Sketch Transformation Gallery</h3><span>{results.length} generated</span></header>{results.length?<div>{results.map(item=><article key={item.id}><button onClick={()=>setInspect(item.image)}><img src={item.image} alt={item.label}/></button><b>{item.label}</b><a href={item.image} download={`Froja-${item.label}.png`}>Download</a></article>)}</div>:<p>Upload a sketch, choose Clean Pencil, Concept Art, 3D Visualization or Realistic Image, then generate the selected views.</p>}</section>
    {inspect&&<div className="sketch3d-inspect" onClick={()=>setInspect("")}><img src={inspect} alt="Large 3D concept inspection"/><button className="sketch3d-close" aria-label="Close image inspector" title="Close"><CloseIcon /></button></div>}
  </section></div>;
}
