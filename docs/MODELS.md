# Model and node requirements

Froja itself contains no model weights. Users are responsible for checking every model and node license.

## Standard checkpoints

Standard checkpoint workflows expect a ComfyUI-compatible checkpoint in `models/checkpoints`. SD 1.x and SDXL-family behavior depends on the checkpoint and available VRAM.

## LoRAs

Put LoRAs in `models/loras`. Froja supports up to eight selected LoRAs and recognizes `<lora:name:strength>` tags. A LoRA must match the selected model architecture.

## Z-Image Turbo

The current adapter expects compatible Z-Image Turbo diffusion weights, a Qwen text encoder, an appropriate autoencoder, and the ComfyUI nodes referenced by `backend.py`. Exact filenames may be configured in a future compatibility-profile release.

## Krea-2 Turbo

The current adapter expects a Krea-2 compatible GGUF diffusion model, Qwen3-VL text encoder, Qwen image VAE, and loader/sampler nodes supported by the installed ComfyUI environment.

## Editing tools

Image-to-image, inpainting, ControlNet, IC-Light, Face Studio, Repair Studio, and JoyAI use optional ComfyUI nodes and models. Froja reports validation failures when required components are absent. Consult sanitized logs in `logs/` locally; never upload private logs without reviewing them.
