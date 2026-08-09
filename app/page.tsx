"use client";

import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { appearanceCategories, appearanceLibrary } from "./appearance-library";

type Model = {
  name: string;
  relative: string;
  path: string;
  source: string;
  size: number;
  architecture: string;
  preview?: string | null;
  triggers?: string[];
  base_model?: string | null;
};
type LoraChoice = Model & { strength: number };
type GenerationRecord = { id:string; image:string; created:string; favorite:boolean; prompt:string; negative:string; model:string; style:string; seed:number; width:number; height:number; steps:number; cfg:number; sampler:string };
type DatasetItem = { id:string; image:string; name:string; caption:string; state:string; metadata?:string };
type TrainingTask = { name:string; position:string; environment:string };
type TrainingResult = { id:string; image:string; name:string; position:string; environment:string; prompt:string; approved:boolean };
type MaterialReference = { name:string; prompt:string; source:string; relative:string; preview:string };

type IconName = "plus" | "home" | "create" | "library" | "preset" | "workflow" | "model" | "lora" | "embedding" | "image" | "video" | "enhance" | "inpaint" | "face" | "control" | "light" | "repair" | "wand" | "settings" | "palette";
function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, string[]> = {
    plus:["M12 5v14","M5 12h14"], home:["m3 11 9-8 9 8","M5 10v10h14V10","M9 20v-6h6v6"],
    create:["M4 5h16v14H4z","m8 5 4 4-4 4-4-4 4-4Z"], library:["M4 4h6v7H4z","M14 4h6v7h-6z","M4 15h6v5H4z","M14 15h6v5h-6z"],
    preset:["M4 7h10","M18 7h2","M4 17h2","M10 17h10","M14 4v6","M6 14v6"], workflow:["M5 5h5v5H5z","M14 14h5v5h-5z","M10 7h4a3 3 0 0 1 3 3v4","m14 11 3 3 3-3"],
    model:["m12 3 9 5-9 5-9-5 9-5Z","m3 12 9 5 9-5","m3 16 9 5 9-5"], lora:["M8 3v6a4 4 0 0 0 8 0V3","M6 3h4","M14 3h4","M12 13v8","M8 21h8"],
    embedding:["M6 3h12v18H6z","M9 7h6","M9 11h6","M9 15h4"], image:["M3 5h18v14H3z","m3 11 4-4 4 4 3-3 5 5","M15 9h.01"],
    video:["M3 5h13v14H3z","m16 5 4 3v8l-4 3V5Z","m8 9 4 3-4 3V9Z"],
    enhance:["m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2L12 3Z","m18 14 .8 2.2L21 17l-2.2.8L18 20l-.8-2.2L15 17l2.2-.8L18 14Z"],
    inpaint:["M4 16 15 5l4 4L8 20H4v-4Z","m13-9 2-2 4 4-2 2"], face:["M12 22a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z","M9 10h.01","M15 10h.01","M8.5 15c2 2 5 2 7 0"],
    control:["M12 3v18","M3 12h18","M7 7h10v10H7z"], light:["M9 18h6","M10 22h4","M8 14a6 6 0 1 1 8 0c-1 1-1 2-1 4H9c0-2 0-3-1-4Z"],
    repair:["M14 6 18 2l4 4-4 4","M16 8 8 16H4v-4L16 8Z","M5 5h5","M7.5 2.5v5"], wand:["m4 20 11-11","m14 4 1-2 1 2 2 1-2 1-1 2-1-2-2-1 2-1Z","m19 13 .7-1.5.8 1.5 1.5.8-1.5.7-.8 1.5-.7-1.5-1.5-.7 1.5-.8Z"],
    settings:["M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z","M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21h-4v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3v-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.5V3h4v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.5 1h.1v4h-.1a1.7 1.7 0 0 0-1.5 1Z"],
    palette:["M12 3a9 9 0 0 0 0 18h1.5a2 2 0 0 0 0-4H12a2 2 0 0 1 0-4h5a4 4 0 0 0 4-4c0-3.3-4-6-9-6Z","M7.5 10h.01","M9 6.5h.01","M14 6h.01","M17 9h.01"]
  };
  return <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name].map((d, index) => <path d={d} key={index} />)}</svg>;
}

// Retained for backward-compatible preset imports.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const styleOptions = [
  ["Photoreal", "Natural light · lifelike detail", "photo"],
  ["Cinematic", "Dramatic lighting · filmic tone", "cinema"],
  ["Renaissance", "Classic art · oil painting", "renaissance"],
  ["Fantasy", "Mythical · ethereal worlds", "fantasy"],
  ["Concept Art", "Design · matte painting", "concept"],
  ["Surreal", "Dreamlike · imaginative", "surreal"],
  ["Minimal", "Clean · simplified", "minimal"],
  ["Cyberpunk", "Neon · dystopian", "cyber"],
];

// Retained for backward-compatible preset imports.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const stylePrompts: Record<string, string> = {
  Photoreal: "photorealistic, natural light, lifelike detail",
  Cinematic: "cinematic lighting, film still, dramatic composition",
  Renaissance:
    "Renaissance oil painting, chiaroscuro, classical composition, fine glazing",
  Fantasy: "epic fantasy art, ethereal atmosphere, intricate worldbuilding",
  "Concept Art": "professional concept art, matte painting, detailed design",
  Surreal: "surrealist art, dreamlike, imaginative visual metaphor",
  Minimal: "minimalist, clean composition, refined simplicity",
  Cyberpunk: "cyberpunk, neon light, futuristic dystopian atmosphere",
};

const uiText: Record<string, Record<string, string>> = {
  en:{new:"New Generation",home:"Home",create:"Create",library:"Library",presets:"Presets",workflows:"Workflows",models:"Models",loras:"LoRA",embeddings:"Embeddings",tools:"TOOLS",imagePrompt:"Image to Prompt",enhance:"Enhance Image",imageImage:"Image to Image",inpaint:"Inpainting",face:"Face Studio",control:"Control Net",relight:"Relight (IC-Light)",repair:"Repair Studio",smart:"Smart Edit (JoyAI)",settings:"Settings",appearance:"Appearance",textSize:"Text size",displaySize:"Display size",language:"Language",typeface:"Typeface",bold:"Bold text"},
  pt:{new:"Nova geração",home:"Início",create:"Criar",library:"Biblioteca",presets:"Predefinições",workflows:"Fluxos de trabalho",models:"Modelos",loras:"LoRA",embeddings:"Incorporações",tools:"FERRAMENTAS",imagePrompt:"Imagem para prompt",enhance:"Melhorar imagem",imageImage:"Imagem para imagem",inpaint:"Retoque",face:"Estúdio facial",control:"Control Net",relight:"Reiluminar (IC-Light)",repair:"Estúdio de reparação",smart:"Edição inteligente (JoyAI)",settings:"Definições",appearance:"Aparência",textSize:"Tamanho do texto",displaySize:"Tamanho do ecrã",language:"Idioma",typeface:"Tipo de letra",bold:"Texto em negrito"},
  it:{new:"Nuova generazione",home:"Home",create:"Crea",library:"Libreria",presets:"Preimpostazioni",workflows:"Flussi di lavoro",models:"Modelli",loras:"LoRA",embeddings:"Incorporamenti",tools:"STRUMENTI",imagePrompt:"Immagine in prompt",enhance:"Migliora immagine",imageImage:"Immagine in immagine",inpaint:"Inpainting",face:"Studio volto",control:"Control Net",relight:"Riillumina (IC-Light)",repair:"Studio riparazione",smart:"Modifica intelligente (JoyAI)",settings:"Impostazioni",appearance:"Aspetto",textSize:"Dimensione testo",displaySize:"Dimensione schermo",language:"Lingua",typeface:"Carattere",bold:"Testo in grassetto"},
  es:{new:"Nueva generación",home:"Inicio",create:"Crear",library:"Biblioteca",presets:"Preajustes",workflows:"Flujos de trabajo",models:"Modelos",loras:"LoRA",embeddings:"Incrustaciones",tools:"HERRAMIENTAS",imagePrompt:"Imagen a prompt",enhance:"Mejorar imagen",imageImage:"Imagen a imagen",inpaint:"Relleno",face:"Estudio facial",control:"Control Net",relight:"Reiluminar (IC-Light)",repair:"Estudio de reparación",smart:"Edición inteligente (JoyAI)",settings:"Ajustes",appearance:"Apariencia",textSize:"Tamaño del texto",displaySize:"Tamaño de pantalla",language:"Idioma",typeface:"Tipografía",bold:"Texto en negrita"},
  fr:{new:"Nouvelle génération",home:"Accueil",create:"Créer",library:"Bibliothèque",presets:"Préréglages",workflows:"Flux de travail",models:"Modèles",loras:"LoRA",embeddings:"Intégrations",tools:"OUTILS",imagePrompt:"Image vers prompt",enhance:"Améliorer l’image",imageImage:"Image vers image",inpaint:"Inpainting",face:"Studio visage",control:"Control Net",relight:"Rééclairer (IC-Light)",repair:"Studio de réparation",smart:"Édition intelligente (JoyAI)",settings:"Paramètres",appearance:"Apparence",textSize:"Taille du texte",displaySize:"Taille d’affichage",language:"Langue",typeface:"Police",bold:"Texte en gras"},
  de:{new:"Neue Generierung",home:"Start",create:"Erstellen",library:"Bibliothek",presets:"Voreinstellungen",workflows:"Arbeitsabläufe",models:"Modelle",loras:"LoRA",embeddings:"Einbettungen",tools:"WERKZEUGE",imagePrompt:"Bild zu Prompt",enhance:"Bild verbessern",imageImage:"Bild zu Bild",inpaint:"Inpainting",face:"Gesichtsstudio",control:"Control Net",relight:"Neu beleuchten (IC-Light)",repair:"Reparaturstudio",smart:"Intelligente Bearbeitung (JoyAI)",settings:"Einstellungen",appearance:"Darstellung",textSize:"Textgröße",displaySize:"Anzeigegröße",language:"Sprache",typeface:"Schriftart",bold:"Fetter Text"}
};

function sizeLabel(bytes: number) {
  return bytes > 1e9
    ? `${(bytes / 1073741824).toFixed(1)} GB`
    : `${(bytes / 1048576).toFixed(0)} MB`;
}
function previewUrl(model?: Model) {
  return model?.preview ? `/api/preview?path=${model.preview}` : "";
}

const trainingShotOptions: Record<string, string[][]> = {
  Character: [["Front","full-body front view, neutral standing pose"],["Three-quarter","three-quarter full-body view, natural confident pose"],["Profile","clean side profile, full body visible"],["Back","rear view, looking slightly over shoulder"],["Action","dynamic physically plausible action pose"],["Seated","natural seated pose, hands visible"],["Portrait","head-and-shoulders close portrait"],["Environment","wide environmental portrait, complete figure visible"]],
  Object: [["Front","front product view"],["Three-quarter","three-quarter product view"],["Side","strict side view"],["Back","rear product view"],["Top","top-down view"],["Detail","macro detail view of materials and construction"],["In Use","object shown naturally in use"],["Environment","wide contextual scene containing the object"]],
  Landscape: [["Wide","wide establishing landscape"],["Ground","eye-level ground view"],["Aerial","high aerial view"],["Low Angle","low viewpoint with foreground depth"],["Morning","same landscape at soft morning light"],["Golden Hour","same landscape at warm golden-hour light"],["Storm","same landscape in dramatic weather"],["Detail","close environmental detail from the same location"]],
  Style: [["Portrait","portrait composition demonstrating the style"],["Full Body","full-body subject demonstrating the style"],["Architecture","architectural scene demonstrating the style"],["Landscape","natural landscape demonstrating the style"],["Interior","detailed interior demonstrating the style"],["Object","single-object study demonstrating the style"],["Action","dynamic action composition demonstrating the style"],["Lighting","dramatic lighting study demonstrating the style"]],
};
const promptCardLibrary: Record<string,{label:string;options:{name:string;prompt:string}[]}> = {
  Subject:{label:"Subject",options:[{name:"Warrior",prompt:"formidable heroic warrior with coherent equipment and identity"},{name:"Furniture",prompt:"professionally designed furniture with realistic construction"},{name:"Architecture",prompt:"coherent architectural subject with structurally believable details"},{name:"Creature",prompt:"distinct fantasy creature with consistent anatomy and markings"},{name:"Portrait",prompt:"single identifiable portrait subject with stable facial identity"}]},
  Material:{label:"Material",options:[{name:"Aged Bronze",prompt:"aged bronze with natural verdigris and worn polished edges"},{name:"Black Steel",prompt:"dark forged steel with subtle wear and realistic reflections"},{name:"Mahogany",prompt:"polished mahogany with deep warm natural grain"},{name:"Marble",prompt:"white marble with subtle grey mineral veining"},{name:"Leather",prompt:"weathered leather with natural creases and stitching"}]},
  Pose:{label:"Pose",options:[{name:"Neutral",prompt:"balanced neutral presentation pose"},{name:"Defensive",prompt:"controlled defensive stance with believable weight"},{name:"Action",prompt:"dynamic action pose with correct anatomy and physical balance"},{name:"Seated",prompt:"natural seated pose with clear silhouette"},{name:"In Use",prompt:"shown naturally in practical use"}]},
  Environment:{label:"Environment",options:[{name:"Studio",prompt:"clean professional studio presentation"},{name:"Castle",prompt:"historic stone castle interior with atmospheric depth"},{name:"Battlefield",prompt:"dramatic battlefield environment with layered depth"},{name:"Forest",prompt:"natural forest environment with realistic vegetation"},{name:"Frozen",prompt:"frozen wasteland with blowing snow and cold atmosphere"}]},
  Lighting:{label:"Lighting",options:[{name:"Cinematic",prompt:"cinematic directional lighting with controlled contrast"},{name:"Golden Hour",prompt:"warm golden-hour light with long soft shadows"},{name:"Moonlight",prompt:"cool moonlight with subtle rim lighting"},{name:"Torchlight",prompt:"warm flickering torchlight with realistic falloff"},{name:"Product",prompt:"soft professional product lighting revealing material detail"}]},
  Camera:{label:"Camera",options:[{name:"Full View",prompt:"complete subject visible in frame"},{name:"Low Angle",prompt:"slight low-angle camera with a powerful perspective"},{name:"Close Detail",prompt:"macro close detail with shallow depth of field"},{name:"Three-quarter",prompt:"three-quarter camera view showing depth and construction"},{name:"Wide",prompt:"wide contextual composition with foreground-to-background depth"}]}
};
const datasetPoseOptions = [["Front","full-body front view, neutral pose, complete subject visible"],["Three-quarter","three-quarter view, natural balanced pose"],["Profile","clean side profile, full subject visible"],["Back","rear view, design and silhouette clearly visible"],["Action","dynamic but anatomically correct action pose"],["Seated","natural seated pose with hands visible"],["Portrait","head-and-shoulders portrait with consistent identity"],["Environment","wide environmental view with complete subject visible"]] as const;
const artStyleOptions = [
  [
    "Photoreal",
    "photorealistic, natural light, realistic skin, lifelike detail",
  ],
  [
    "Cinematic",
    "cinematic lighting, film still, dramatic composition, color grading",
  ],
  [
    "High Renaissance",
    "High Renaissance oil painting, classical balance, sfumato, fine glazing",
  ],
  [
    "Michelangelo Influence",
    "monumental anatomy, sculptural form, Renaissance drama",
  ],
  [
    "Leonardo Influence",
    "sfumato, subtle expression, atmospheric depth, Renaissance painting",
  ],
  [
    "Raphael Influence",
    "graceful figures, harmony, High Renaissance composition",
  ],
  ["Baroque", "Baroque painting, chiaroscuro, theatrical light, rich movement"],
  [
    "Caravaggio Influence",
    "tenebrism, intense realism, dramatic directional light",
  ],
  [
    "Rembrandt Influence",
    "warm shadow, expressive portraiture, painterly depth",
  ],
  ["Vermeer Influence", "quiet interior, soft window light, precise color"],
  [
    "Impressionism",
    "visible brushwork, luminous color, fleeting natural light",
  ],
  ["Monet Influence", "atmospheric light, soft color, impressionist brushwork"],
  ["Van Gogh Influence", "expressive impasto, rhythmic strokes, intense color"],
  [
    "Art Nouveau",
    "elegant curves, botanical ornament, decorative illustration",
  ],
  [
    "Hokusai Influence",
    "Japanese woodblock composition, bold contour, flat color",
  ],
  ["Fantasy", "epic fantasy art, ethereal atmosphere, intricate worldbuilding"],
  [
    "Dark Fantasy",
    "dark fantasy, Gothic grandeur, ominous atmosphere, dramatic detail",
  ],
  [
    "Concept Art",
    "professional concept art, matte painting, detailed production design",
  ],
  [
    "Surrealism",
    "surrealist art, dream logic, symbolic imagery, uncanny juxtaposition",
  ],
  ["Cyberpunk", "cyberpunk, neon technology, futuristic dystopian city"],
  [
    "Steampunk",
    "steampunk, brass machinery, Victorian design, intricate mechanisms",
  ],
  [
    "Minimal",
    "minimalist, clean geometry, restrained palette, refined simplicity",
  ],
  [
    "Watercolor",
    "watercolor painting, transparent washes, soft edges, textured paper",
  ],
  [
    "Charcoal Drawing",
    "expressive charcoal drawing, tonal study, textured strokes",
  ],
  [
    "Marble Sculpture",
    "carved marble sculpture, museum lighting, classical form",
  ],
  ["Bronze Monument", "patinated bronze, heroic scale, monumental sculpture"],
] as const;
const artStylePrompts: Record<string, string> =
  Object.fromEntries(artStyleOptions);

const joyaiSuggestions = [
  {
    label: "Repair hands",
    prompt:
      "Correct only the visible hands and fingers. Give each hand five anatomically natural fingers with accurate joints, perspective, grip, and contact with nearby objects. Preserve the face, identity, clothing, body pose, background, lighting, camera position, and framing.",
  },
  {
    label: "Repair face",
    prompt:
      "Correct the face and eyes with natural symmetry, realistic pupils, matching eye direction, accurate eyelids, natural skin texture, and correct facial anatomy. Preserve the person's identity, expression, hairstyle, age, clothing, pose, background, lighting, and composition.",
  },
  {
    label: "Change posture",
    prompt:
      "Adjust the person's posture to [describe the new posture]. Correct the shoulders, arms, hands, torso, legs, and balance naturally. Preserve the face, identity, clothing, hairstyle, background, lighting, camera position, and composition.",
  },
  {
    label: "Move an object",
    prompt:
      "Move the [person or object] from [current location] to [new location]. Preserve its appearance, scale, orientation, lighting, shadows, background, camera position, and every other element. Change only its position.",
  },
  {
    label: "Rotate subject",
    prompt:
      "Rotate the [person or object] to show the [front, left, right, or rear] view. Preserve its identity, design, colors, proportions, surroundings, lighting, and camera framing.",
  },
  {
    label: "Change camera",
    prompt:
      "Move the camera. Camera rotation: Yaw [angle] degrees, Pitch [angle] degrees. Camera zoom: [in, out, or unchanged]. Keep the 3D scene static; only change the viewpoint. Preserve all subjects, clothing, objects, environment, and lighting.",
  },
  {
    label: "Replace background",
    prompt:
      "Replace only the background with [describe the new background]. Preserve the main subject's face, identity, pose, clothing, proportions, edges, foreground objects, and lighting direction. Blend the new environment naturally.",
  },
  {
    label: "Strict preservation",
    prompt:
      "Make only this change: [describe one exact change]. Preserve the face, identity, expression, hairstyle, clothing, pose, objects, background, lighting, colors, camera position, perspective, framing, and composition. Do not add or remove anything else.",
  },
] as const;

