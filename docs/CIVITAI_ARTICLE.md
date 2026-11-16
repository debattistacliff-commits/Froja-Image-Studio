# Building Froja Image Studio: A Local-First Creative Workspace for ComfyUI

![Froja Image Studio banner](https://huggingface.co/spaces/cliffrd/Froja-Image-Studio-Preview/resolve/main/assets/froja-brand-banner.png)

## A personal project growing into an open creative tool

Froja Image Studio began with a straightforward idea: local AI image creation should feel organised, visual and approachable without forcing users to duplicate enormous model libraries or abandon the tools they already trust.

I already had checkpoints, LoRAs, embeddings and ComfyUI workflows stored on my own computer. I did not want another application that copied those files and filled another drive. I wanted one professional workspace that could discover the existing libraries, keep them in place and make the creative process easier to understand.

That idea became Froja.

Froja is an independent, local-first image studio built around ComfyUI and user-owned models. It is an active work in progress, but the central image workflow is already usable and the project is now open for feedback and collaboration.

## What Froja is designed to solve

Powerful local image systems often expose every technical detail at once. That flexibility is valuable, but it can also make common creative work unnecessarily complicated.

Froja aims to place the most useful controls into focused studios:

- Browse checkpoints and LoRAs from linked folders without copying model weights.
- Compose positive and negative prompts in a clear workspace.
- Attach LoRAs visually and preserve their trigger information.
- Apply styles, camera direction, lighting and reusable prompt cards.
- Generate through a user-managed ComfyUI installation.
- Inspect outputs, zoom into details and open the output location.
- Enhance, relight, repair and prepare images through dedicated tools.
- Build controlled image sets for future LoRA training.

The goal is not to replace ComfyUI. Froja provides a more guided creative layer while ComfyUI remains the generation engine.

![Froja Image Studio interface](https://huggingface.co/spaces/cliffrd/Froja-Image-Studio-Preview/resolve/main/assets/froja-studio.png)

## Your models stay yours

One of Froja's most important principles is that existing model libraries should remain where they are.

Froja can be configured to index user-managed checkpoint, LoRA, VAE and embedding folders. This avoids maintaining a second copy of large files and allows people to organise storage according to their own system.

The public project does not include copyrighted checkpoints, private outputs, personal paths, API keys or anyone's private model collection. Every user supplies and manages their own compatible resources.

## Creation Studio

The main workspace brings prompt writing, model selection, LoRAs, styles, camera controls and generation settings together. The preview area retains useful generation information such as checkpoint, seed, size, sampler and prompt, making results easier to understand and reproduce.

Froja also includes prompt assistance designed to work with a local Ollama installation. This is optional: users remain in control of whether a prompt is enhanced and which local language model is used.

## Froja Training Studio

Creating a useful LoRA dataset requires more than producing several nearly identical images. A training set benefits from controlled variety, clear captions and careful quality selection.

Froja Training Studio is being developed to help plan complementary views—for example front, three-quarter, side, back, top, detail, in-use and environmental compositions. Images run sequentially for safer GPU usage and can be inspected before they are approved for a dataset.

The intention is to help users create cleaner reference sets while keeping the final decisions in human hands.

## Appearance Library and prompt cards

Froja's Appearance Library explores a visual way to direct materials, surfaces, hair, hands, environments, fabrics and colour harmony. Reusable prompt cards can combine a subject, material, pose, environment, lighting setup and camera direction into a consistent creative brief.

This is prompt and reference direction—not a claim of physically exact 3D material simulation. The selected properties guide the generation workflow while the result still depends on the chosen model and workflow.

## A public interactive preview

The new Hugging Face Space offers a safe taste of the project without uploading private models or requiring a GPU. Visitors can explore the interface, build a prompt interactively, try different subject, style, material, camera and lighting combinations, and read the current roadmap.

**Try the interactive preview:**  
https://huggingface.co/spaces/cliffrd/Froja-Image-Studio-Preview

**View the source and documentation:**  
https://github.com/debattistacliff-commits/Froja-Image-Studio

## Current status

Froja remains an active work in progress. The image studio and public presentation are available today, while some advanced editing, compatibility and training workflows still depend on the ComfyUI nodes and models installed on each machine.

The unfinished experimental video work is deliberately not part of this public release. The priority is to make the image experience dependable, understandable and properly documented before expanding the public scope.

## Collaboration is welcome

I would especially value help with:

- Testing different ComfyUI installations and checkpoint families.
- Reproducible bug reports with clear terminal output.
- Accessibility and interface improvements.
- Windows and Linux packaging.
- Documentation and workflow examples.
- Model metadata, previews and compatibility detection.
- Careful, focused code contributions.

If you test Froja, please describe your hardware, operating system, ComfyUI setup, selected model and the exact steps that produced the issue. This makes feedback much more useful than a general report that something failed.

## The direction

Froja is intended to become a welcoming bridge between creative users and powerful local AI image workflows: professional enough for serious work, clear enough to learn and open enough for the community to improve.

This project has grown through experimentation, testing, mistakes and many rounds of refinement. It is still evolving, and constructive suggestions are genuinely welcome.

Thank you for taking a look at Froja Image Studio.

---

### Suggested Civitai tags

`Froja` `ComfyUI` `Stable Diffusion` `Local AI` `Image Generation` `LoRA` `LoRA Training` `Workflow` `Open Source` `AI Tools` `Prompt Engineering` `Image Editing`

