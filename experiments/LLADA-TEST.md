# LLaDA isolated compatibility trial

This is a trial, not a validated Froja checkpoint. Existing Krea/SenseNova
packages, workflows and model choices are not modified.

Runtime: https://github.com/RealRebelAI/LLaDa-Image_ComfyUI
Inspected revision: 12597edf68b0e5d27842a1a970a769692e63aca9

Quantized weights: https://huggingface.co/realrebelai/LLaDa-Image-Turbo_ComfyUI
The INT8 transformer, Q4_K_M encoder and VAE require approximately 16 GB.
Official Turbo auxiliary components require another approximately 3.4 GB.
These are disk download sizes, not a guarantee of VRAM requirements.

The smoke test prepends an isolated Diffusers 0.39.0 installation to the
existing ComfyUI Python path. Nothing is installed over the active packages.
The trial defaults to model-level CPU offload and tiled VAE decoding. The
runtime's sequential offload currently conflicts with its lazy GGUF tensors.

From the Froja root, using the configured ComfyUI Python:

```powershell
& G:/ComfyUI_NEW/.venv/Scripts/python.exe scripts/llada_smoke_test.py --check-only
& G:/ComfyUI_NEW/.venv/Scripts/python.exe scripts/llada_smoke_test.py
```

Default compatibility test: 512 x 512, one step, guidance 1, seed 42. Once
that passes, use `--steps 4` for the intended Turbo quality. The output is
`test-output/llada_quantized_smoke.png`. A successful import alone does not
confirm that image generation or face-preserving editing works.

Do not select these files in an SDXL/Krea checkpoint loader. LLaDA requires
its own pipeline and supporting encoder. Add it to Froja's model options
only after a successful generation trial.