const cameraProfiles = [
  { id: "none", name: "No Camera Look", format: "Neutral", lens: "Model default", focal: "Auto", aperture: "Auto", use: "Illustration and unrestricted composition", icon: "neutral", prompt: "" },
  { id: "s35", name: "Studio Digital S35", format: "Cinema", lens: "Modern spherical prime", focal: "35 mm", aperture: "f/4", use: "Balanced cinematic scenes and groups", icon: "cinema", prompt: "shot on a professional Super 35 digital cinema camera, modern spherical 35mm prime lens, f/4 aperture, natural perspective, cinematic color science" },
  { id: "portrait", name: "Full Frame Portrait", format: "Digital", lens: "Portrait prime", focal: "85 mm", aperture: "f/1.8", use: "Faces, fashion and shallow backgrounds", icon: "portrait", prompt: "shot on a professional full-frame camera, 85mm portrait prime lens, f/1.8 aperture, shallow depth of field, soft background separation, natural facial perspective" },
  { id: "medium", name: "Medium Format Fine Art", format: "Medium format", lens: "Standard prime", focal: "80 mm", aperture: "f/5.6", use: "Renaissance, fine art and rich detail", icon: "medium", prompt: "medium-format fine-art photography, 80mm standard prime lens, f/5.6 aperture, exceptional tonal depth, refined detail, gentle perspective compression" },
  { id: "wide", name: "Architectural Wide", format: "Full frame", lens: "Rectilinear wide", focal: "24 mm", aperture: "f/8", use: "Interiors, monuments and landscapes", icon: "wide", prompt: "professional architectural photography, rectilinear 24mm wide-angle lens, f/8 aperture, deep focus, corrected vertical lines, expansive spatial perspective" },
  { id: "documentary", name: "Documentary Street", format: "Compact full frame", lens: "Reportage prime", focal: "35 mm", aperture: "f/2.8", use: "Natural people, action and environments", icon: "street", prompt: "documentary photography, 35mm reportage prime lens, f/2.8 aperture, candid natural perspective, available light, authentic environmental detail" },
  { id: "telephoto", name: "Cinematic Telephoto", format: "Cinema", lens: "Telephoto prime", focal: "135 mm", aperture: "f/2.8", use: "Compressed backgrounds and dramatic portraits", icon: "tele", prompt: "cinematic telephoto photography, 135mm prime lens, f/2.8 aperture, strong background compression, isolated subject, soft cinematic bokeh" },
  { id: "macro", name: "Macro Detail", format: "Full frame", lens: "1:1 macro", focal: "100 mm", aperture: "f/8", use: "Eyes, jewelry, textures and small objects", icon: "macro", prompt: "high-resolution macro photography, 100mm 1:1 macro lens, f/8 aperture, precise close focus, controlled depth of field, extremely detailed textures" },
  { id: "vintage", name: "Vintage Cinema", format: "35mm film", lens: "Anamorphic", focal: "50 mm", aperture: "T2.8", use: "Period drama and expressive cinematic images", icon: "vintage", prompt: "shot on 35mm motion-picture film, vintage 50mm anamorphic lens at T2.8, organic film grain, gentle halation, oval bokeh, subtle cinematic flare" },
] as const;

