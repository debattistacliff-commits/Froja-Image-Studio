"""Isolated LLaDA quantized smoke test; does not modify the active ComfyUI."""
import argparse
import importlib.util
import json
import logging
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments'
parser = argparse.ArgumentParser()
parser.add_argument('--check-only', action='store_true')
parser.add_argument('--prompt', default='A small bronze robot sitting on a wooden chair, turquoise studio background, warm soft light, detailed product photography.')
parser.add_argument('--width', type=int, default=512)
parser.add_argument('--height', type=int, default=512)
parser.add_argument('--steps', type=int, default=1)
parser.add_argument('--output', default=str(ROOT / 'test-output/llada_quantized_smoke.png'))
parser.add_argument('--offload', choices=['model_cpu_offload', 'sequential_cpu_offload', 'cuda', 'cpu'], default='model_cpu_offload')
args = parser.parse_args()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if args.width < 256 or args.height < 256 or args.width > 1024 or args.height > 1024 or args.width % 32 or args.height % 32:
    parser.error('Trial sizes must be multiples of 32 between 256 and 1024.')
if args.steps < 1 or args.steps > 4:
    parser.error('Turbo trial steps must be between 1 and 4.')
print('Checking isolated LLaDA dependencies...', flush=True)
config = json.loads((ROOT / 'config/config.local.json').read_text())
comfy = Path(config['comfy_root'])
sys.path[:0] = [str(EXP / 'llada-deps'), str(comfy)]
os.environ['HF_HOME'] = str(EXP / 'llada-hf-cache')
repo = EXP / 'LLaDa-Image_ComfyUI'
spec = importlib.util.spec_from_file_location('froja_llada_test', repo / '__init__.py', submodule_search_locations=[str(repo)])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
print('LLaDA custom nodes imported successfully.', flush=True)
model_dir = EXP / 'llada-models'
files = {
    'diffusion_path': 'LLaDA-Image-Turbo-INT8.safetensors',
    'text_encoder_path': 'LLaDA-Image-Turbo-text_encoder-Q4_K_M.gguf',
    'vae_path': 'LLaDa_VAE.safetensors',
}
missing = [name for name in files.values() if not (model_dir / name).is_file()]
print(json.dumps({'missing_files': missing}), flush=True)
if args.check_only:
    sys.exit(0)
if missing:
    raise SystemExit('Wait for the model downloads to finish before generating.')
from froja_llada_test.llada_gguf_adapter import build_llada_pipeline
from froja_llada_test.llada import LLaDAImagePipeline
import torch
selection = {key: str(model_dir / name) for key, name in files.items()}
selection.update(dtype='bfloat16', offload=args.offload, vae_tiling='On')
started = time.time()
print(f'Loading INT8 transformer + Q4 encoder with {args.offload}.', flush=True)
pipe = build_llada_pipeline(selection, LLaDAImagePipeline, repo / 'configs')
result = pipe(prompt=args.prompt, generation_mode='text', width=args.width, height=args.height,
              num_inference_steps=args.steps, guidance_scale=1.0,
              generator=torch.Generator(device='cpu' if 'offload' in args.offload else 'cuda').manual_seed(42),
              output_type='pil')
out = Path(args.output).resolve()
out.parent.mkdir(parents=True, exist_ok=True)
result.images[0].save(out)
print(json.dumps({'image': str(out), 'seconds': round(time.time()-started, 2),
                  'peak_vram_gb': round(torch.cuda.max_memory_allocated()/1024**3, 2)}), flush=True)