export default function Home() {
  const [models, setModels] = useState<Model[]>([]);
  const [loras, setLoras] = useState<Model[]>([]);
  const [modelQuery, setModelQuery] = useState("");
  const [loraQuery, setLoraQuery] = useState("");
  const [checkpoint, setCheckpoint] = useState("");
  const [selectedLoras, setSelectedLoras] = useState<LoraChoice[]>([]);
  const [prompt, setPrompt] = useState(
    "A bronze archer priestess performing inside a circular temple arena, ornate columns, epic scale, ultra-detailed",
  );
  const [negative, setNegative] = useState(
    "blurry, low quality, deformed hands, extra fingers, watermark, text",
  );
  const [style, setStyle] = useState("Fantasy");
  const [cameraProfile, setCameraProfile] = useState("none");
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraYaw, setCameraYaw] = useState(0);
  const [cameraPitch, setCameraPitch] = useState(0);
  const [cameraZoom, setCameraZoom] = useState("unchanged");
  const [tab, setTab] = useState<"prompt" | "negative" | "advanced">("prompt");
  const [steps, setSteps] = useState(28);
  const [cfg, setCfg] = useState(7);
  const [seed, setSeed] = useState(-1);
  const [width, setWidth] = useState(768);
  const [height, setHeight] = useState(768);
  const [sampler, setSampler] = useState("euler");
  const [engine, setEngine] = useState("starting");
  const [counts, setCounts] = useState({ checkpoints: 0, loras: 0, vae: 0, embeddings: 0 });
  const [navPanel, setNavPanel] = useState<"home" | "library" | "presets" | "workflows" | "embeddings" | "settings" | "">("");
  const [embeddings, setEmbeddings] = useState<Model[]>([]);
  const [embeddingSearch, setEmbeddingSearch] = useState("");
  const [maintenanceState, setMaintenanceState] = useState("");
  const [uiTheme, setUiTheme] = useState(() => localStorage.getItem("froja-theme") || "forge");
  const [fontScale, setFontScale] = useState(() => Number(localStorage.getItem("froja-font-scale") || 110));
  const [textScale, setTextScale] = useState(() => Number(localStorage.getItem("froja-text-scale") || 110));
  const [fontFamily, setFontFamily] = useState(() => localStorage.getItem("froja-font-family") || "modern");
  const [iconStyle, setIconStyle] = useState(() => localStorage.getItem("froja-icon-style") || "outline");
  const [boldText, setBoldText] = useState(() => localStorage.getItem("froja-bold-text") === "true");
  const [uiLanguage, setUiLanguage] = useState(() => localStorage.getItem("froja-language") || "en");
  const [customBackground, setCustomBackground] = useState(() => localStorage.getItem("froja-custom-background") || "/themes/teal-studio.png");
  const [pendingBackground, setPendingBackground] = useState("");
  const [themeFileName, setThemeFileName] = useState("");
  const [themeUploadState, setThemeUploadState] = useState("Choose or drop an image");
  const t = (key: string) => uiText[uiLanguage]?.[key] || uiText.en[key] || key;
  const [job, setJob] = useState("");
  const [jobState, setJobState] = useState("Idle");
  const [previewTab, setPreviewTab] = useState<"preview" | "history" | "favorites">("preview");
  const [generationHistory, setGenerationHistory] = useState<GenerationRecord[]>(() => {
    try { return JSON.parse(localStorage.getItem("froja-generation-history") || "[]"); }
    catch { return []; }
  });
  const [image, setImage] = useState(
    "/generated/renaissance-inventor-healthcheck.png",
  );
  const [previewZoomOpen, setPreviewZoomOpen] = useState(false);
  const [previewZoom, setPreviewZoom] = useState(100);
  const [outputFolderState, setOutputFolderState] = useState("");
  const [hasGenerated, setHasGenerated] = useState(false);
  const [contextLora, setContextLora] = useState<{
    item: Model;
    x: number;
    y: number;
  } | null>(null);
  const [error, setError] = useState("");
  const [modelOpen, setModelOpen] = useState(false);
  const [loraOpen, setLoraOpen] = useState(false);
  const [assisting, setAssisting] = useState<"enhance" | "create" | "">("");
  const [imagePromptOpen, setImagePromptOpen] = useState(false);
  const [imagePromptSource, setImagePromptSource] = useState("");
  const [imagePromptResult, setImagePromptResult] = useState("");
  const [imagePromptDetail, setImagePromptDetail] = useState("balanced");
  const [imagePromptState, setImagePromptState] = useState("Ready");
  const [enhanceOpen, setEnhanceOpen] = useState(false);
  const [enhanceSource, setEnhanceSource] = useState("");
  const [enhanceResult, setEnhanceResult] = useState("");
  const [enhanceDownloadName, setEnhanceDownloadName] = useState("froja-enhanced.jpg");
  const [enhanceState, setEnhanceState] = useState("Ready");
  const [enhanceSharpen, setEnhanceSharpen] = useState(22);
  const [enhanceDenoise, setEnhanceDenoise] = useState(8);
  const [enhanceDust, setEnhanceDust] = useState(0);
  const [enhanceBrightness, setEnhanceBrightness] = useState(0);
  const [enhanceContrast, setEnhanceContrast] = useState(4);
  const [enhanceColor, setEnhanceColor] = useState(2);
  const [enhanceScale, setEnhanceScale] = useState(1);
  const [enhanceSize, setEnhanceSize] = useState("");
  const [enhanceZoom, setEnhanceZoom] = useState(100);
  const [faceOpen, setFaceOpen] = useState(false);
  const [faceSource, setFaceSource] = useState("");
  const [faceTarget, setFaceTarget] = useState("");
  const [faceJob, setFaceJob] = useState("");
  const [faceResult, setFaceResult] = useState("");
  const [faceState, setFaceState] = useState("Ready");
  const [faceRestore, setFaceRestore] = useState("codeformer-v0.1.0.pth");
  const [toolMode, setToolMode] = useState<
    "img2img" | "inpaint" | "controlnet" | ""
  >("");
  const [toolSource, setToolSource] = useState("");
  const [toolMask, setToolMask] = useState("");
  const [toolJob, setToolJob] = useState("");
  const [toolResult, setToolResult] = useState("");
  const [toolState, setToolState] = useState("Ready");
  const [toolStrength, setToolStrength] = useState(0.65);
  const [controlMode, setControlMode] = useState("canny");
  const [relightOpen, setRelightOpen] = useState(false);
  const [relightSource, setRelightSource] = useState("");
  const [relightDirection, setRelightDirection] = useState("left");
  const [relightStrength, setRelightStrength] = useState(0.8);
  const [relightX, setRelightX] = useState(0.2);
  const [relightY, setRelightY] = useState(0.5);
  const [relightQuality, setRelightQuality] = useState<"soft" | "hard">("soft");
  const [relightBrightness, setRelightBrightness] = useState(50);
  const [relightColor, setRelightColor] = useState("#ffffff");
  const [relightJob, setRelightJob] = useState("");
  const [relightResult, setRelightResult] = useState("");
  const [relightState, setRelightState] = useState("Ready");
  const [repairOpen, setRepairOpen] = useState(false);
  const [repairSource, setRepairSource] = useState("");
  const [repairMode, setRepairMode] = useState("face");
  const [repairStrength, setRepairStrength] = useState(0.4);
  const [repairJob, setRepairJob] = useState("");
  const [repairResult, setRepairResult] = useState("");
  const [repairState, setRepairState] = useState("Ready");
  const [joyaiOpen, setJoyaiOpen] = useState(false);
  const [joyaiSource, setJoyaiSource] = useState("");
  const [joyaiInstruction, setJoyaiInstruction] = useState("");
  const [joyaiSteps, setJoyaiSteps] = useState(20);
  const [joyaiJob, setJoyaiJob] = useState("");
  const [joyaiResult, setJoyaiResult] = useState("");
  const [joyaiState, setJoyaiState] = useState("Ready");
  const [repairBox, setRepairBox] = useState<{
    x: number;
    y: number;
    w: number;
    h: number;
  } | null>(null);
  const [repairDrag, setRepairDrag] = useState<{ x: number; y: number } | null>(
    null,
  );

  const [datasetOpen,setDatasetOpen]=useState(false); const [datasetItems,setDatasetItems]=useState<DatasetItem[]>([]); const [datasetTrigger,setDatasetTrigger]=useState(""); const [datasetSize,setDatasetSize]=useState(768); const [datasetCrop,setDatasetCrop]=useState(true); const [datasetState,setDatasetState]=useState("Ready"); const [datasetBasePrompt,setDatasetBasePrompt]=useState(""); const [datasetVariation,setDatasetVariation]=useState("Front"); const [datasetJob,setDatasetJob]=useState(""); const [datasetJobState,setDatasetJobState]=useState("Ready"); const [datasetPendingPrompt,setDatasetPendingPrompt]=useState("");
  const [trainingInspectId,setTrainingInspectId]=useState(""); const [trainingInspectZoom,setTrainingInspectZoom]=useState(1);
  const [trainingStudioOpen,setTrainingStudioOpen]=useState(false); const [trainingSessionLoaded,setTrainingSessionLoaded]=useState(false); const [trainingSession,setTrainingSession]=useState("Froja_Training_001"); const [trainingType,setTrainingType]=useState("Character"); const [trainingConcept,setTrainingConcept]=useState(""); const [trainingShots,setTrainingShots]=useState<string[]>(trainingShotOptions.Character.map(item=>item[0])); const [trainingEnvironments,setTrainingEnvironments]=useState<string[]>(["Studio"]); const [trainingImagesPerSetup,setTrainingImagesPerSetup]=useState(1); const [trainingQueue,setTrainingQueue]=useState<TrainingTask[]>([]); const [trainingJob,setTrainingJob]=useState(""); const [trainingPending,setTrainingPending]=useState({name:"",position:"",environment:"",prompt:""}); const [trainingResults,setTrainingResults]=useState<TrainingResult[]>([]); const [trainingState,setTrainingState]=useState("Ready"); const [trainingGalleryGroup,setTrainingGalleryGroup]=useState("Setup");
  const [materialReferences,setMaterialReferences]=useState<MaterialReference[]>([]); const [materialFolder,setMaterialFolder]=useState(""); const [materialLibraryState,setMaterialLibraryState]=useState("Ready");
  const [promptCardsOpen,setPromptCardsOpen]=useState(false); const [promptCardSelections,setPromptCardSelections]=useState<Record<string,string>>({}); const [promptCardConsistency,setPromptCardConsistency]=useState(true); const [customPromptCard,setCustomPromptCard]=useState(""); const [customPromptCards,setCustomPromptCards]=useState<string[]>(()=>{try{return JSON.parse(localStorage.getItem("froja-custom-prompt-cards")||"[]")}catch{return[]}});
  useEffect(()=>{localStorage.setItem("froja-custom-prompt-cards",JSON.stringify(customPromptCards));},[customPromptCards]);
  const randomizePromptCards=()=>{const next:Record<string,string>={};Object.entries(promptCardLibrary).forEach(([category,group])=>{next[category]=group.options[Math.floor(Math.random()*group.options.length)].name;});setPromptCardSelections(next);};
  const addCustomPromptCard=()=>{const value=customPromptCard.trim();if(!value)return;setCustomPromptCards(items=>items.includes(value)?items:[...items,value]);setPromptCardSelections(items=>({...items,Custom:value}));setCustomPromptCard("");};
  const trainingInspectIndex=trainingResults.findIndex(item=>item.id===trainingInspectId); const trainingInspectItem=trainingInspectIndex>=0?trainingResults[trainingInspectIndex]:undefined;
  const stepTrainingInspection=(direction:number)=>{if(!trainingResults.length)return;const next=(Math.max(0,trainingInspectIndex)+direction+trainingResults.length)%trainingResults.length;setTrainingInspectId(trainingResults[next].id);setTrainingInspectZoom(1);};
  useEffect(()=>{if(!trainingInspectId)return;const handler=(event:KeyboardEvent)=>{if(event.key==="Escape")setTrainingInspectId("");if(event.key==="ArrowLeft")stepTrainingInspection(-1);if(event.key==="ArrowRight")stepTrainingInspection(1);};window.addEventListener("keydown",handler);return()=>window.removeEventListener("keydown",handler);},[trainingInspectId,trainingInspectIndex,trainingResults]);
  const [appearanceOpen,setAppearanceOpen]=useState(true); const [appearanceCategory,setAppearanceCategory]=useState("Materials"); const [appearanceSearch,setAppearanceSearch]=useState(""); const [appearanceSelections,setAppearanceSelections]=useState<Record<string,string>>({}); const [appearanceColor,setAppearanceColor]=useState("#3c8f8b"); const [appearanceHarmony,setAppearanceHarmony]=useState("Cool Analogous"); const [appearanceRoughness,setAppearanceRoughness]=useState(62); const [appearanceWeathering,setAppearanceWeathering]=useState(38); const [appearanceConsistency,setAppearanceConsistency]=useState(true); const [appearanceTarget,setAppearanceTarget]=useState("Main object / subject");

  const loadMaterialLibrary=async()=>{setMaterialLibraryState("Scanning…");try{const response=await fetch("/api/materials");const result=await response.json();if(!response.ok)throw new Error(result.error||"Material scan failed.");setMaterialReferences(Array.isArray(result.items)?result.items:[]);setMaterialFolder(result.folder||"");setMaterialLibraryState(`${result.items?.length||0} local material${result.items?.length===1?"":"s"} found`);}catch(caught){setMaterialLibraryState(caught instanceof Error?caught.message:"Material scan failed.");}};
  useEffect(()=>{loadMaterialLibrary();},[]);
  const currentAppearancePresets=useMemo(()=>appearanceCategory==="Materials"?[...appearanceLibrary.Materials.presets,...materialReferences.map(item=>({name:item.name,prompt:item.prompt,preview:`url("${item.preview}") center/cover no-repeat`}))]:appearanceLibrary[appearanceCategory].presets,[appearanceCategory,materialReferences]);
  useEffect(() => {
    const load = async () => {
      try {
        const [status, m, l] = await Promise.all([
          fetch("/api/status").then((r) => r.json()),
          fetch("/api/models?type=checkpoints&limit=5000").then((r) =>
            r.json(),
          ),
          fetch("/api/models?type=loras&limit=5000").then((r) => r.json()),
        ]);
        setEngine(status.engine);
        setCounts(status.counts);
        setModels(m.items);
        setLoras(l.items);
        if (!checkpoint && m.items.length) {
          const safe = m.items.find(
            (item: Model) =>
              !["Flux", "Z-Image", "Qwen", "ACE Audio"].includes(
                item.architecture,
              ),
          );
          setCheckpoint((safe || m.items[0]).relative);
        }
      } catch {
        setEngine("offline");
      }
    };
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, [checkpoint]);

  useEffect(() => {
    if (!job) return;
    const timer = setInterval(async () => {
      const result = await fetch(`/api/jobs/${job}`).then((r) => r.json());
      setJobState(result.status);
      if (result.status === "complete" && result.images?.[0]) {
        setImage(result.images[0]);
        const record: GenerationRecord = {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          image: result.images[0], created: new Date().toISOString(), favorite: false,
          prompt, negative, model: checkpoint, style, seed, width, height, steps, cfg, sampler,
        };
        setGenerationHistory((items) => [record, ...items.filter((item) => item.image !== record.image)].slice(0, 200));
        setHasGenerated(true);
        setJob("");
        setJobState("Complete");
      }
      if (result.status === "failed" || result.status === "error") {
        setError(result.error || "Generation failed");
        setJob("");
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [job, prompt, negative, checkpoint, style, seed, width, height, steps, cfg, sampler]);

  useEffect(() => {
    localStorage.setItem("froja-theme", uiTheme);
    localStorage.setItem("froja-font-scale", String(fontScale));
    localStorage.setItem("froja-text-scale", String(textScale));
    localStorage.setItem("froja-font-family", fontFamily);
    localStorage.setItem("froja-icon-style", iconStyle);
    localStorage.setItem("froja-bold-text", String(boldText));
    localStorage.setItem("froja-language", uiLanguage);
    if (customBackground) localStorage.setItem("froja-custom-background", customBackground);
    else localStorage.removeItem("froja-custom-background");
  }, [uiTheme, fontScale, textScale, fontFamily, iconStyle, boldText, uiLanguage, customBackground]);

  useEffect(() => { localStorage.setItem("froja-generation-history", JSON.stringify(generationHistory.slice(0, 200))); }, [generationHistory]);
  useEffect(() => {
    if (!faceJob) return;
    const timer = setInterval(async () => {
      const result = await fetch(`/api/extension-jobs/${faceJob}`).then((r) =>
        r.json(),
      );
      setFaceState(result.status);
      if (result.status === "complete" && result.images?.[0]) {
        setFaceResult(result.images[0]);
        setFaceJob("");
        setFaceState("Complete");
      }
      if (result.status === "failed" || result.status === "error") {
        setError(
          typeof result.error === "string"
            ? result.error
            : "Face Studio failed.",
        );
        setFaceJob("");
        setFaceState("Error");
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [faceJob]);
  useEffect(() => {
    if (!toolJob) return;
    const timer = setInterval(async () => {
      const result = await fetch(`/api/extension-jobs/${toolJob}`).then((r) =>
        r.json(),
      );
      setToolState(result.status);
      if (result.status === "complete" && result.images?.[0]) {
        setToolResult(result.images[0]);
        setToolJob("");
        setToolState("Complete");
      }
      if (result.status === "failed" || result.status === "error") {
        setError(
          typeof result.error === "string"
            ? result.error
            : "Image tool failed.",
        );
        setToolJob("");
        setToolState("Error");
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [toolJob]);
  useEffect(() => {
    if (!relightJob) return;
    const timer = setInterval(async () => {
      const result = await fetch(`/api/extension-jobs/${relightJob}`).then(
        (r) => r.json(),
      );
      setRelightState(result.status);
      if (result.status === "complete" && result.images?.[0]) {
        setRelightResult(result.images[0]);
        setRelightJob("");
        setRelightState("Complete");
      }
      if (result.status === "failed" || result.status === "error") {
        setError(
          typeof result.error === "string"
            ? result.error
            : "Relighting failed.",
        );
        setRelightJob("");
        setRelightState("Error");
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [relightJob]);
  useEffect(() => {
    if (!repairJob) return;
    const timer = setInterval(async () => {
      const result = await fetch(`/api/extension-jobs/${repairJob}`).then((r) =>
        r.json(),
      );
      setRepairState(result.status);
      if (result.status === "complete" && result.images?.[0]) {
        setRepairResult(result.images[0]);
        setRepairJob("");
        setRepairState("Complete");
      }
      if (result.status === "failed" || result.status === "error") {
        setError(
          typeof result.error === "string" ? result.error : "Repair failed.",
        );
        setRepairJob("");
        setRepairState("Error");
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [repairJob]);
  useEffect(() => {
    if (!joyaiJob) return;
    const timer = setInterval(async () => {
      const result = await fetch(`/api/joyai-jobs/${joyaiJob}`).then((r) =>
        r.json(),
      );
      setJoyaiState(result.status);
      if (result.status === "complete" && result.images?.[0]) {
        setJoyaiResult(result.images[0]);
        setJoyaiJob("");
        setJoyaiState("Complete");
      }
      if (result.status === "failed" || result.status === "error") {
        setError(
          typeof result.error === "string" ? result.error : "JoyAI Smart Edit failed.",
        );
        setJoyaiJob("");
        setJoyaiState("Error");
      }
    }, 2500);
    return () => clearInterval(timer);
  }, [joyaiJob]);
  useEffect(() => {
    const close = () => setContextLora(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, []);

  useEffect(() => {
    if (!loras.length) return;
    const tags = [...prompt.matchAll(/<lora:([^:>]+)(?::([0-9.]+))?>/gi)];
    if (!tags.length) return;
    const timer = window.setTimeout(() => {
      setSelectedLoras((currentItems) => {
        const next = [...currentItems];
        for (const tag of tags) {
          const found = loras.find(
            (item) =>
              item.name.replace(/\.safetensors$/i, "").toLowerCase() ===
              tag[1].trim().toLowerCase(),
          );
          if (
            found &&
            !next.some((item) => item.path === found.path) &&
            next.length < 8
          )
            next.push({ ...found, strength: Number(tag[2] || 1) });
        }
        return next.length === currentItems.length ? currentItems : next;
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [prompt, loras]);

  const visibleModels = useMemo(
    () =>
      [...models]
        .filter((m) => m.name.toLowerCase().includes(modelQuery.toLowerCase()))
        .sort((a, b) => {
          const aVerified = ["Flux2-Klein", "Mage-Flow", "Krea-2"].includes(a.architecture) && a.size < 10 * 1024 ** 3;
          const bVerified = ["Flux2-Klein", "Mage-Flow", "Krea-2"].includes(b.architecture) && b.size < 10 * 1024 ** 3;
          return Number(bVerified) - Number(aVerified) || a.name.localeCompare(b.name);
        })
        .slice(0, 500),
    [models, modelQuery],
  );
  const verifiedCompactModels = useMemo(
    () => models
      .filter((m) => ["Flux2-Klein", "Mage-Flow", "Krea-2"].includes(m.architecture) && m.size < 10 * 1024 ** 3)
      .sort((a, b) => a.name.localeCompare(b.name)),
    [models],
  );
  const visibleLoras = useMemo(
    () =>
      [...loras]
        .filter((m) =>
          `${m.name} ${(m.triggers || []).join(" ")}`
            .toLowerCase()
            .includes(loraQuery.toLowerCase()),
        )
        .sort((a, b) =>
          Number(selectedLoras.some((item) => item.path === b.path)) - Number(selectedLoras.some((item) => item.path === a.path)) ||
          Number(Boolean(b.preview)) - Number(Boolean(a.preview)) ||
          a.name.localeCompare(b.name),
        )
        .slice(0, 1000),
    [loras, loraQuery, selectedLoras],
  );
  const current = models.find((m) => m.relative === checkpoint);
  const currentCamera = cameraProfiles.find((camera) => camera.id === cameraProfile) || cameraProfiles[0];
  const needsSpecialWorkflow =
    !!current && ["Qwen", "ACE Audio", "Flux2-Large"].includes(current.architecture);
  const isZImage = current?.architecture === "Z-Image";
  const isKrea2 = current?.architecture === "Krea-2";
  const isFlux2Klein = current?.architecture === "Flux2-Klein";
  const isMageFlow = current?.architecture === "Mage-Flow";
  const isFlux = current?.architecture === "Flux" || isFlux2Klein;
  const isDarkBeast = isKrea2 && /darkbeast/i.test(current?.name || "");

  useEffect(() => {
    if (!isKrea2) return;
    const timer = window.setTimeout(() => {
      setSteps(8);
      setCfg(1);
      setSampler("er_sde");
      // Keep the compact Krea GGUF workflow safe on 12 GB GPUs.  Users can
      // still choose 1024px manually, but selecting the model must not force
      // an unnecessary jump in VRAM use.
      setWidth((value) => Math.max(value, 512));
      setHeight((value) => Math.max(value, 512));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isKrea2]);

  useEffect(() => {
    if (!isZImage) return;
    const timer = window.setTimeout(() => {
      setSteps(4);
      setCfg(1);
      setSampler("res_multistep");
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isZImage]);

  useEffect(() => {
    if (!isFlux) return;
    const timer = window.setTimeout(() => {
      setSteps(isFlux2Klein ? 4 : 8);
      setCfg(1);
      setSampler("euler");
      setWidth((value) => isFlux2Klein ? 512 : Math.max(value, 768));
      setHeight((value) => isFlux2Klein ? 512 : Math.max(value, 768));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isFlux, isFlux2Klein]);

  useEffect(() => {
    if (!isMageFlow) return;
    const timer = window.setTimeout(() => {
      setSteps(4);
      setCfg(1);
      setSampler("euler");
      setWidth(512);
      setHeight(512);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isMageFlow]);

  function toggleLora(lora: Model) {
    const chosen = selectedLoras.some((item) => item.path === lora.path);
    if (chosen) {
      setSelectedLoras((items) =>
        items.filter((item) => item.path !== lora.path),
      );
      return;
    }
    if (selectedLoras.length >= 8) {
      setError("You can attach up to eight LoRAs at once.");
      return;
    }
    setSelectedLoras((items) => [...items, { ...lora, strength: 0.8 }]);
    const words = (lora.triggers || []).filter(
      (word) => !prompt.toLowerCase().includes(word.toLowerCase()),
    );
    if (words.length)
      setPrompt((value) =>
        `${words.join(", ")}, ${value}`.replace(/^,\s*/, ""),
      );
    setError("");
  }

  function prepareLora(lora: Model) {
    if (!selectedLoras.some((item) => item.path === lora.path))
      toggleLora(lora);
    setLoraOpen(false);
    setTab("prompt");
    setContextLora(null);
  }

  async function setLoraPreview(lora: Model) {
    if (!hasGenerated) {
      setError(
        "Generate an image in Froja first, then right-click the LoRA and assign it as the preview.",
      );
      setContextLora(null);
      return;
    }
    const response = await fetch("/api/loras/set-preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lora_path: lora.path, image_url: image }),
    });
    const result = await response.json();
    if (!response.ok) {
      setError(result.error || "Could not save the LoRA preview.");
      setContextLora(null);
      return;
    }
    const refreshed = await fetch(
      "/api/models?type=loras&limit=5000&refresh=1",
    ).then((r) => r.json());
    setLoras(refreshed.items);
    setError("");
    setContextLora(null);
  }

  async function promptAssist(mode: "enhance" | "create") {
    if (!prompt.trim()) {
      setError("Write a short idea first, then ask Froja to develop it.");
      return;
    }
    setAssisting(mode);
    setError("");
    try {
      const response = await fetch("/api/prompt-assist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, mode, model: "qwen3.5:4b" }),
      });
      const result = await response.json();
      if (!response.ok)
        throw new Error(result.error || "Prompt assistant failed.");
      setPrompt(result.prompt);
      setTab("prompt");
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Prompt assistant failed.",
      );
    } finally {
      setAssisting("");
    }
  }

  async function analyzeImagePrompt() {
    if (!imagePromptSource) {
      setError("Choose an image first.");
      return;
    }
    setError("");
    setImagePromptState("Analyzing image");
    try {
      const response = await fetch("/api/image-to-prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image: imagePromptSource,
          detail: imagePromptDetail,
          model: "llama3.2-vision:latest",
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Image analysis failed.");
      setImagePromptResult(result.prompt);
      setImagePromptState("Complete");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Image analysis failed.");
      setImagePromptState("Error");
    }
  }

  function useImagePrompt() {
    if (!imagePromptResult.trim()) return;
    setPrompt(imagePromptResult.trim());
    setTab("prompt");
    setImagePromptOpen(false);
  }

  async function imageUrlToDataUrl(source: string) {
    if (source.startsWith("data:image/")) return source;
    const blob = await fetch(source).then((response) => { if (!response.ok) throw new Error("Image could not be read."); return response.blob(); });
    return await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = reject; reader.readAsDataURL(blob); });
  }
  async function addCurrentToDataset() {
    try {
      const source = await imageUrlToDataUrl(image);
      setDatasetItems((items) => [...items, { id:crypto.randomUUID(), image:source, name:`froja-${items.length + 1}.png`, caption:prompt.trim(), state:"Caption ready" }]);
      setDatasetOpen(true); setDatasetState("Current Froja image added. Review its caption before export.");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not add the current image."); }
  }
  function addDatasetFiles(files?: FileList | null) {
    [...(files || [])].slice(0, Math.max(0, 200 - datasetItems.length)).forEach((file) => {
      if (!file.type.startsWith("image/") || file.size > 25 * 1024 * 1024) return;
      const reader = new FileReader(); reader.onload = () => setDatasetItems((items) => [...items, { id:crypto.randomUUID(), image:String(reader.result), name:file.name, caption:"", state:"Needs caption" }]); reader.readAsDataURL(file);
    });
    setDatasetState("Images added. Captions remain under your control.");
  }
  async function inspectDatasetItem(id: string) {
    const item = datasetItems.find((entry) => entry.id === id); if (!item) return;
    setDatasetItems((items) => items.map((entry) => entry.id === id ? {...entry, state:"Reading embedded data…"} : entry));
    try {
      const response = await fetch("/api/image-metadata", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({image:item.image})});
      const result = await response.json(); if (!response.ok) throw new Error(result.error || "Metadata check failed.");
      if (!result.found) {
        setDatasetItems((items) => items.map((entry) => entry.id === id ? {...entry, state:"No embedded generation data — use Create Caption Locally", metadata:"No prompt or settings were stored inside this file."} : entry)); return;
      }
      const details = [result.source, result.model && `Model: ${result.model}`, result.seed && `Seed: ${result.seed}`, result.steps && `Steps: ${result.steps}`, result.cfg && `CFG: ${result.cfg}`, result.sampler && `Sampler: ${result.sampler}`, `${result.width} × ${result.height}`, result.negative && `Negative: ${result.negative}`].filter(Boolean).join(" · ");
      setDatasetItems((items) => items.map((entry) => entry.id === id ? {...entry, caption:result.prompt || entry.caption, state:"Original generation data recovered", metadata:details} : entry));
      if (result.prompt && !datasetBasePrompt) setDatasetBasePrompt(result.prompt);
    } catch (caught) { setDatasetItems((items) => items.map((entry) => entry.id === id ? {...entry, state:caught instanceof Error ? caught.message : "Metadata check failed"} : entry)); }
  }
  useEffect(() => {
    if (!trainingStudioOpen || trainingSessionLoaded) return;
    fetch("/api/training-session").then(response=>response.json()).then(saved=>{
      if(saved.session)setTrainingSession(saved.session);
      if(saved.concept)setTrainingConcept(saved.concept);
      if(saved.type&&trainingShotOptions[saved.type])setTrainingType(saved.type);
      if(Array.isArray(saved.results))setTrainingResults(saved.results);
      setTrainingSessionLoaded(true);
    }).catch(()=>setTrainingSessionLoaded(true));
  },[trainingStudioOpen,trainingSessionLoaded]);

  useEffect(() => {
    if(!trainingSessionLoaded)return;
    const timer=window.setTimeout(()=>fetch("/api/training-session",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session:trainingSession,concept:trainingConcept,type:trainingType,results:trainingResults})}).catch(()=>undefined),500);
    return()=>window.clearTimeout(timer);
  },[trainingSessionLoaded,trainingSession,trainingConcept,trainingType,trainingResults]);
  function startTrainingSet() {
    if (!trainingConcept.trim()) { setTrainingState("Describe the subject, landscape, object, or style first."); return; }
    if (!checkpoint) { setTrainingState("Choose a working Froja checkpoint first."); return; }
    if (!trainingShots.length) { setTrainingState("Select at least one variation."); return; }
    if (!trainingEnvironments.length) { setTrainingState("Select at least one environment."); return; }
    const tasks: TrainingTask[] = [];
    for (const position of trainingShots) for (const environment of trainingEnvironments) for (let copy=1; copy<=trainingImagesPerSetup; copy++) tasks.push({name:`${position} · ${environment} · ${copy}`,position,environment});
    if (tasks.length > 24) { setTrainingState(`This plan contains ${tasks.length} images. Reduce it to 24 or fewer for safe review and GPU use.`); return; }
    setTrainingResults([]); setTrainingQueue(tasks); setTrainingState(`Preparing ${tasks.length} controlled variations…`);
  }

  useEffect(() => {
    if (trainingJob || !trainingQueue.length) return;
    const task=trainingQueue[0]; const name=task.name; const guide=trainingShotOptions[trainingType].find(([item])=>item===task.position)?.[1] || task.position;
    const appearancePrompt=Object.entries(appearanceSelections).map(([category,value])=>{ const preset=appearanceLibrary[category]?.presets.find(item=>item.name===value)||(category==="Materials"?materialReferences.find(item=>item.name===value):undefined); return preset?`${appearanceTarget.toLowerCase()}: ${preset.prompt}`:`${category.toLowerCase()}: ${value}`; }).join(", "); const cardEntries=promptCardConsistency?Object.entries(promptCardSelections):Object.entries(promptCardSelections).map(([category])=>{const options=promptCardLibrary[category]?.options||[];return [category,options.length?options[Math.floor(Math.random()*options.length)].name:promptCardSelections[category]];}); const wildcardPrompt=cardEntries.map(([category,value])=>promptCardLibrary[category]?.options.find(item=>item.name===value)?.prompt||value).filter(Boolean).join(", "); const composed=`${trainingConcept.trim()}, ${guide}, ${task.environment.toLowerCase()} environment${appearancePrompt?`, ${appearancePrompt}`:""}${wildcardPrompt?`, prompt cards: ${wildcardPrompt}`:""}, ${appearanceHarmony.toLowerCase()} color harmony led by ${appearanceColor}, surface roughness ${appearanceRoughness} percent, weathering ${appearanceWeathering} percent, ${appearanceConsistency?"strictly preserve these appearance choices across all eight views":"allow controlled appearance variation"}, preserve the exact same core subject or location design, consistent materials, shapes, colors and artistic language, distinct composition from the other dataset images, high detail, clean LoRA training reference`;
    setTrainingPending({name,position:task.position,environment:task.environment,prompt:composed}); setTrainingState(`Queueing ${name} (${trainingResults.length+1} of ${trainingResults.length+trainingQueue.length})…`);
    fetch("/api/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({checkpoint,architecture:current?.architecture,prompt:composed,negative_prompt:[negative,"duplicate composition, repeated camera angle, inconsistent identity, changed design, low detail, blur, watermark, text, malformed anatomy"].filter(Boolean).join(", "),steps,cfg,seed:Math.floor(Math.random()*4294967295),width,height,sampler,scheduler:"normal",loras:selectedLoras.map((l)=>({name:l.relative,strength:l.strength}))})})
      .then(async response=>{const result=await response.json();if(!response.ok)throw new Error(result.error||"Generation failed.");setTrainingJob(result.prompt_id);setTrainingState(`Generating ${name}…`);})
      .catch(caught=>{setTrainingQueue([]);setTrainingState(caught instanceof Error?caught.message:"Generation failed.");});
  },[trainingQueue,trainingJob,trainingType,trainingConcept,trainingResults.length,checkpoint,current?.architecture,negative,steps,cfg,width,height,sampler,selectedLoras,appearanceSelections,appearanceColor,appearanceHarmony,appearanceRoughness,appearanceWeathering,appearanceConsistency,appearanceTarget,promptCardSelections,promptCardConsistency]);

  useEffect(() => {
    if(!trainingJob)return;
    const timer=window.setInterval(async()=>{
      try{
        const result=await fetch(`/api/jobs/${trainingJob}`).then(response=>response.json());
        if(result.status==="complete"&&result.images?.[0]){
          const source=await imageUrlToDataUrl(result.images[0]);
          setTrainingResults(items=>[...items,{id:crypto.randomUUID(),image:source,name:trainingPending.name,position:trainingPending.position,environment:trainingPending.environment,prompt:trainingPending.prompt,approved:false}]);
          setTrainingQueue(items=>items.slice(1));setTrainingJob("");setTrainingState(`${trainingPending.name} completed. Continuing the set…`);
        }else if(result.status==="failed"||result.status==="error"){setTrainingQueue([]);setTrainingJob("");setTrainingState(result.error||`${trainingPending.name} failed.`);}
      }catch{setTrainingQueue([]);setTrainingJob("");setTrainingState("Froja lost contact with the image engine.");}
    },1500);return()=>window.clearInterval(timer);
  },[trainingJob,trainingPending]);

  function sendApprovedTrainingImages() {
    const approved=trainingResults.filter(item=>item.approved);
    if(!approved.length){setTrainingState("Approve at least one strong image first.");return;}
    setDatasetItems(items=>[...items,...approved.map(item=>({id:crypto.randomUUID(),image:item.image,name:`training-${item.name.toLowerCase().replace(/[^a-z0-9]+/g,"-")}.png`,caption:item.prompt,state:"Approved in Training Set Studio"}))]);
    setDatasetBasePrompt(trainingConcept);setTrainingState(`${approved.length} approved image${approved.length===1?"":"s"} sent to LoRA Dataset Studio.`);
  }
  async function generateDatasetVariation() {
    const base = (datasetBasePrompt || datasetItems[0]?.caption || prompt).trim();
    if (!base) { setDatasetState("Add an image with a recovered caption, or write a base subject/style prompt first."); return; }
    if (!checkpoint) { setDatasetState("Choose a working Froja checkpoint first."); return; }
    const pose = datasetPoseOptions.find(([name]) => name === datasetVariation)?.[1] || datasetPoseOptions[0][1];
    const variationPrompt = `${base}, ${pose}, preserve the same character identity, clothing design, materials, color palette, artistic style and lighting language, clean LoRA training reference, anatomically correct hands and body`;
    setDatasetJobState("Queueing"); setDatasetState(`Generating ${datasetVariation} variation…`); setDatasetPendingPrompt(variationPrompt);
    try {
      const response = await fetch("/api/generate", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({checkpoint, architecture:current?.architecture, prompt:variationPrompt, negative_prompt:[negative,"different character, changed costume, changed color palette, duplicate person, extra limbs, cropped body"].filter(Boolean).join(", "), steps, cfg, seed:Math.floor(Math.random()*4294967295), width, height, sampler, scheduler:"normal", loras:selectedLoras.map((l)=>({name:l.relative,strength:l.strength}))})});
      const result=await response.json(); if(!response.ok) throw new Error(result.error || "Variation generation failed.");
      setDatasetJob(result.prompt_id); setDatasetJobState("Running");
    } catch(caught) { setDatasetJobState("Error"); setDatasetState(caught instanceof Error ? caught.message : "Variation generation failed."); }
  }

  useEffect(() => {
    if (!datasetJob) return;
    const timer=window.setInterval(async()=>{
      try {
        const result=await fetch(`/api/jobs/${datasetJob}`).then((response)=>response.json()); setDatasetJobState(result.status);
        if(result.status==="complete" && result.images?.[0]){
          const source=await imageUrlToDataUrl(result.images[0]);
          setDatasetItems((items)=>[...items,{id:crypto.randomUUID(),image:source,name:`variation-${datasetVariation.toLowerCase().replace(/[^a-z0-9]+/g,"-")}.png`,caption:datasetPendingPrompt,state:"Generated variation · caption ready"}]);
          setDatasetJob(""); setDatasetJobState("Complete"); setDatasetState(`${datasetVariation} generated and added to this dataset.`);
        } else if(result.status==="failed" || result.status==="error") { setDatasetJob(""); setDatasetJobState("Error"); setDatasetState(result.error || "Variation generation failed."); }
      } catch { setDatasetJob(""); setDatasetJobState("Error"); setDatasetState("Froja lost contact with the image engine while checking this variation."); }
    },1500);
    return()=>window.clearInterval(timer);
  },[datasetJob,datasetPendingPrompt,datasetVariation]);
  async function captionDatasetItem(id: string) {
    const item = datasetItems.find((entry) => entry.id === id); if (!item) return;
    setDatasetItems((items) => items.map((entry) => entry.id === id ? {...entry, state:"Analyzing locally…"} : entry));
    try {
      const response = await fetch("/api/image-to-prompt", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({image:item.image, detail:"balanced", model:"llama3.2-vision:latest"}) });
      const result = await response.json(); if (!response.ok) throw new Error(result.error || "Captioning failed.");
      setDatasetItems((items) => items.map((entry) => entry.id === id ? {...entry, caption:result.prompt, state:"Caption ready"} : entry));
    } catch (caught) { setDatasetItems((items) => items.map((entry) => entry.id === id ? {...entry, state:(caught instanceof Error && /refused|urlopen|10061/i.test(caught.message)) ? "Local visual captioning is offline — start Ollama, or use Read Original Prompt & Settings" : caught instanceof Error ? caught.message : "Captioning failed"} : entry)); }
  }
  async function exportDataset() {
    if (!datasetItems.length) return; setDatasetState("Building safe dataset ZIP…");
    try {
      const response = await fetch("/api/dataset/export", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({items:datasetItems, trigger:datasetTrigger, size:datasetSize, crop:datasetCrop}) });
      if (!response.ok) { const result=await response.json(); throw new Error(result.error || "Export failed."); }
      const url=URL.createObjectURL(await response.blob()); const anchor=document.createElement("a"); anchor.href=url; anchor.download="froja-lora-dataset.zip"; anchor.click(); URL.revokeObjectURL(url);
      setDatasetState(`Exported ${datasetItems.length} image/caption pair${datasetItems.length === 1 ? "" : "s"}. Originals were untouched.`);
    } catch (caught) { setDatasetState(caught instanceof Error ? caught.message : "Export failed."); }
  }
  async function runEnhancement() {
    if (!enhanceSource) {
      setError("Choose an image first.");
      return;
    }
    setError("");
    setEnhanceState("Enhancing image");
    setEnhanceResult("");
    try {
      const response = await fetch("/api/enhance-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image: enhanceSource,
          sharpen: enhanceSharpen,
          denoise: enhanceDenoise,
          dust: enhanceDust,
          brightness: enhanceBrightness,
          contrast: enhanceContrast,
          color: enhanceColor,
          scale: enhanceScale,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Image enhancement failed.");
      setEnhanceResult(result.image);
      setEnhanceDownloadName(`froja-enhanced-${Date.now()}.jpg`);
      setEnhanceSize(`${result.width} × ${result.height}`);
      setEnhanceState("Complete");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Image enhancement failed.");
      setEnhanceState("Error");
    }
  }

  function applyEnhancePreset(preset: "gentle" | "photo" | "restore") {
    if (preset === "gentle") {
      setEnhanceSharpen(22); setEnhanceDenoise(8); setEnhanceDust(0);
      setEnhanceBrightness(0); setEnhanceContrast(4); setEnhanceColor(2);
    } else if (preset === "photo") {
      setEnhanceSharpen(38); setEnhanceDenoise(15); setEnhanceDust(0);
      setEnhanceBrightness(3); setEnhanceContrast(8); setEnhanceColor(7);
    } else {
      setEnhanceSharpen(28); setEnhanceDenoise(24); setEnhanceDust(38);
      setEnhanceBrightness(4); setEnhanceContrast(7); setEnhanceColor(4);
    }
  }

  function loadFaceFile(
    file: File | undefined,
    setter: (value: string) => void,
  ) {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("Choose a PNG, JPEG, or WebP image.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setter(String(reader.result || ""));
    reader.readAsDataURL(file);
  }
  async function runFaceSwap() {
    if (!faceSource || !faceTarget) {
      setError("Choose both a source face and a target image.");
      return;
    }
    setError("");
    setFaceState("Queueing");
    setFaceResult("");
    const response = await fetch("/api/face-swap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_image: faceSource,
        target_image: faceTarget,
        source_face: 0,
        target_face: 0,
        restoration: faceRestore,
        visibility: 0.85,
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      setError(result.error || "Face Studio failed.");
      setFaceState("Error");
      return;
    }
    setFaceJob(result.prompt_id);
    setFaceState("Running");
  }
  function openImageTool(mode: "img2img" | "inpaint" | "controlnet") {
    setToolMode(mode);
    setToolSource("");
    setToolMask("");
    setToolResult("");
    setToolState("Ready");
  }

  async function runImageTool() {
    if (!toolMode || !toolSource) {
      setError("Choose a source image first.");
      return;
    }
    if (toolMode === "inpaint" && !toolMask) {
      setError("Choose a black-and-white mask. White areas will be replaced.");
      return;
    }
    setError("");
    setToolState("Queueing");
    setToolResult("");
    const response = await fetch("/api/image-tool", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: toolMode,
        source_image: toolSource,
        mask_image: toolMask,
        prompt,
        width,
        height,
        seed,
        strength: toolStrength,
        control_mode: controlMode,
        control_strength: toolStrength,
        loras: selectedLoras.map((l) => ({
          name: l.relative,
          strength: l.strength,
        })),
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      setError(result.error || "Image tool failed.");
      setToolState("Error");
      return;
    }
    setToolJob(result.prompt_id);
    setToolState("Running");
  }
  async function runRelight() {
    if (!relightSource) {
      setError("Choose an image to relight first.");
      return;
    }
    setError("");
    setRelightState("Queueing");
    setRelightResult("");
    const response = await fetch("/api/relight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_image: relightSource,
        prompt: `${prompt}, ${artStylePrompts[style]}, realistic ${relightDirection} directional illumination, ${relightQuality} light, light color ${relightColor}, ${relightBrightness}% brightness`,
        negative_prompt: negative,
        direction: relightDirection,
        strength: relightStrength,
        softness: relightQuality,
        brightness: relightBrightness,
        color: relightColor,
        light_x: relightX,
        light_y: relightY,
        width: Math.min(width, 1024),
        height: Math.min(height, 1024),
        seed,
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      setError(result.error || "Relighting failed.");
      setRelightState("Error");
      return;
    }
    setRelightJob(result.prompt_id);
    setRelightState("Running");
  }

  function setRelightPreset(direction: string) {
    const positions: Record<string, [number, number]> = {
      top: [0.5, 0.08], front: [0.5, 0.5], right: [0.92, 0.5],
      left: [0.08, 0.5], back: [0.5, 0.82], bottom: [0.5, 0.92],
    };
    const [x, y] = positions[direction] || positions.front;
    setRelightDirection(direction);
    setRelightX(x);
    setRelightY(y);
  }

  function moveRelightPoint(event: React.PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.max(0.04, Math.min(0.96, (event.clientX - rect.left) / rect.width));
    const y = Math.max(0.04, Math.min(0.96, (event.clientY - rect.top) / rect.height));
    setRelightX(x);
    setRelightY(y);
    if (y < 0.25) setRelightDirection("top");
    else if (y > 0.75) setRelightDirection("bottom");
    else if (x < 0.3) setRelightDirection("left");
    else if (x > 0.7) setRelightDirection("right");
    else setRelightDirection("center");
  }

  function repairPointerPosition(event: React.PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    };
  }
  function startRepairBox(event: React.PointerEvent<HTMLDivElement>) {
    if (repairMode !== "box") return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = repairPointerPosition(event);
    setRepairDrag(point);
    setRepairBox({ ...point, w: 0, h: 0 });
  }
  function moveRepairBox(event: React.PointerEvent<HTMLDivElement>) {
    if (!repairDrag || repairMode !== "box") return;
    const point = repairPointerPosition(event);
    setRepairBox({
      x: Math.min(repairDrag.x, point.x),
      y: Math.min(repairDrag.y, point.y),
      w: Math.abs(point.x - repairDrag.x),
      h: Math.abs(point.y - repairDrag.y),
    });
  }

  async function runRepair() {
    if (!repairSource) {
      setError("Choose an image to repair first.");
      return;
    }
    const repairPrompts: Record<string, string> = {
      face: "natural symmetrical face, detailed eyes, realistic skin, correct facial anatomy, preserve identity and expression",
      hands:
        "anatomically correct hands, five natural fingers on each hand, correct joints and grip, preserve pose",
      body: "anatomically correct human body, natural balanced posture, realistic proportions, correct limbs, preserve clothing and identity",
      box: "repair only the selected area naturally, match surrounding lighting and texture, preserve everything outside the selection",
    };
    if (
      repairMode === "box" &&
      (!repairBox || repairBox.w < 0.01 || repairBox.h < 0.01)
    ) {
      setError("Drag a box over the face, eye, hand, or damaged area first.");
      return;
    }
    setError("");
    setRepairState("Queueing");
    setRepairResult("");
    const response = await fetch("/api/repair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_image: repairSource,
        mode: repairMode,
        prompt: `${repairPrompts[repairMode]}, ${prompt}`,
        negative_prompt: `${negative}, deformed, disfigured, extra fingers, missing fingers, fused fingers, extra limbs, bad anatomy`,
        strength: repairStrength,
        box: repairBox,
        seed,
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      setError(result.error || "Repair failed.");
      setRepairState("Error");
      return;
    }
    setRepairJob(result.prompt_id);
    setRepairState("Running");
  }

  async function runJoyaiEdit() {
    if (!joyaiSource) {
      setError("Choose an image for Smart Edit first.");
      return;
    }
    if (!joyaiInstruction.trim()) {
      setError("Describe the change you want JoyAI to make.");
      return;
    }
    setError("");
    setJoyaiState("Queueing — first load can take several minutes");
    setJoyaiResult("");
    const response = await fetch("/api/joyai-edit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_image: joyaiSource,
        instruction: joyaiInstruction,
        negative_prompt: negative,
        steps: joyaiSteps,
        seed,
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      setError(result.error || "JoyAI Smart Edit failed.");
      setJoyaiState("Error");
      return;
    }
    setJoyaiJob(result.prompt_id);
    setJoyaiState("Running — approximately 10–12 minutes");
  }

  function sendCameraMoveToJoyai() {
    setJoyaiInstruction(
      `Move the camera. Camera rotation: Yaw ${cameraYaw} degrees, Pitch ${cameraPitch} degrees. Camera zoom: ${cameraZoom}. Keep the 3D scene static; only change the viewpoint. Preserve every subject, face, identity, pose, clothing, object, environment, lighting, color, and spatial relationship.`,
    );
    setCameraOpen(false);
    setJoyaiOpen(true);
  }

  async function generate() {
    if (!checkpoint) {
      setError("Choose a checkpoint first.");
      return;
    }
    if (needsSpecialWorkflow) {
      setError(
        `${current?.architecture} uses a dedicated workflow that is not enabled in the standard SD/SDXL generator yet.`,
      );
      return;
    }
    setError("");
    setJobState("Queueing");
    const styled = [prompt, artStylePrompts[style], currentCamera.prompt]
      .filter(Boolean)
      .join(", ");
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        checkpoint,
        architecture: current?.architecture,
        prompt: styled,
        negative_prompt: negative,
        steps,
        cfg,
        seed,
        width,
        height,
        sampler,
        scheduler: "normal",
        loras: selectedLoras.map((l) => ({
          name: l.relative,
          strength: l.strength,
        })),
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      setError(result.error || "Generation failed");
      setJobState("Error");
      return;
    }
    setJob(result.prompt_id);
    setJobState("Running");
  }

  function protectAnatomyAndPose() {
    const poseGuide = "anatomically correct natural human anatomy, physically plausible pose, exactly two arms and two hands, five natural fingers on each hand, correct grip and joint alignment, coherent object geometry, no duplicated limbs or objects, sharp detailed face and eyes";
    setPrompt((value) => value.toLowerCase().includes("physically plausible pose") ? value : [value.trim(), poseGuide].filter(Boolean).join(", "));
    setNegative((value) => [value.trim(), "extra limbs, extra arms, extra hands, extra fingers, missing fingers, fused fingers, malformed hands, broken wrists, disconnected limbs, duplicated objects, impossible pose, deformed face, crossed eyes"].filter(Boolean).join(", "));
    setMaintenanceState("Anatomy and complex-pose guidance added to the prompt.");
  }

  async function openOutputFolder() {
    setOutputFolderState("Opening…");
    try {
      const response = await fetch("/api/open-output", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_url: image }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not open the output folder.");
      setOutputFolderState(result.selected ? "Image selected in folder" : "Output folder opened");
    } catch (openError) {
      setOutputFolderState(openError instanceof Error ? openError.message : "Could not open output folder");
    }
  }

  async function openNavigation(panel: typeof navPanel) {
    setNavPanel(panel);
    if (panel === "embeddings" || panel === "library") {
      try {
        const data = await fetch("/api/models?type=embeddings&limit=5000").then((response) => response.json());
        setEmbeddings(data.items || []);
      } catch {
        setMaintenanceState("Could not read the linked embedding folders.");
      }
    }
  }

  function newGeneration() {
    setPrompt(""); setNegative(""); setSelectedLoras([]); setSeed(-1);
    setError(""); setJobState("Idle"); setTab("prompt"); setNavPanel("");
  }

  function saveCurrentPreset() {
    const preset = { prompt, negative, style, steps, cfg, width, height, sampler, checkpoint };
    localStorage.setItem("froja-user-preset", JSON.stringify(preset));
    setMaintenanceState("My Preset saved in Froja.");
  }

  function loadCurrentPreset() {
    const raw = localStorage.getItem("froja-user-preset");
    if (!raw) { setMaintenanceState("No saved preset yet."); return; }
    const preset = JSON.parse(raw);
    setPrompt(preset.prompt || ""); setNegative(preset.negative || ""); setStyle(preset.style || "Fantasy");
    setSteps(preset.steps || 28); setCfg(preset.cfg || 7); setWidth(preset.width || 768); setHeight(preset.height || 768);
    setSampler(preset.sampler || "euler"); if (preset.checkpoint) setCheckpoint(preset.checkpoint);
    setMaintenanceState("My Preset loaded."); setNavPanel("");
  }

  function downloadSettingsBackup() {
    const backup = { version: 1, created: new Date().toISOString(), preset: localStorage.getItem("froja-user-preset"), note: "Froja settings only. Models are linked and are not copied." };
    const url = URL.createObjectURL(new Blob([JSON.stringify(backup, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `froja-settings-${new Date().toISOString().slice(0, 10)}.json`; anchor.click(); URL.revokeObjectURL(url);
    setMaintenanceState("Settings backup downloaded. No model files were copied.");
  }

  async function refreshLibrary() {
    setMaintenanceState("Refreshing linked folders…");
    const [status, modelData, loraData, embeddingData] = await Promise.all([
      fetch("/api/status?refresh=1").then((r) => r.json()),
      fetch("/api/models?type=checkpoints&refresh=1&limit=5000").then((r) => r.json()),
      fetch("/api/models?type=loras&refresh=1&limit=5000").then((r) => r.json()),
      fetch("/api/models?type=embeddings&refresh=1&limit=5000").then((r) => r.json()),
    ]);
    setCounts(status.counts); setModels(modelData.items || []); setLoras(loraData.items || []); setEmbeddings(embeddingData.items || []);
    setMaintenanceState("Library refreshed successfully.");
  }

  function openHistoryRecord(record: GenerationRecord) {
    setImage(record.image); setPrompt(record.prompt); setNegative(record.negative); setStyle(record.style);
    setSeed(record.seed); setWidth(record.width); setHeight(record.height); setSteps(record.steps); setCfg(record.cfg); setSampler(record.sampler);
    if (record.model) setCheckpoint(record.model); setPreviewTab("preview"); setHasGenerated(true);
  }

  function toggleFavorite(record?: GenerationRecord) {
    const target = record || generationHistory.find((item) => item.image === image);
    if (!target) { const record: GenerationRecord = { id:`${Date.now()}-favorite`, image, created:new Date().toISOString(), favorite:true, prompt, negative, model:checkpoint, style, seed, width, height, steps, cfg, sampler }; setGenerationHistory((items) => [record, ...items].slice(0, 200)); return; }
    setGenerationHistory((items) => items.map((item) => item.id === target.id ? {...item, favorite:!item.favorite} : item));
  }

  async function copyGenerationInfo() {
    await navigator.clipboard.writeText(`Model: ${current?.name || checkpoint}\nSeed: ${seed}\nSteps: ${steps}\nSize: ${width} × ${height}\nCFG: ${cfg}\nSampler: ${sampler}\n\nPrompt: ${prompt}\n\nNegative Prompt: ${negative}`);
    setOutputFolderState("Generation information copied");
  }

  async function sendCurrentToEnhance() {
    try {
      const blob = await fetch(image).then((response) => response.blob());
      const dataUrl = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = reject; reader.readAsDataURL(blob); });
      setEnhanceSource(dataUrl); setEnhanceResult(""); setEnhanceState("Ready"); setEnhanceOpen(true);
    } catch { setError("Froja could not send this history image to Enhance Image."); }
  }

  async function loadThemeBackground(file?: File) {
    if (!file) return;
    if (!file.type.startsWith("image/")) { setMaintenanceState("Choose a PNG, JPEG or WebP image."); return; }
    if (file.size > 20 * 1024 * 1024) { setMaintenanceState("Theme images must be smaller than 20 MB."); return; }
    setThemeUploadState("Preparing image…"); setThemeFileName(file.name);
    try {
      const bitmap = await createImageBitmap(file);
      const scale = Math.min(1, 1920 / bitmap.width, 1200 / bitmap.height);
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(bitmap.width * scale)); canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height); bitmap.close();
      setPendingBackground(canvas.toDataURL("image/jpeg", .86));
      setThemeUploadState(`${canvas.width} × ${canvas.height} ready to preview`);
      setMaintenanceState("Background prepared. Select Apply Background to save it.");
    } catch {
      setThemeUploadState("Could not read this image"); setMaintenanceState("The selected image could not be processed. Try PNG, JPEG or WebP.");
    }
  }

  return (
    <main lang={uiLanguage} className={`studio theme-${uiTheme} font-${fontFamily} icons-${iconStyle} ${boldText ? "bold-text" : ""} ${customBackground ? "has-custom-background" : ""}`} style={{ "--font-scale": `${fontScale}%`, "--text-scale": textScale / 100, "--froja-bg-image": customBackground ? `url(${customBackground})` : "none" } as CSSProperties}>
      <aside className="leftbar">
        <div className="logo brand-banner">
          <img src="/froja-brand-banner.png" alt="Froja Image Studio" />
        </div>
        <button className="new-btn" onClick={newGeneration}>
          <Icon name="plus" /> <span>{t("new")}</span><kbd>Ctrl N</kbd>
        </button>
        <nav>
          <button onClick={() => openNavigation("home")}>
            <Icon name="home" /><span>{t("home")}</span>
          </button>
          <button className="active" onClick={() => setNavPanel("")}>
            <Icon name="create" /><span>{t("create")}</span>
          </button>
          <button onClick={() => openNavigation("library")}>
            <Icon name="library" /><span>{t("library")}</span>
            <i>{counts.checkpoints + counts.loras}</i>
          </button>
          <button onClick={() => openNavigation("presets")}>
            <Icon name="preset" /><span>{t("presets")}</span>
          </button>
          <button onClick={() => openNavigation("workflows")}>
            <Icon name="workflow" /><span>{t("workflows")}</span>
          </button>
          <button onClick={() => { setModelQuery(""); setModelOpen(true); }}>
            <Icon name="model" /><span>{t("models")}</span>
            <i>{counts.checkpoints}</i>
          </button>
          <button onClick={() => { setLoraQuery(""); setLoraOpen(true); }}>
            <Icon name="lora" /><span>{t("loras")}</span>
            <i>{counts.loras}</i>
          </button>
          <button onClick={() => openNavigation("embeddings")}>
            <Icon name="embedding" /><span>{t("embeddings")}</span>
            <i>{counts.embeddings || 0}</i>
          </button>
        </nav>
        <p className="nav-label">{t("tools")}</p>
        <nav>
          <button className="image-prompt-nav" onClick={() => setImagePromptOpen(true)}>
            <Icon name="image" /><span>{t("imagePrompt")}</span>
          </button>
          <button className="training-nav" onClick={() => setTrainingStudioOpen(true)}>
            <Icon name="create" /><span>Froja Training Studio</span><i>{trainingResults.length || "New"}</i>
          </button>          <button className="dataset-nav" onClick={() => setDatasetOpen(true)}>
            <Icon name="lora" /><span>LoRA Dataset Studio</span><i>{datasetItems.length || "Add"}</i>
          </button>          <button className="enhance-nav" onClick={() => setEnhanceOpen(true)}>
            <Icon name="enhance" /><span>{t("enhance")}</span>
          </button>
          <button onClick={() => openImageTool("img2img")}>
            <Icon name="image" /><span>{t("imageImage")}</span>
          </button>
          <button onClick={() => openImageTool("inpaint")}>
            <Icon name="inpaint" /><span>{t("inpaint")}</span>
          </button>
          <button onClick={() => setFaceOpen(true)}>
            <Icon name="face" /><span>{t("face")}</span>
          </button>
          <button onClick={() => openImageTool("controlnet")}>
            <Icon name="control" /><span>{t("control")}</span>
          </button>
          <button onClick={() => setRelightOpen(true)}>
            <Icon name="light" /><span>{t("relight")}</span>
          </button>
          <button onClick={() => setRepairOpen(true)}>
            <Icon name="repair" /><span>{t("repair")}</span>
          </button>
          <button onClick={() => setJoyaiOpen(true)}>
            <Icon name="wand" /><span>{t("smart")}</span>
          </button>
        </nav>
        <div className="engine">
          <div>
            <span className={engine} />
            <b>Engine {engine}</b>
          </div>
          <div className="engine-line">
            <i />
          </div>
          <small>
            RTX 4070 Ti <em>{counts.checkpoints} models linked</em>
          </small>
        </div>
        <button className="settings" onClick={() => openNavigation("settings")}><Icon name="settings" /><span>{t("settings")}</span></button>
      </aside>

      <section className="center">
        <header>
          <b className="header-title"><Icon name="create" /> Create</b>
          <span>/</span>
          <small>New Generation</small>
          <div className="header-state">{jobState}</div>
        </header>
        <section className="prompt-panel">
          <div className="tabs">
            <button
              className={tab === "prompt" ? "on" : ""}
              onClick={() => setTab("prompt")}
            >
              Prompt
            </button>
            <button
              className={tab === "negative" ? "on" : ""}
              onClick={() => setTab("negative")}
            >
              Negative Prompt
            </button>
            <button
              className={tab === "advanced" ? "on" : ""}
              onClick={() => setTab("advanced")}
            >
              Advanced
            </button>
          </div>
          {tab === "prompt" && selectedLoras.length > 0 && (
            <div className="prompt-attachments">
              {selectedLoras.map((l) => (
                <div key={l.path}>
                  {previewUrl(l) ? (
                    <img src={previewUrl(l)} alt={`${l.name} preview`} />
                  ) : (
                    <span>Lo</span>
                  )}
                  <b>{l.name.replace(/\.safetensors$/i, "")}</b>
                  <em>{l.strength.toFixed(2)}</em>
                  <button onClick={() => toggleLora(l)}>×</button>
                </div>
              ))}
            </div>
          )}
          {tab !== "advanced" ? (
            <textarea
              value={tab === "prompt" ? prompt : negative}
              onChange={(e) =>
                tab === "prompt"
                  ? setPrompt(e.target.value)
                  : setNegative(e.target.value)
              }
              placeholder={
                tab === "prompt"
                  ? "Describe the image you want…"
                  : "What should Froja avoid?"
              }
            />
          ) : (
            <div className="advanced-grid">
              <label>
                Sampler
                <select
                  value={sampler}
                  onChange={(e) => setSampler(e.target.value)}
                >
                  <option value="res_multistep">Res Multistep (Z-Image)</option>
                  <option value="er_sde">ER-SDE (Krea-2)</option>
                  <option value="euler">Euler</option>
                  <option value="euler_ancestral">Euler a</option>
                  <option value="dpmpp_2m">DPM++ 2M</option>
                </select>
              </label>
              <label>
                Seed
                <input
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(+e.target.value)}
                />
              </label>
              <label>
                Width
                <input
                  type="number"
                  value={width}
                  onChange={(e) => setWidth(+e.target.value)}
                />
              </label>
              <label>
                Height
                <input
                  type="number"
                  value={height}
                  onChange={(e) => setHeight(+e.target.value)}
                />
              </label>
            </div>
          )}
          <div className="prompt-foot">
            <button onClick={() => { setLoraQuery(""); setLoraOpen(true); }}>＋ Attach LoRA</button>
            <button onClick={() => setImagePromptOpen(true)}>
              ▧ Image to Prompt
            </button>
            <button
              disabled={!!assisting}
              onClick={() => promptAssist("enhance")}
            >
              {assisting === "enhance"
                ? "Ollama is writing…"
                : "♢ Enhance with Ollama"}
            </button>
            <button
              disabled={!!assisting}
              onClick={() => promptAssist("create")}
            >
              {assisting === "create"
                ? "Ollama is creating…"
                : "♧ Prompt Helper"}
            </button>
            <button onClick={protectAnatomyAndPose} title="Add stronger instructions for hands, faces, bodies, poses and held objects">
              Anatomy &amp; Pose
            </button>
            <span>
              {(tab === "negative" ? negative : prompt).length} / 2000
            </span>
          </div>
        </section>

        <div className="section-title">
          <b>Styles</b>
          <small>Applied automatically to your prompt</small>
        </div>
        <div className="style-picker">
          <div>
            <span>Selected style</span>
            <b>{style}</b>
            <small>{artStylePrompts[style]}</small>
          </div>
          <label>
            Art Style / Artist Influence
            <select value={style} onChange={(e) => setStyle(e.target.value)}>
              {artStyleOptions.map(([name]) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="section-title camera-title">
          <b>Camera & Lens</b>
          <small>Applied automatically to text-to-image prompts</small>
        </div>
        <button className="camera-summary" onClick={() => setCameraOpen(true)}>
          <span className={`camera-visual ${currentCamera.icon}`}>
            <i className="camera-body-shape" />
            <i className="camera-lens-shape" />
          </span>
          <span>
            <small>{currentCamera.format}</small>
            <b>{currentCamera.name}</b>
            <em>{currentCamera.use}</em>
          </span>
          <span className="camera-spec"><small>Lens</small><b>{currentCamera.lens}</b></span>
          <span className="camera-spec"><small>Focal</small><b>{currentCamera.focal}</b></span>
          <span className="camera-spec"><small>Aperture</small><b>{currentCamera.aperture}</b></span>
          <strong>Change camera →</strong>
        </button>

        <section className="model-settings">
          <div className="section-title">
            <b>Model & Settings</b>
            <small>Live data from your linked folders</small>
          </div>
          <div className="settings-grid">
            <div className="model-block">
              <label>Checkpoint</label>
              <button className="picker" onClick={() => { setModelQuery(""); setModelOpen(true); }}>
                {previewUrl(current) ? (
                  <img
                    className="model-thumb image"
                    src={previewUrl(current)}
                    alt={`${current?.name || "Selected checkpoint"} preview`}
                  />
                ) : (
                  <span className="model-thumb">
                    {current?.architecture?.slice(0, 2) || "AI"}
                  </span>
                )}
                <span>
                  <b>{current?.name || "Choose checkpoint"}</b>
                  <small>
                    {current
                      ? `${current.source} · ${sizeLabel(current.size)}`
                      : "No model selected"}
                  </small>
                </span>
                <em>⌄</em>
              </button>
              <label>LoRAs</label>
              <button
                className="picker compact"
                onClick={() => { setLoraQuery(""); setLoraOpen(true); }}
              >
                <span>
                  <b>
                    {selectedLoras.length
                      ? `${selectedLoras.length} LoRA selected`
                      : "Add LoRA"}
                  </b>
                  <small>
                    {selectedLoras.map((l) => l.name).join(", ") ||
                      (isKrea2
                        ? "Use only LoRAs marked for Krea-2 Raw or Turbo"
                        : "Optional style and character adapters")}
                  </small>
                </span>
                <em>＋</em>
              </button>
            </div>
            <div className="sliders">
              <label>
                Steps <b>{steps}</b>
                <input
                  type="range"
                  min="4"
                  max="60"
                  value={steps}
                  onChange={(e) => setSteps(+e.target.value)}
                />
              </label>
              <label>
                CFG Scale <b>{cfg}</b>
                <input
                  type="range"
                  min="1"
                  max="15"
                  step=".5"
                  value={cfg}
                  onChange={(e) => setCfg(+e.target.value)}
                />
              </label>
              {isKrea2 && (
                <small>Krea-2 Turbo automatically uses its official 8-step distilled settings. Conventional negative prompting is not used.</small>
              )}
              <label>
                Seed{" "}
                <input
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(+e.target.value)}
                />
              </label>
            </div>
            <div className="dimensions">
              <label>
                Image Size
                <select
                  value={`${width}x${height}`}
                  onChange={(e) => {
                    const [w, h] = e.target.value.split("x").map(Number);
                    setWidth(w);
                    setHeight(h);
                  }}
                >
                  <option value="512x512">512 Square</option>
                  <option value="768x768">768 Square</option>
                  <option value="1024x1024">1024 Square</option>
                  <option value="832x1216">832 × 1216 Portrait</option>
                  <option value="1024x1536">1024 × 1536 Portrait</option>
                  <option value="768x1344">768 × 1344 Portrait 9:16</option>
                  <option value="1216x832">1216 × 832 Landscape</option>
                  <option value="1536x1024">1536 × 1024 Landscape</option>
                  <option value="1344x768">1344 × 768 Landscape 16:9</option>
                </select>
              </label>
              <div>
                <label>
                  Width
                  <input
                    type="number"
                    min="256"
                    max="2048"
                    step="16"
                    value={width}
                    onChange={(e) => setWidth(+e.target.value)}
                  />
                </label>
                <label>
                  Height
                  <input
                    type="number"
                    min="256"
                    max="2048"
                    step="16"
                    value={height}
                    onChange={(e) => setHeight(+e.target.value)}
                  />
                </label>
              </div>
              <label>
                Sampler
                <select
                  value={sampler}
                  onChange={(e) => setSampler(e.target.value)}
                >
                  <option value="res_multistep">Res Multistep (Z-Image)</option>
                  <option value="er_sde">ER-SDE (Krea-2)</option>
                  <option value="euler">Euler</option>
                  <option value="euler_ancestral">Euler a</option>
                  <option value="dpmpp_2m">DPM++ 2M</option>
                </select>
              </label>
            </div>
          </div>
          {error && <div className="error">{error}</div>}
          {isDarkBeast && (
            <div className="model-note">
              DarkBeast uses the Krea-2 workflow. Its 24.5 GB BF16 checkpoint may exceed a 12 GB GPU; use Krea-2 Turbo Q4 if generation runs out of VRAM.
            </div>
          )}
          {isMageFlow && (
            <div className="model-note">
              Mage-Flow Turbo INT8 is verified at 512 × 512 on this 12 GB GPU. It uses close to 11 GB VRAM, so keep 512px for dependable generation.
            </div>
          )}
          {isFlux2Klein && (
            <div className="model-note">
              FLUX.2 Klein Q4 GGUF is the verified compact FLUX workflow for this GPU: 4 steps, CFG 1, and a safe 512px starting size.
            </div>
          )}
          <div className="generate-row">
            <button className="preset">
              Preset: {isZImage ? "Z-Image Turbo · 4 steps" : "My Default"}
            </button>
            <button
              className="generate"
              disabled={!!job || engine !== "ready" || needsSpecialWorkflow}
              onClick={generate}
            >
              {job
                ? "Generating…"
                : needsSpecialWorkflow
                  ? `${current?.architecture} workflow required`
                  : engine === "ready"
                    ? isZImage
                      ? "Generate Z-Image"
                      : isMageFlow
                        ? "Generate Mage-Flow"
                        : isFlux2Klein
                          ? "Generate FLUX.2 Klein"
                          : isFlux
                            ? "Generate Flux"
                      : "Generate"
                    : "Engine starting…"}
            </button>
          </div>
        </section>
      </section>

      {toolMode && (
        <div className="modal face-modal" onClick={() => setToolMode("")}>
          <div
            className="drawer wide tool-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <h2>
                  {toolMode === "img2img"
                    ? "Image to Image"
                    : toolMode === "inpaint"
                      ? "Inpainting"
                      : "ControlNet"}
                </h2>
                <p>
                  {toolMode === "img2img"
                    ? "Transform an existing image while preserving its composition."
                    : toolMode === "inpaint"
                      ? "Replace only the white areas of a black-and-white mask."
                      : "Guide Z-Image with Canny edges, depth, or human pose."}
                </p>
              </div>
              <button onClick={() => setToolMode("")}>×</button>
            </header>
            <div className="tool-layout">
              <label className="tool-upload">
                <b>Source image</b>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) =>
                    loadFaceFile(e.target.files?.[0], setToolSource)
                  }
                />
                {toolSource ? (
                  <img src={toolSource} alt="Source image for editing" />
                ) : (
                  <span>Choose an image</span>
                )}
              </label>
              {toolMode === "inpaint" && (
                <label className="tool-upload">
                  <b>Mask image</b>
                  <small>White = replace, black = preserve</small>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={(e) =>
                      loadFaceFile(e.target.files?.[0], setToolMask)
                    }
                  />
                  {toolMask ? (
                    <img src={toolMask} alt="Inpainting mask" />
                  ) : (
                    <span>Choose a matching mask</span>
                  )}
                </label>
              )}
            </div>
            <label className="tool-prompt">
              Prompt
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
            </label>
            {toolMode === "controlnet" && (
              <label className="face-setting">
                Control type
                <select
                  value={controlMode}
                  onChange={(e) => setControlMode(e.target.value)}
                >
                  <option value="canny">Canny edges</option>
                  <option value="depth">Depth</option>
                  <option value="pose">Human pose</option>
                </select>
              </label>
            )}
            <label className="tool-range">
              {toolMode === "controlnet"
                ? "Control strength"
                : "Transformation strength"}{" "}
              <b>{toolStrength.toFixed(2)}</b>
              <input
                type="range"
                min="0.1"
                max="1"
                step=".05"
                value={toolStrength}
                onChange={(e) => setToolStrength(+e.target.value)}
              />
            </label>
            {error && <div className="error">{error}</div>}
            <button
              className="generate face-run"
              disabled={
                !toolSource ||
                !!toolJob ||
                (toolMode === "inpaint" && !toolMask)
              }
              onClick={runImageTool}
            >
              {toolJob
                ? `${toolState}…`
                : toolMode === "img2img"
                  ? "Transform Image"
                  : toolMode === "inpaint"
                    ? "Inpaint Image"
                    : "Run ControlNet"}
            </button>
            {toolResult && (
              <div className="face-result">
                <h3>Completed result</h3>
                <img src={toolResult} alt="Image editing result" />
                <a href={toolResult} download>
                  Open or save result
                </a>
              </div>
            )}
          </div>
        </div>
      )}

      <aside className="preview">
        <div className="preview-tabs">
          <button className={previewTab === "preview" ? "on" : ""} onClick={() => setPreviewTab("preview")}>Preview</button>
          <button className={previewTab === "history" ? "on" : ""} onClick={() => setPreviewTab("history")}>History <i>{generationHistory.length}</i></button>
          <button className={previewTab === "favorites" ? "on" : ""} onClick={() => setPreviewTab("favorites")}>Favorites <i>{generationHistory.filter((item) => item.favorite).length}</i></button>
        </div>
        {previewTab !== "preview" ? <div className="result-gallery">
          <header><div><b>{previewTab === "history" ? "Generation History" : "Favorite Images"}</b><small>{previewTab === "history" ? "Your latest 200 Froja generations" : "Images you marked for quick access"}</small></div></header>
          {(previewTab === "history" ? generationHistory : generationHistory.filter((item) => item.favorite)).length ? <div className="result-grid">{(previewTab === "history" ? generationHistory : generationHistory.filter((item) => item.favorite)).map((record) => <article key={record.id}><button className="result-image" onClick={() => openHistoryRecord(record)}><img src={record.image} alt={record.prompt || "Froja generation"} /></button><div><b>{record.style}</b><small>{new Date(record.created).toLocaleString()} · {record.width} × {record.height}</small><p>{record.prompt}</p><button className={record.favorite ? "favorite on" : "favorite"} onClick={() => toggleFavorite(record)} aria-label={record.favorite ? "Remove from favorites" : "Add to favorites"}>{record.favorite ? "★" : "☆"}</button></div></article>)}</div> : <div className="empty-results"><Icon name={previewTab === "favorites" ? "preset" : "image"} /><b>{previewTab === "favorites" ? "No favorites yet" : "No generated images yet"}</b><p>{previewTab === "favorites" ? "Open an image and select Add to Favorites." : "New images will be recorded automatically after generation."}</p></div>}
        </div> : <>
        <div className="preview-meta">
          <span>{style}</span>
          <small>
            {width} × {height}px
          </small>
        </div>
        <div className="image-frame">
          <img src={image} alt="Latest Froja generation" onDoubleClick={() => setPreviewZoomOpen(true)} />
          {job && (
            <div className="rendering">
              <i />
              <b>Generating image…</b>
              <small>{jobState}</small>
            </div>
          )}
        </div>
        <div className="preview-actions">
          <button onClick={() => { setPreviewZoom(100); setPreviewZoomOpen(true); }}><Icon name="enhance" /> Zoom</button>
          <button className={generationHistory.find((item) => item.image === image)?.favorite ? "favorite-active" : ""} onClick={() => toggleFavorite()}>{generationHistory.find((item) => item.image === image)?.favorite ? "★ Favorited" : "☆ Favorite"}</button>
          <button onClick={sendCurrentToEnhance}><Icon name="enhance" /> Enhance</button>
          <button onClick={openOutputFolder}><Icon name="library" /> Folder</button>
          {outputFolderState && <small>{outputFolderState}</small>}
        </div>
        <div className="thumbs">{generationHistory.slice(0, 6).map((record) => <img key={record.id} className={record.image === image ? "selected" : ""} src={record.image} alt={record.prompt || "Recent Froja generation"} onClick={() => openHistoryRecord(record)} />)}</div>
        <section className="info">
          <h3>
            Generation Info <button onClick={copyGenerationInfo}>Copy All</button>
          </h3>
          <div className="info-grid">
            <span>
              Model<b>{current?.name || "—"}</b>
            </span>
            <span>
              Seed<b>{seed < 0 ? "Random" : seed}</b>
            </span>
            <span>
              Steps<b>{steps}</b>
            </span>
            <span>
              Size
              <b>
                {width} × {height}
              </b>
            </span>
            <span>
              CFG Scale<b>{cfg}</b>
            </span>
            <span>
              Sampler<b>{sampler}</b>
            </span>
          </div>
          <hr />
          <h4>Prompt</h4>
          <p>{prompt}</p>
          <h4>Negative Prompt</h4>
          <p>{negative}</p>
        </section>
        </>}
      </aside>

      {relightOpen && (
        <div className="modal face-modal" onClick={() => setRelightOpen(false)}>
          <div
            className="drawer wide tool-drawer relight-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <h2>Froja Relight</h2>
                <p>Move the light around an existing image with IC-Light.</p>
              </div>
              <button onClick={() => setRelightOpen(false)}>×</button>
            </header>
            <div className="tool-layout">
              <label className="tool-upload">
                <b>Image to relight</b>
                <small>Portraits, objects and interiors work best</small>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) =>
                    loadFaceFile(e.target.files?.[0], setRelightSource)
                  }
                />
                {relightSource ? (
                  <img src={relightSource} alt="Original image for relighting" />
                ) : (
                  <span>Choose an image</span>
                )}
              </label>
              {relightResult && (
                <div className="tool-upload relight-after">
                  <b>Relighted result</b>
                  <img src={relightResult} alt="Relighted result" />
                </div>
              )}
            </div>
            <label className="tool-prompt">
              Lighting description
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Warm window light, cinematic shadows, soft rim light…"
              />
            </label>
            <section className="relight-control">
              <div className="relight-presets">
                {["top", "front", "right", "left", "back", "bottom"].map((direction) => (
                  <button
                    key={direction}
                    className={
                      direction === relightDirection ? "selected" : ""
                    }
                    onClick={() => setRelightPreset(direction)}
                  >
                    {direction[0].toUpperCase() + direction.slice(1)}
                  </button>
                ))}
              </div>
              <div
                className="relight-pad"
                onPointerDown={(event) => {
                  event.currentTarget.setPointerCapture(event.pointerId);
                  moveRelightPoint(event);
                }}
                onPointerMove={(event) => {
                  if (event.currentTarget.hasPointerCapture(event.pointerId)) moveRelightPoint(event);
                }}
              >
                <span>Hold and drag to change light direction</span>
                <i className="light-arrow top">⌃</i><i className="light-arrow right">›</i>
                <i className="light-arrow bottom">⌄</i><i className="light-arrow left">‹</i>
                <b
                  className="light-point"
                  style={{ left: `${relightX * 100}%`, top: `${relightY * 100}%`, background: relightColor }}
                />
              </div>
              <div className="relight-settings-title">Light settings</div>
              <div className="relight-toggle">
                <button className={relightQuality === "soft" ? "selected" : ""} onClick={() => setRelightQuality("soft")}>Soft</button>
                <button className={relightQuality === "hard" ? "selected" : ""} onClick={() => setRelightQuality("hard")}>Hard</button>
              </div>
              <label className="relight-setting-row">
                <span>Brightness</span>
                <input type="range" min="10" max="100" value={relightBrightness} onChange={(e) => setRelightBrightness(+e.target.value)} />
                <b>{relightBrightness}%</b>
              </label>
              <label className="relight-setting-row color">
                <span>Color</span>
                <input type="color" value={relightColor} onChange={(e) => setRelightColor(e.target.value)} />
                <b>{relightColor.toUpperCase()}</b>
              </label>
            </section>
            <label className="tool-range">
              Relighting strength <b>{relightStrength.toFixed(2)}</b>
              <input
                type="range"
                min="0.35"
                max="1"
                step=".05"
                value={relightStrength}
                onChange={(e) => setRelightStrength(+e.target.value)}
              />
            </label>
            <p className="face-note">
              IC-Light reconstructs illumination, so stronger settings can also
              change some fine details. Start around 0.70–0.80.
            </p>
            {error && <div className="error">{error}</div>}
            <button
              className="generate face-run"
              disabled={!relightSource || !!relightJob}
              onClick={runRelight}
            >
              {relightJob ? `Relighting: ${relightState}…` : "Relight Image"}
            </button>
            {relightResult && (
              <div className="face-result relight-result">
                <h3>Completed result</h3>
                <a href={relightResult} download>
                  Open or save result
                </a>
              </div>
            )}
          </div>
        </div>
      )}

      {cameraOpen && (
        <div className="modal face-modal" onClick={() => setCameraOpen(false)}>
          <div className="drawer wide tool-drawer camera-drawer" onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <h2>Froja Camera Lab</h2>
                <p>Choose a photographic look or prepare a JoyAI viewpoint edit.</p>
              </div>
              <button onClick={() => setCameraOpen(false)}>×</button>
            </header>
            <div className="camera-lab-heading">
              <div><b>Camera profiles</b><small>Selecting one automatically adds its camera language to text-to-image prompts.</small></div>
              <span>{cameraProfiles.length - 1} looks</span>
            </div>
            <div className="camera-profile-grid">
              {cameraProfiles.map((camera) => (
                <button
                  key={camera.id}
                  className={cameraProfile === camera.id ? "selected" : ""}
                  onClick={() => setCameraProfile(camera.id)}
                >
                  <span className={`camera-visual ${camera.icon}`}>
                    <i className="camera-body-shape" />
                    <i className="camera-lens-shape" />
                  </span>
                  <span className="camera-card-name"><small>{camera.format}</small><b>{camera.name}</b></span>
                  <span className="camera-card-specs">
                    <i><small>Lens</small><b>{camera.lens}</b></i>
                    <i><small>Focal</small><b>{camera.focal}</b></i>
                    <i><small>Aperture</small><b>{camera.aperture}</b></i>
                  </span>
                  <em>{camera.use}</em>
                </button>
              ))}
            </div>
            <section className="camera-move-panel">
              <div><b>Change the viewpoint of an existing image</b><small>These controls prepare an exact JoyAI camera instruction.</small></div>
              <div className="camera-move-grid">
                <label>Yaw <b>{cameraYaw}°</b><input type="range" min="-180" max="180" step="5" value={cameraYaw} onChange={(e) => setCameraYaw(+e.target.value)} /></label>
                <label>Pitch <b>{cameraPitch}°</b><input type="range" min="-60" max="60" step="5" value={cameraPitch} onChange={(e) => setCameraPitch(+e.target.value)} /></label>
                <label>Zoom<select value={cameraZoom} onChange={(e) => setCameraZoom(e.target.value)}><option value="unchanged">Unchanged</option><option value="in">Zoom in</option><option value="out">Zoom out</option></select></label>
              </div>
              <button className="generate camera-send" onClick={sendCameraMoveToJoyai}>Use Viewpoint in Smart Edit</button>
            </section>
            <button className="camera-done" onClick={() => setCameraOpen(false)}>Apply {currentCamera.name}</button>
          </div>
        </div>
      )}

      {joyaiOpen && (
        <div className="modal face-modal" onClick={() => setJoyaiOpen(false)}>
          <div
            className="drawer wide tool-drawer joyai-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <h2>Froja Smart Edit</h2>
                <p>Instruction-based structural editing powered by JoyAI.</p>
              </div>
              <button onClick={() => setJoyaiOpen(false)}>×</button>
            </header>
            <div className="joyai-warning">
              <b>Creative editor — not a surgical repair tool</b>
              <span>
                JoyAI can correct posture, move or rotate objects, and change the
                camera, but it may also recompose the scene. Use Repair Studio or
                Inpainting when the surrounding image must remain exact.
              </span>
            </div>
            <div className="tool-layout">
              <label className="tool-upload">
                <b>Image to edit</b>
                <small>JoyAI produces a new 1024 × 1024 interpretation</small>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) =>
                    loadFaceFile(e.target.files?.[0], setJoyaiSource)
                  }
                />
                {joyaiSource ? (
                  <img src={joyaiSource} alt="Source image for Smart Edit" />
                ) : (
                  <span>Choose an image</span>
                )}
              </label>
              {joyaiResult && (
                <div className="tool-upload">
                  <b>Smart Edit result</b>
                  <img src={joyaiResult} alt="Smart Edit result" />
                </div>
              )}
            </div>
            <section className="joyai-suggestions">
              <div>
                <b>What do you want to change?</b>
                <small>
                  Choose a starting instruction, then replace anything inside
                  [brackets] with your own details.
                </small>
              </div>
              <div className="joyai-suggestion-grid">
                {joyaiSuggestions.map((suggestion) => (
                  <button
                    key={suggestion.label}
                    type="button"
                    className={
                      joyaiInstruction === suggestion.prompt ? "selected" : ""
                    }
                    onClick={() => setJoyaiInstruction(suggestion.prompt)}
                  >
                    {suggestion.label}
                  </button>
                ))}
              </div>
            </section>
            <label className="tool-prompt">
              Editing instruction
              <textarea
                value={joyaiInstruction}
                onChange={(e) => setJoyaiInstruction(e.target.value)}
                placeholder="Correct the hands and posture while preserving the person's identity, clothing and lighting…"
              />
            </label>
            <label className="tool-range">
              Quality steps <b>{joyaiSteps}</b>
              <input
                type="range"
                min="8"
                max="30"
                step="2"
                value={joyaiSteps}
                onChange={(e) => setJoyaiSteps(+e.target.value)}
              />
            </label>
            <p className="face-note">
              Tested on this RTX 4070 Ti: 20 steps took approximately 11 minutes
              and used nearly all available VRAM and RAM. Do not run another
              large model at the same time.
            </p>
            {error && <div className="error">{error}</div>}
            <button
              className="generate face-run"
              disabled={!joyaiSource || !joyaiInstruction.trim() || !!joyaiJob}
              onClick={runJoyaiEdit}
            >
              {joyaiJob ? `Smart Editing: ${joyaiState}…` : "Run JoyAI Smart Edit"}
            </button>
            {joyaiResult && (
              <div className="face-result">
                <h3>Completed Smart Edit</h3>
                <a href={joyaiResult} download>
                  Open or save result
                </a>
              </div>
            )}
          </div>
        </div>
      )}

      {navPanel && (
        <div className="modal navigation-modal" onClick={() => setNavPanel("")}>
          <div className="drawer navigation-drawer" onClick={(event) => event.stopPropagation()}>
            <header><div><h2>{navPanel[0].toUpperCase() + navPanel.slice(1)}</h2><p>Froja workspace and application controls.</p></div><button onClick={() => setNavPanel("")}>×</button></header>
            {navPanel === "home" && <div className="nav-workspace"><div className="nav-stats"><article><b>{counts.checkpoints}</b><small>Checkpoints</small></article><article><b>{counts.loras}</b><small>LoRAs</small></article><article><b>{counts.embeddings || 0}</b><small>Embeddings</small></article><article><b>{engine}</b><small>Image engine</small></article></div><h3>Quick start</h3><button onClick={() => setNavPanel("")}>Create a new image</button><button onClick={() => { setNavPanel(""); setImagePromptOpen(true); }}>Recognize an image and create a prompt</button><button onClick={() => { setNavPanel(""); setEnhanceOpen(true); }}>Enhance an existing image</button></div>}
            {navPanel === "library" && <div className="nav-workspace"><p>Your files remain in their existing folders; Froja only indexes them.</p><button onClick={() => { setNavPanel(""); setModelQuery(""); setModelOpen(true); }}>Checkpoints <b>{counts.checkpoints}</b></button><button onClick={() => { setNavPanel(""); setLoraQuery(""); setLoraOpen(true); }}>LoRA models <b>{counts.loras}</b></button><button onClick={() => setNavPanel("embeddings")}>Embeddings <b>{counts.embeddings || 0}</b></button><button onClick={refreshLibrary}>Refresh all linked folders</button></div>}
            {navPanel === "presets" && <div className="nav-workspace"><p>Save and restore your current prompt, model, style, sampler, dimensions, steps and CFG settings.</p><button onClick={saveCurrentPreset}>Save current settings as My Preset</button><button onClick={loadCurrentPreset}>Load My Preset</button><button onClick={() => { setSteps(28); setCfg(7); setWidth(768); setHeight(768); setSampler("euler"); setMaintenanceState("Balanced defaults applied."); }}>Apply balanced defaults</button></div>}
            {navPanel === "workflows" && <div className="workflow-grid"><button onClick={() => { setNavPanel(""); setImagePromptOpen(true); }}><b>Image → Prompt</b><small>Understand an image and produce a generation prompt.</small></button><button onClick={() => { setNavPanel(""); openImageTool("img2img"); }}><b>Image → Image</b><small>Recreate or transform an existing image.</small></button><button onClick={() => { setNavPanel(""); openImageTool("inpaint"); }}><b>Inpainting</b><small>Repair a selected area.</small></button><button onClick={() => { setNavPanel(""); setRelightOpen(true); }}><b>IC-Light Relight</b><small>Change the direction and character of light.</small></button><button onClick={() => { setNavPanel(""); setRepairOpen(true); }}><b>Repair Studio</b><small>Correct faces, eyes, hands and local defects.</small></button><button onClick={() => { setNavPanel(""); setJoyaiOpen(true); }}><b>Smart Edit</b><small>Edit an image using natural-language instructions.</small></button></div>}
            {navPanel === "embeddings" && <><input className="nav-search" placeholder="Search embeddings…" value={embeddingSearch} onChange={(event) => setEmbeddingSearch(event.target.value)} /><div className="embedding-list">{embeddings.filter((item) => item.name.toLowerCase().includes(embeddingSearch.toLowerCase())).map((item) => <article key={item.path}><div><b>{item.name}</b><small>{item.source} · {(item.size / 1024 / 1024).toFixed(1)} MB</small></div><button onClick={() => { setNegative((value) => [value, `embedding:${item.name.replace(/\.[^.]+$/, "")}`].filter(Boolean).join(", ")); setMaintenanceState(`${item.name} added to the negative prompt.`); }}>Add to negative prompt</button></article>)}</div></>}
            {navPanel === "settings" && <div className="nav-workspace">
              <h3 className="settings-section-title"><Icon name="palette" /> {t("appearance")}</h3>
              <div className="theme-grid">
                {[['forge','Forge Dark','Teal · professional'],['midnight','Midnight Blue','Blue · calm'],['bronze','Warm Bronze','Copper · artistic'],['contrast','High Contrast','Clear · accessible']].map(([id,name,note]) => <button className={uiTheme === id ? 'selected' : ''} onClick={() => setUiTheme(id)} key={id}><i /><b>{name}</b><small>{note}</small></button>)}
              </div>
              <div className="icon-style-options"><button className={iconStyle === "outline" ? "selected" : ""} onClick={() => setIconStyle("outline")}><span className="icon-demo outline-demo"><Icon name="settings" /></span><b>Professional Outline</b><small>Clean, minimal and compact</small></button><button className={iconStyle === "soft3d" ? "selected" : ""} onClick={() => setIconStyle("soft3d")}><span className="icon-demo soft3d-demo"><Icon name="settings" /></span><b>Soft 3D</b><small>Windows-style depth and recognition</small></button></div>
              <div className="accessibility-options"><label>{t("language")}<select value={uiLanguage} onChange={(event) => setUiLanguage(event.target.value)}><option value="en">English</option><option value="pt">Português</option><option value="it">Italiano</option><option value="es">Español</option><option value="fr">Français</option><option value="de">Deutsch</option></select></label><label>{t("typeface")}<select value={fontFamily} onChange={(event) => setFontFamily(event.target.value)}><option value="modern">Modern Sans</option><option value="humanist">Humanist</option><option value="classic">Classic Serif</option><option value="mono">Technical Mono</option></select></label></div>
              <label className="font-scale-control">{t("textSize")} <b>{textScale}%</b><input aria-label={t("textSize")} type="range" min="90" max="160" step="5" value={textScale} onChange={(event) => setTextScale(+event.target.value)} /><small>Make writing larger or smaller without changing panel dimensions.</small></label>
              <label className="font-scale-control">{t("displaySize")} <b>{fontScale}%</b><input aria-label={t("displaySize")} type="range" min="90" max="140" step="5" value={fontScale} onChange={(event) => setFontScale(+event.target.value)} /><small>Make the complete interface larger or smaller.</small></label>
              <label className="switch-control"><span><b>{t("bold")}</b><small>Increase the weight of interface labels.</small></span><input type="checkbox" checked={boldText} onChange={(event) => setBoldText(event.target.checked)} /></label>
              <div className="built-in-backgrounds"><b>Built-in Froja themes</b><small>Each choice applies its background, accent colours, panel tint and glow.</small><div>{[["/themes/cosmic-quiet.png","Cosmic Quiet","midnight"],["/themes/bronze-forge.png","Bronze Forge","bronze"],["/themes/teal-studio.png","Teal Studio","forge"]].map(([src,name,theme]) => <button className={customBackground === src ? "selected" : ""} key={src} onClick={() => { setCustomBackground(src); setUiTheme(theme); setPendingBackground(""); setThemeFileName(""); setMaintenanceState(`${name} theme applied.`); }}><img src={src} alt={`${name} Froja background`} /><span>{name}</span><small>{theme === "bronze" ? "Copper accents" : theme === "midnight" ? "Blue accents" : "Teal accents"}</small></button>)}</div></div>
              <div className="background-control">
                <b>Theme background image</b><small>PNG, JPEG or WebP · up to 20 MB · resized automatically</small>
                <label className="theme-dropzone" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); loadThemeBackground(event.dataTransfer.files?.[0]); }}><Icon name="image" /><span>{themeUploadState}</span>{themeFileName && <small>{themeFileName}</small>}<strong>Choose Image</strong><input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => loadThemeBackground(event.target.files?.[0])} /></label>
                {(pendingBackground || customBackground) && <img src={pendingBackground || customBackground} alt="Custom Froja theme background preview" />}
                <div className="background-actions">{pendingBackground && <button className="apply-background" onClick={() => { setCustomBackground(pendingBackground); setPendingBackground(""); setMaintenanceState("Custom background applied and saved."); }}>Apply Background</button>}{(pendingBackground || customBackground) && <button onClick={() => { setPendingBackground(""); setCustomBackground(""); setThemeFileName(""); setThemeUploadState("Choose or drop an image"); setMaintenanceState("Custom background removed."); }}>Remove</button>}</div>
              </div>
              <h3 className="settings-section-title"><Icon name="library" /> Library</h3><button onClick={refreshLibrary}>Refresh models, LoRAs and embeddings</button>
              <h3 className="settings-section-title"><Icon name="preset" /> Backup</h3><button onClick={downloadSettingsBackup}>Download Froja settings backup</button><small>Backups contain settings and presets only. Checkpoints and LoRAs are never copied.</small>
              <h3 className="settings-section-title"><Icon name="settings" /> Updates</h3><div className="settings-note"><b>Safe update channel</b><p>Automatic replacement is currently disabled until Froja has versioned releases and one-click rollback. This prevents an update from breaking your working installation.</p></div>
            </div>}
            {maintenanceState && <div className="maintenance-state">{maintenanceState}</div>}
          </div>
        </div>
      )}

      {previewZoomOpen && (
        <div className="modal generated-zoom-modal" onClick={() => setPreviewZoomOpen(false)}>
          <div className="generated-zoom-dialog" onClick={(event) => event.stopPropagation()}>
            <header>
              <div><h2>Generated Image Detail</h2><p>Zoom and scroll to inspect the finished image.</p></div>
              <button onClick={() => setPreviewZoomOpen(false)}>×</button>
            </header>
            <div className="generated-zoom-toolbar">
              <button onClick={() => setPreviewZoom(100)}>Fit</button>
              <button onClick={() => setPreviewZoom(150)}>150%</button>
              <button onClick={() => setPreviewZoom(200)}>200%</button>
              <input aria-label="Generated image zoom" type="range" min="50" max="400" step="10" value={previewZoom} onChange={(event) => setPreviewZoom(+event.target.value)} />
              <strong>{previewZoom}%</strong>
              <button onClick={openOutputFolder}>▣ Open Folder</button>
            </div>
            <div className="generated-zoom-canvas">
              <img style={{ width: `${previewZoom}%` }} src={image} alt="Generated image enlarged for detail inspection" />
            </div>
          </div>
        </div>
      )}

      {enhanceOpen && (
        <div className="modal face-modal" onClick={() => setEnhanceOpen(false)}>
          <div className="drawer wide tool-drawer enhance-drawer" onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <h2>Enhance Image</h2>
                <p>Sharpen, clean, rebalance and upscale an existing image without changing its composition.</p>
              </div>
              <button onClick={() => setEnhanceOpen(false)}>×</button>
            </header>
            <div className="enhance-presets">
              <button onClick={() => applyEnhancePreset("gentle")}><b>Gentle Sharp</b><small>Natural everyday improvement</small></button>
              <button onClick={() => applyEnhancePreset("photo")}><b>Photo Detail</b><small>Stronger clarity and colour</small></button>
              <button onClick={() => applyEnhancePreset("restore")}><b>Old Photo Clean</b><small>Noise, dust and scratch reduction</small></button>
            </div>
            <div className="enhance-layout">
              <label className="tool-upload enhance-preview">
                <b>Original image</b>
                <small>PNG, JPEG or WebP · maximum 25 MB</small>
                <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => {
                  setEnhanceResult(""); setEnhanceState("Ready"); setEnhanceSize("");
                  loadFaceFile(e.target.files?.[0], setEnhanceSource);
                }} />
                {enhanceSource ? <div className="enhance-viewport"><img style={{ width: `${enhanceZoom}%` }} src={enhanceSource} alt="Original image selected for enhancement" /></div> : <span>Choose or drop an image here</span>}
              </label>
              <div className="tool-upload enhance-preview">
                <b>Enhanced result</b>
                <small>{enhanceSize || "Your processed image will appear here"}</small>
                {enhanceResult ? <div className="enhance-viewport"><img style={{ width: `${enhanceZoom}%` }} src={enhanceResult} alt="Enhanced image result" /></div> : <span>{enhanceState}</span>}
              </div>
            </div>
            <div className="enhance-zoom" aria-label="Before and after zoom controls">
              <b>Compare zoom</b>
              <button onClick={() => setEnhanceZoom(100)}>Fit</button>
              <button onClick={() => setEnhanceZoom(150)}>150%</button>
              <button onClick={() => setEnhanceZoom(200)}>200%</button>
              <input aria-label="Comparison zoom" type="range" min="50" max="300" step="10" value={enhanceZoom} onChange={(e) => setEnhanceZoom(+e.target.value)} />
              <strong>{enhanceZoom}%</strong>
              <small>Both previews use the same zoom. Scroll inside either image to inspect fine detail.</small>
            </div>
            <div className="enhance-controls">
              <label>Sharpen <b>{enhanceSharpen}%</b><input type="range" min="0" max="100" value={enhanceSharpen} onChange={(e) => setEnhanceSharpen(+e.target.value)} /></label>
              <label>Denoise <b>{enhanceDenoise}%</b><input type="range" min="0" max="100" value={enhanceDenoise} onChange={(e) => setEnhanceDenoise(+e.target.value)} /></label>
              <label>Dust & scratches <b>{enhanceDust}%</b><input type="range" min="0" max="100" value={enhanceDust} onChange={(e) => setEnhanceDust(+e.target.value)} /></label>
              <label>Brightness <b>{enhanceBrightness}</b><input type="range" min="-50" max="50" value={enhanceBrightness} onChange={(e) => setEnhanceBrightness(+e.target.value)} /></label>
              <label>Contrast <b>{enhanceContrast}</b><input type="range" min="-50" max="50" value={enhanceContrast} onChange={(e) => setEnhanceContrast(+e.target.value)} /></label>
              <label>Colour <b>{enhanceColor}</b><input type="range" min="-50" max="50" value={enhanceColor} onChange={(e) => setEnhanceColor(+e.target.value)} /></label>
              <label>Upscale<select value={enhanceScale} onChange={(e) => setEnhanceScale(+e.target.value)}><option value={1}>Original size</option><option value={2}>2×</option><option value={4}>4× (smart limit)</option></select></label>
            </div>
            <div className="image-prompt-actions">
              {enhanceResult && <a className="enhance-download" href={enhanceResult} download={enhanceDownloadName}>Save Enhanced Image</a>}
              <button className="primary" disabled={!enhanceSource || enhanceState === "Enhancing image"} onClick={runEnhancement}>
                {enhanceState === "Enhancing image" ? "Enhancing…" : "Apply Enhancements"}
              </button>
            </div>
          </div>
        </div>
      )}

      {imagePromptOpen && (
        <div className="modal face-modal" onClick={() => setImagePromptOpen(false)}>
          <div
            className="drawer wide tool-drawer image-prompt-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <h2>Image to Prompt</h2>
                <p>Upload a reference image and Froja will turn everything visible into a reusable generation prompt.</p>
              </div>
              <button onClick={() => setImagePromptOpen(false)}>×</button>
            </header>
            <div className="image-prompt-layout">
              <label className="tool-upload image-prompt-upload">
                <b>Reference image</b>
                <small>PNG, JPEG or WebP · maximum 20 MB</small>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => {
                    setImagePromptResult("");
                    setImagePromptState("Ready");
                    loadFaceFile(e.target.files?.[0], setImagePromptSource);
                  }}
                />
                {imagePromptSource ? <img src={imagePromptSource} alt="Reference selected for prompt recognition" /> : <span>Choose or drop an image here</span>}
              </label>
              <div className="image-prompt-controls">
                <label>
                  Description detail
                  <select value={imagePromptDetail} onChange={(e) => setImagePromptDetail(e.target.value)}>
                    <option value="concise">Concise</option>
                    <option value="balanced">Balanced</option>
                    <option value="detailed">Highly detailed</option>
                  </select>
                </label>
                <div className="vision-status">
                  <b>Local vision model</b>
                  <small>Llama Vision recognizes it, then Qwen rewrites the result as a generation prompt · your image stays local</small>
                  <em>{imagePromptState}</em>
                </div>
                <button
                  className="tool-run"
                  disabled={!imagePromptSource || imagePromptState === "Analyzing image"}
                  onClick={analyzeImagePrompt}
                >
                  {imagePromptState === "Analyzing image" ? "Recognizing image…" : "Recognize and Create Prompt"}
                </button>
              </div>
            </div>
            <label className="tool-prompt image-prompt-result">
              Generated prompt
              <textarea
                value={imagePromptResult}
                onChange={(e) => setImagePromptResult(e.target.value)}
                placeholder="The image description will appear here. You can edit it before using it."
              />
            </label>
            <div className="image-prompt-actions">
              <button disabled={!imagePromptResult} onClick={() => navigator.clipboard.writeText(imagePromptResult)}>Copy Prompt</button>
              <button className="primary" disabled={!imagePromptResult} onClick={useImagePrompt}>Use in Text to Image</button>
            </div>
          </div>
        </div>
      )}

      {trainingStudioOpen && (
        <div className="modal training-modal" onClick={()=>setTrainingStudioOpen(false)}>
          <div className="training-workspace with-appearance" onClick={event=>event.stopPropagation()}>
            <header className="training-head"><div><h2>✦ Froja Training Studio</h2><p>Generate eight consistent images in different positions, angles and environments for professional LoRA training.</p></div><span><button onClick={()=>{setTrainingResults([]);setTrainingQueue([]);setTrainingShots(trainingShotOptions[trainingType].map(([name])=>name));setTrainingEnvironments(["Studio"]);setTrainingImagesPerSetup(1);setTrainingSession(`Froja_Training_${Date.now().toString().slice(-5)}`);setTrainingState("New eight-image session ready.");}}>＋ New Session</button><button className="appearance-toggle" onClick={()=>setAppearanceOpen(value=>!value)}>◉ Appearance Extension</button><button className="prompt-cards-toggle" onClick={()=>setPromptCardsOpen(value=>!value)}>▦ Prompt Cards</button><button onClick={()=>setTrainingStudioOpen(false)}>×</button></span></header>
            <aside className="appearance-extension appearance-library">
              <header><h3>Appearance Library</h3></header>

              <nav className="appearance-tabs">{["Materials","Body","Hair","Hands","Landscapes","Fabric"].map(category=><button key={category} className={appearanceCategory===category?"selected":""} onClick={()=>setAppearanceCategory(category)}><i>{appearanceLibrary[category].icon}</i><span>{appearanceLibrary[category].label}</span></button>)}</nav>
              {appearanceCategory==="Materials"&&<div className="material-library-tools"><span><b>My Material Folder</b><small>{materialLibraryState}</small></span><button onClick={async()=>{await fetch("/api/materials/open-folder",{method:"POST"});setMaterialLibraryState("Folder opened — add PNG, JPG or WebP files, then rescan.");}}>Open Folder</button><button onClick={loadMaterialLibrary}>Rescan</button>{materialFolder&&<em title={materialFolder}>{materialFolder}</em>}</div>}
              <div className={`appearance-cards category-${appearanceCategory.toLowerCase()}`}>{currentAppearancePresets.filter(preset=>preset.name.toLowerCase().includes(appearanceSearch.toLowerCase())).map(preset=><button key={preset.name} className={appearanceSelections[appearanceCategory]===preset.name?"selected":""} onClick={()=>setAppearanceSelections(items=>{const next={...items};if(next[appearanceCategory]===preset.name)delete next[appearanceCategory];else next[appearanceCategory]=preset.name;return next;})}><i style={{background:preset.preview}}/><b>{preset.name}</b>{appearanceSelections[appearanceCategory]===preset.name&&<em>✓</em>}</button>)}</div>
              {(()=>{const selected=currentAppearancePresets.find(preset=>preset.name===(appearanceSelections[appearanceCategory]||currentAppearancePresets[0]?.name))||currentAppearancePresets[0];return <>
                <section className={`appearance-preview-grid category-${appearanceCategory.toLowerCase()}`}><div className="appearance-live"><b>Live Preview</b><small>{selected.name}</small><i className={`swatch-preview swatch-${appearanceCategory.toLowerCase()}-${currentAppearancePresets.indexOf(selected)+1}`} style={{background:selected.preview}}/></div><div className="appearance-harmony"><header><b>Colour Harmony</b><select value={appearanceHarmony} onChange={event=>setAppearanceHarmony(event.target.value)}><option>Cool Analogous</option><option>Analogous</option><option>Complementary</option><option>Triadic</option><option>Monochrome</option><option>Warm</option><option>Cool</option></select></header><div className="color-wheel"><input aria-label="Appearance colour" type="color" value={appearanceColor} onChange={event=>setAppearanceColor(event.target.value)}/></div><div className="palette-rows"><span>Primary<i style={{background:appearanceColor}}/><i/><i/></span><span>Secondary<i/><i/><i/></span><span>Accent<i/><i/><i/></span></div></div></section>
                <section className="appearance-sliders">{appearanceLibrary[appearanceCategory].controls.map((control,index)=>{const value=index===0?appearanceRoughness:index===1?appearanceWeathering:Math.max(15,78-index*9);return <label key={control}>{control}<b>{(value/100).toFixed(2)}</b><input type="range" min="0" max="100" value={value} onChange={event=>{if(index===0)setAppearanceRoughness(+event.target.value);if(index===1)setAppearanceWeathering(+event.target.value);}}/></label>})}</section>
                <label className="appearance-target"><span>Apply selection to</span><select value={appearanceTarget} onChange={event=>setAppearanceTarget(event.target.value)}><option>Main object / subject</option><option>Background / environment</option><option>Clothing / accessories</option><option>Complete image</option></select></label><section className="appearance-finish"><b>Style Finish</b><div><button className="selected">Natural</button><button>Balanced</button><button>Styled</button><button>Weathered</button></div></section>
              </>})()}
              <label className="appearance-lock"><span><b>Consistency Lock</b><small>Lock selected appearance across all eight outputs</small></span><input type="checkbox" checked={appearanceConsistency} onChange={event=>setAppearanceConsistency(event.target.checked)}/></label>
              <button className="appearance-apply" onClick={()=>setTrainingState(`Appearance Library applied to all ${trainingShots.length*trainingEnvironments.length*trainingImagesPerSetup} planned images.`)}>Apply appearance to all 8</button>
              <footer>{Object.entries(appearanceSelections).map(([category,value])=><span key={category}>{category}: {value}</span>)}</footer>
            </aside>            {promptCardsOpen&&<aside className="prompt-cards-studio">
              <header><div><h3>Prompt Cards & Wildcards Studio</h3><p>Build controlled combinations manually or create a randomized variation.</p></div><button onClick={()=>setPromptCardsOpen(false)}>×</button></header>
              <div className="prompt-card-actions"><button onClick={randomizePromptCards}>✦ Randomize Combination</button><button onClick={()=>setPromptCardSelections({})}>Clear Cards</button></div>
              <div className="prompt-card-groups">{Object.entries(promptCardLibrary).map(([category,group])=><section key={category}><h4>{group.label}</h4><div>{group.options.map(card=><button key={card.name} className={promptCardSelections[category]===card.name?"selected":""} onClick={()=>setPromptCardSelections(items=>{const next={...items};if(next[category]===card.name)delete next[category];else next[category]=card.name;return next;})}><b>{card.name}</b><small>{card.prompt}</small></button>)}</div></section>)}</div>
              <section className="custom-prompt-cards"><h4>My Custom Cards</h4><p className="custom-card-help">Save a reusable prompt fragment. Adding it selects it immediately; click a saved card to turn it on or off.</p><div><input value={customPromptCard} onChange={event=>setCustomPromptCard(event.target.value)} onKeyDown={event=>{if(event.key==="Enter"){event.preventDefault();addCustomPromptCard();}}} placeholder="Example: aged brass corners, realistic worn edges"/><button disabled={!customPromptCard.trim()} onClick={addCustomPromptCard}>Add & Select</button></div><nav>{!customPromptCards.length&&<small>No custom cards saved yet.</small>}{customPromptCards.map(card=><button key={card} aria-pressed={promptCardSelections.Custom===card} className={promptCardSelections.Custom===card?"selected":""} onClick={()=>setPromptCardSelections(items=>{const next={...items};if(next.Custom===card)delete next.Custom;else next.Custom=card;return next;})}><b>{promptCardSelections.Custom===card?"✓ ":""}{card}</b><i title="Delete custom card" onClick={event=>{event.stopPropagation();setCustomPromptCards(items=>items.filter(item=>item!==card));setPromptCardSelections(items=>items.Custom===card?Object.fromEntries(Object.entries(items).filter(([key])=>key!=="Custom")):items);}}>×</i></button>)}</nav></section>
              <label className="prompt-card-lock"><span><b>Consistency Lock</b><small>Use this card combination across all eight training images</small></span><input type="checkbox" checked={promptCardConsistency} onChange={event=>setPromptCardConsistency(event.target.checked)}/></label>
              <div className="prompt-card-preview"><b>Combined wildcard prompt</b><p>{Object.entries(promptCardSelections).map(([category,value])=>promptCardLibrary[category]?.options.find(item=>item.name===value)?.prompt||value).join(", ")||"Choose cards or use Randomize Combination."}</p></div>
              <button className="prompt-card-apply" disabled={!Object.keys(promptCardSelections).length} onClick={()=>{setTrainingState(Object.keys(promptCardSelections).length+" Prompt Card selection"+(Object.keys(promptCardSelections).length===1?"":"s")+" applied to "+(trainingShots.length*trainingEnvironments.length*trainingImagesPerSetup)+" planned images.");setPromptCardsOpen(false);}}>Apply Selected Cards to Training Set</button>
            </aside>}            <div className="training-setup">
              <label>What are you training?<div className="training-types">{Object.keys(trainingShotOptions).map(type=><button key={type} className={trainingType===type?"selected":""} onClick={()=>{setTrainingType(type);setTrainingShots(trainingShotOptions[type].map(([name])=>name));setTrainingEnvironments(["Studio"]);setTrainingImagesPerSetup(1);}}>{type}</button>)}</div></label>
              <label>Core subject, place, object, or visual style<textarea value={trainingConcept} onChange={event=>setTrainingConcept(event.target.value)} placeholder="Describe exactly what must stay consistent across the complete training set…" /></label>
              <div className="training-model"><span>Active checkpoint <b>{current?.name||"Not selected"}</b></span><span>Active LoRAs <b>{selectedLoras.length}</b></span><span>Output <b>{width} × {height}</b></span><span>Steps <b>{steps}</b></span></div>
            </div>
            <section className="training-shots"><header><div><h3>Eight-picture variation plan</h3><p>Select eight complementary views. Froja runs them one at a time for 12 GB GPU safety.</p></div><span><button onClick={()=>setTrainingShots(trainingShotOptions[trainingType].map(([name])=>name))}>Select all 8</button><button onClick={()=>setTrainingShots([])}>Clear</button></span></header><div>{trainingShotOptions[trainingType].map(([name,guide])=><button key={name} className={trainingShots.includes(name)?"selected":""} onClick={()=>setTrainingShots(items=>items.includes(name)?items.filter(item=>item!==name):[...items,name])}><i>{trainingShots.includes(name)?"✓":""}</i><b>{name}</b><small>{guide}</small></button>)}</div></section>
            <section className="training-environment-panel"><div><b>Environments</b><div>{["Studio","Outdoor","Landscape","City","Sci-Fi","Fantasy","Indoor","Custom"].map(name=><button key={name} className={trainingEnvironments.includes(name)?"selected":""} onClick={()=>setTrainingEnvironments(items=>items.includes(name)?items.filter(item=>item!==name):[...items,name])}>{name}</button>)}</div></div><div><b>Output Settings</b><label>Images per setup<select value={trainingImagesPerSetup} onChange={event=>setTrainingImagesPerSetup(+event.target.value)}><option value={1}>1</option><option value={2}>2</option></select></label><label>Image size<select value={`${width}x${height}`} onChange={event=>{const [w,h]=event.target.value.split("x").map(Number);setWidth(w);setHeight(h);}}><option value="512x512">512 × 512</option><option value="768x768">768 × 768</option><option value="1024x1024">1024 × 1024</option><option value="768x1024">768 × 1024 Portrait</option><option value="1024x768">1024 × 768 Landscape</option></select></label></div></section>
                        <section className="quality-guide"><b>Approve only strong training images</b><span>☑ Same identity/design</span><span>☑ Clear subject</span><span>☑ Different composition</span><span>☑ Correct anatomy/geometry</span><span>☑ No text or watermark</span><span>☑ No major artifacts</span></section>
            <div className="training-selected-options"><small>Selected options</small>{Object.entries(appearanceSelections).map(([category,value])=><span key={category}>{category}: {value}</span>)}{Object.entries(promptCardSelections).map(([category,value])=><span key={"card-"+category}>Card · {category}: {value}</span>)}<span>Palette: {appearanceHarmony}</span></div><div className="training-run"><span><b>{trainingState}</b><small>{trainingResults.length} completed · {trainingQueue.length} remaining</small></span>{trainingQueue.length||trainingJob?<button onClick={()=>{setTrainingQueue([]);setTrainingState("Stopping after the current image.");}}>Stop after current</button>:<button className="primary" onClick={startTrainingSet}>Generate Selected Set</button>}</div>
            <div className="training-gallery-tools"><b>Gallery</b><label>Group by<select value={trainingGalleryGroup} onChange={event=>setTrainingGalleryGroup(event.target.value)}><option>Setup</option><option>Position</option><option>Environment</option></select></label><button onClick={()=>setTrainingResults(items=>items.map(item=>({...item,approved:true})))}>Select All</button></div><div className="training-results">{!trainingResults.length&&<div className="training-empty"><Icon name="create"/><b>No variations generated yet</b><span>Select a plan and generate a controlled training set.</span></div>}{trainingResults.map(item=><article key={item.id} className={item.approved?"approved":""}><button className="training-image-inspect" title="Open image inspector" onClick={()=>{setTrainingInspectId(item.id);setTrainingInspectZoom(1);}}><img src={item.image} alt={`${item.name} training variation`}/><span>⌕ Inspect & Zoom</span></button><div><b>{item.name}</b><small>{item.approved?"Approved for dataset":"Review before approval"}</small><button onClick={()=>setTrainingResults(items=>items.map(result=>result.id===item.id?{...result,approved:!result.approved}:result))}>{item.approved?"Remove Approval":"Approve Image"}</button><button onClick={()=>setTrainingResults(items=>items.filter(result=>result.id!==item.id))}>Reject</button></div></article>)}</div>
            <footer className="training-footer"><span><b>{trainingResults.filter(item=>item.approved).length}</b> approved of {trainingResults.length}</span><button onClick={sendApprovedTrainingImages} disabled={!trainingResults.some(item=>item.approved)}>Send Approved Images to LoRA Dataset Studio</button><button className="primary" disabled={!trainingResults.some(item=>item.approved)} onClick={()=>{sendApprovedTrainingImages();setTrainingStudioOpen(false);setDatasetOpen(true);}}>Open Dataset Studio</button></footer>
          </div>
        </div>
      )}
      {trainingInspectItem&&<div className="training-inspector-modal" onClick={()=>setTrainingInspectId("")}><section className="training-inspector" onClick={event=>event.stopPropagation()}><header><div><h2>{trainingInspectItem.name}</h2><p>{trainingInspectIndex+1} of {trainingResults.length} · {trainingInspectItem.position} · {trainingInspectItem.environment}</p></div><button aria-label="Close image inspector" onClick={()=>setTrainingInspectId("")}>×</button></header><div className="training-inspector-toolbar"><button onClick={()=>setTrainingInspectZoom(value=>Math.max(.25,value-.25))}>−</button><b>{Math.round(trainingInspectZoom*100)}%</b><button onClick={()=>setTrainingInspectZoom(value=>Math.min(4,value+.25))}>＋</button><button onClick={()=>setTrainingInspectZoom(1)}>Fit 100%</button><small>Mouse wheel zoom · scroll to examine details · arrow keys change image</small></div><div className="training-inspector-stage" onWheel={event=>{event.preventDefault();setTrainingInspectZoom(value=>Math.max(.25,Math.min(4,value+(event.deltaY<0?.15:-.15))))}}><img src={trainingInspectItem.image} alt={trainingInspectItem.name+" full quality inspection"} style={{width:(trainingInspectZoom*90)+"%",maxWidth:"none",maxHeight:"none"}}/></div><footer><button onClick={()=>stepTrainingInspection(-1)}>← Previous</button><div><b>{trainingInspectItem.approved?"Approved for dataset":"Awaiting quality review"}</b><p>{trainingInspectItem.prompt}</p></div><button onClick={()=>setTrainingResults(items=>items.map(item=>item.id===trainingInspectItem.id?{...item,approved:!item.approved}:item))}>{trainingInspectItem.approved?"Remove Approval":"Approve Image"}</button><button onClick={()=>stepTrainingInspection(1)}>Next →</button></footer></section></div>}
      {datasetOpen && (
        <div className="modal face-modal" onClick={() => setDatasetOpen(false)}>
          <div className="drawer wide tool-drawer dataset-drawer" onClick={(event) => event.stopPropagation()}>
            <header><div><h2>LoRA Dataset Studio</h2><p>Build a clean, captioned training set from your own images. Nothing is added automatically and originals stay untouched.</p></div><button onClick={() => setDatasetOpen(false)}>×</button></header>
            <div className="dataset-toolbar">
              <button className="primary" onClick={addCurrentToDataset}>Add Current Froja Image</button>
              <label className="dataset-upload">Upload Images<input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={(event) => addDatasetFiles(event.target.files)} /></label>
              <label>Trigger word<input value={datasetTrigger} onChange={(event) => setDatasetTrigger(event.target.value)} placeholder="e.g. my_character" /></label>
              <label>Output size<select value={datasetSize} onChange={(event) => setDatasetSize(+event.target.value)}><option value={0}>Original</option><option value={512}>512 × 512</option><option value={768}>768 × 768</option><option value={1024}>1024 × 1024</option></select></label>
              <label className="dataset-check"><input type="checkbox" checked={datasetCrop} onChange={(event) => setDatasetCrop(event.target.checked)} /> Centre crop to square</label>
            </div>
            <section className="variation-studio">
              <header><div><h3>Dataset Variation Studio</h3><p>Create deliberate pose and camera variations with the active Froja checkpoint and LoRAs. Each completed result is added here for your review—never exported automatically.</p></div><em>{datasetJobState}</em></header>
              <label>Base subject and style<textarea value={datasetBasePrompt} onChange={(event)=>setDatasetBasePrompt(event.target.value)} placeholder="Recovered prompt appears here, or describe the character and style that must remain consistent…" /></label>
              <div className="pose-grid">{datasetPoseOptions.map(([name,guide])=><button key={name} className={datasetVariation===name?"selected":""} onClick={()=>setDatasetVariation(name)}><b>{name}</b><small>{guide}</small></button>)}</div>
              <div className="variation-actions"><span>Uses active model: <b>{current?.name || "Choose a checkpoint"}</b> · {selectedLoras.length} LoRA selected</span><button className="primary" disabled={!!datasetJob || !checkpoint} onClick={generateDatasetVariation}>{datasetJob ? `Generating: ${datasetJobState}…` : `Generate ${datasetVariation}`}</button></div>
            </section>            <div className="dataset-list">
              {!datasetItems.length && <div className="dataset-empty"><Icon name="image" /><b>No training images yet</b><span>Add the current result or choose your own images. Froja only processes them when you ask.</span></div>}
              {datasetItems.map((item, index) => <article key={item.id}><img src={item.image} alt={item.name} /><div><b>{String(index + 1).padStart(3,"0")} · {item.name}</b><small>{item.state}</small>{item.metadata && <em className="dataset-metadata">{item.metadata}</em>}<textarea value={item.caption} onChange={(event) => setDatasetItems((items) => items.map((entry) => entry.id === item.id ? {...entry, caption:event.target.value} : entry))} placeholder="Describe this image for LoRA training…" /><span><button onClick={() => inspectDatasetItem(item.id)}>Read Original Prompt & Settings</button><button onClick={() => captionDatasetItem(item.id)}>Create Caption Visually</button><button onClick={() => setDatasetItems((items) => items.filter((entry) => entry.id !== item.id))}>Remove</button></span></div></article>)}
            </div>
            <footer className="dataset-footer"><span><b>{datasetItems.length}</b> image/caption pairs · ZIP includes dataset.json</span><button className="primary" disabled={!datasetItems.length} onClick={exportDataset}>Export LoRA Dataset ZIP</button></footer>
            <div className="dataset-state">{datasetState}</div>
          </div>
        </div>
      )}
      {repairOpen && (
        <div className="modal face-modal" onClick={() => setRepairOpen(false)}>
          <div
            className="drawer wide tool-drawer repair-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <h2>Froja Repair Studio</h2>
                <p>Detect and rebuild damaged faces, hands, or body anatomy.</p>
              </div>
              <button onClick={() => setRepairOpen(false)}>×</button>
            </header>
            <div className="tool-layout">
              <div className="tool-upload">
                <b>Image to inspect and repair</b>
                <small>Froja will edit only detected regions</small>
                <input
                  type="file"
                  aria-label="Choose repair image"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => {
                    setRepairBox(null);
                    loadFaceFile(e.target.files?.[0], setRepairSource);
                  }}
                />
                {repairSource ? (
                  <div
                    className={`repair-canvas ${repairMode === "box" ? "selecting" : ""}`}
                    onPointerDown={startRepairBox}
                    onPointerMove={moveRepairBox}
                    onPointerUp={() => setRepairDrag(null)}
                  >
                    <img src={repairSource} alt="Source image for repair" draggable={false} />
                    {repairMode === "box" && repairBox && (
                      <span
                        className="repair-selection"
                        style={{
                          left: `${repairBox.x * 100}%`,
                          top: `${repairBox.y * 100}%`,
                          width: `${repairBox.w * 100}%`,
                          height: `${repairBox.h * 100}%`,
                        }}
                      />
                    )}
                  </div>
                ) : (
                  <span>Choose an image</span>
                )}
              </div>
              {repairResult && (
                <div className="tool-upload repair-after">
                  <b>Repaired result</b>
                  <img src={repairResult} alt="Repair result" />
                </div>
              )}
            </div>
            <label className="face-setting">
              Repair target
              <select
                value={repairMode}
                onChange={(e) => setRepairMode(e.target.value)}
              >
                <option value="face">Face and eyes</option>
                <option value="hands">Hands and fingers</option>
                <option value="body">Body and posture</option>
                <option value="box">Manual selection box</option>
              </select>
            </label>
            {repairMode === "box" && (
              <div className="repair-box-help">
                <b>Drag directly over the image to draw the repair box.</b>
                <span>
                  Use a tight box around one face, eye, hand, or damaged object.
                </span>
                {repairBox && (
                  <button onClick={() => setRepairBox(null)}>
                    Clear selection
                  </button>
                )}
              </div>
            )}
            <label className="tool-prompt">
              Repair instructions
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Preserve the person, expression, clothing and composition…"
              />
            </label>
            <label className="tool-range">
              Repair strength <b>{repairStrength.toFixed(2)}</b>
              <input
                type="range"
                min="0.15"
                max="0.75"
                step=".05"
                value={repairStrength}
                onChange={(e) => setRepairStrength(+e.target.value)}
              />
            </label>
            <p className="face-note">
              Use 0.25–0.40 for subtle corrections. Body/Posture can change more
              of the person; use Inpainting when you need to select an exact
              area manually.
            </p>
            {error && <div className="error">{error}</div>}
            <button
              className="generate face-run"
              disabled={
                !repairSource ||
                !!repairJob ||
                (repairMode === "box" && !repairBox)
              }
              onClick={runRepair}
            >
              {repairJob ? `Repairing: ${repairState}…` : "Inspect & Repair"}
            </button>
            {repairResult && (
              <div className="face-result repair-result">
                <h3>Completed repair</h3>
                <a href={repairResult} download>
                  Open or save result
                </a>
              </div>
            )}
          </div>
        </div>
      )}

      {modelOpen && (
        <div className="modal" onClick={() => setModelOpen(false)}>
          <div className="drawer wide" onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <h2>Checkpoint Library</h2>
                <p>
                  {models.length} linked models ·{" "}
                  {models.filter((m) => m.preview).length} with previews ·
                  nothing copied
                </p>
              </div>
              <button onClick={() => setModelOpen(false)}>×</button>
            </header>
            <input
              autoFocus
              placeholder="Search checkpoints by name…"
              value={modelQuery}
              onChange={(e) => setModelQuery(e.target.value)}
            />
            {verifiedCompactModels.length > 0 && (
              <div className="verified-models">
                <div>
                  <b>Ready for this 12 GB GPU</b>
                  <small>ComfyUI diffusion models available through Froja</small>
                </div>
                {verifiedCompactModels.map((m) => (
                  <button key={m.path} onClick={() => { setCheckpoint(m.relative); setModelOpen(false); }}>
                    <span>{m.architecture}</span>
                    <b>{m.name.replace(/\.(safetensors|ckpt|gguf)$/i, "")}</b>
                    <small>{sizeLabel(m.size)}</small>
                  </button>
                ))}
              </div>
            )}
            <div className="library-grid">
              {visibleModels.map((m) => (
                <button
                  key={m.path}
                  className={checkpoint === m.relative ? "selected" : ""}
                  onClick={() => {
                    setCheckpoint(m.relative);
                    setModelOpen(false);
                  }}
                >
                  <div className="card-preview">
                    {previewUrl(m) ? (
                      <img src={previewUrl(m)} alt={`${m.name} checkpoint preview`} loading="lazy" />
                    ) : (
                      <span>{m.architecture}</span>
                    )}
                    <i>{checkpoint === m.relative ? "✓" : ""}</i>
                  </div>
                  <b title={m.name}>
                    {m.name.replace(/\.(safetensors|ckpt|gguf)$/i, "")}
                  </b>
                  <small>
                    {m.architecture} · {m.source}
                  </small>
                  {["Flux2-Klein", "Mage-Flow", "Krea-2"].includes(m.architecture) && m.size < 10 * 1024 ** 3 && (
                    <span className="compact-model-badge">Verified for this 12 GB GPU</span>
                  )}
                  <em>{sizeLabel(m.size)}</em>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
      {loraOpen && (
        <div className="modal" onClick={() => setLoraOpen(false)}>
          <div className="drawer wide" onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <h2>Attach LoRA to Prompt</h2>
                <p>
                  {loras.length} linked LoRAs · right-click a card for preview
                  and generation actions
                </p>
              </div>
              <button onClick={() => setLoraOpen(false)}>×</button>
            </header>
            <input
              autoFocus
              placeholder="Search LoRAs by name or trigger…"
              value={loraQuery}
              onChange={(e) => setLoraQuery(e.target.value)}
            />
            {selectedLoras.length > 0 && (
              <div className="selected-loras">
                <h3>Attached to this prompt</h3>
                {selectedLoras.map((l) => (
                  <div key={l.path}>
                    {previewUrl(l) ? (
                      <img src={previewUrl(l)} alt={`${l.name} LoRA preview`} />
                    ) : (
                      <span>Lo</span>
                    )}
                    <b>{l.name}</b>
                    <input
                      type="range"
                      min="0"
                      max="2"
                      step=".05"
                      value={l.strength}
                      onChange={(e) =>
                        setSelectedLoras((v) =>
                          v.map((x) =>
                            x.path === l.path
                              ? { ...x, strength: +e.target.value }
                              : x,
                          ),
                        )
                      }
                    />
                    <em>{l.strength.toFixed(2)}</em>
                    <button onClick={() => toggleLora(l)}>×</button>
                  </div>
                ))}
              </div>
            )}
            <div className="library-grid">
              {visibleLoras.map((l) => {
                const chosen = selectedLoras.some((x) => x.path === l.path);
                return (
                  <button
                    key={l.path}
                    className={chosen ? "selected" : ""}
                    onClick={() => toggleLora(l)}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      setContextLora({ item: l, x: e.clientX, y: e.clientY });
                    }}
                  >
                    <div className="card-preview">
                      {previewUrl(l) ? (
                        <img src={previewUrl(l)} alt={`${l.name} LoRA preview`} loading="lazy" />
                      ) : (
                        <span>LoRA</span>
                      )}
                      <i>{chosen ? "✓" : "＋"}</i>
                    </div>
                    <b title={l.name}>
                      {l.name.replace(/\.safetensors$/i, "")}
                    </b>
                    <small>{l.base_model || l.source}</small>
                    {l.triggers?.length ? (
                      <p className="trigger-line">
                        Trigger: {l.triggers.slice(0, 3).join(", ")}
                      </p>
                    ) : (
                      <p className="trigger-line muted">
                        No saved trigger words
                      </p>
                    )}
                    <em>{sizeLabel(l.size)}</em>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
      {faceOpen && (
        <div className="modal face-modal" onClick={() => setFaceOpen(false)}>
          <div className="drawer wide" onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <h2>Froja Face Studio</h2>
                <p>
                  Replace a face locally using ReActor and restore it with
                  CodeFormer or GFPGAN.
                </p>
              </div>
              <button onClick={() => setFaceOpen(false)}>×</button>
            </header>
            <div className="face-grid">
              <label>
                <b>1. Source face</b>
                <small>The identity you want to use</small>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) =>
                    loadFaceFile(e.target.files?.[0], setFaceSource)
                  }
                />
                {faceSource ? (
                  <img src={faceSource} alt="Source face" />
                ) : (
                  <span>Choose a clear, front-facing face</span>
                )}
              </label>
              <label>
                <b>2. Target image</b>
                <small>The image whose face will be replaced</small>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) =>
                    loadFaceFile(e.target.files?.[0], setFaceTarget)
                  }
                />
                {faceTarget ? (
                  <img src={faceTarget} alt="Target image for face replacement" />
                ) : (
                  <span>Choose the destination image</span>
                )}
              </label>
            </div>
            <label className="face-setting">
              Face restoration
              <select
                value={faceRestore}
                onChange={(e) => setFaceRestore(e.target.value)}
              >
                <option value="codeformer-v0.1.0.pth">CodeFormer</option>
                <option value="GFPGANv1.4.pth">GFPGAN 1.4</option>
                <option value="GPEN-BFR-512.onnx">GPEN 512</option>
                <option value="none">No restoration</option>
              </select>
            </label>
            <p className="face-note">
              Use images you own or have permission to edit. Face processing
              stays on this computer.
            </p>
            {error && <div className="error">{error}</div>}
            <button
              className="generate face-run"
              disabled={!faceSource || !faceTarget || !!faceJob}
              onClick={runFaceSwap}
            >
              {faceJob ? `Face Studio: ${faceState}…` : "Replace Face"}
            </button>
            {faceResult && (
              <div className="face-result">
                <h3>Completed result</h3>
                <img src={faceResult} alt="Face Studio result" />
                <a href={faceResult} download>
                  Open or save result
                </a>
              </div>
            )}
          </div>
        </div>
      )}
      {contextLora && (
        <div
          className="context-menu"
          style={{
            left: Math.min(contextLora.x, window.innerWidth - 245),
            top: Math.min(contextLora.y, window.innerHeight - 170),
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div>
            <b>{contextLora.item.name.replace(/\.safetensors$/i, "")}</b>
            <small>LoRA actions</small>
          </div>
          <button onClick={() => prepareLora(contextLora.item)}>
            ＋ Attach to prompt
          </button>
          <button onClick={() => prepareLora(contextLora.item)}>
            ✦ Prepare generation
          </button>
          <button
            disabled={!hasGenerated}
            onClick={() => setLoraPreview(contextLora.item)}
          >
            ▧ Use latest image as preview
          </button>
          {!hasGenerated && (
            <p>Generate an image first to enable preview assignment.</p>
          )}
        </div>
      )}
    </main>
  );
}
