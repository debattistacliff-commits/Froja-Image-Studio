# Contributing to Froja

Thank you for helping improve Froja Image Studio. Contributions from artists, testers, translators, workflow authors, designers, and developers are welcome.

## Good ways to help

- Reproduce and document bugs on different GPUs and operating systems.
- Improve Windows and Linux setup.
- Add safe model-family adapters and validation.
- Improve accessibility, translations, keyboard navigation, and responsive layout.
- Add tests for ComfyUI workflows without distributing model weights.
- Improve documentation and screenshots.

## Before opening an issue

Search existing issues, run the current release checks, and remove private paths, prompts, images, tokens, and model filenames you cannot share.

For bugs, include the Froja version, operating system, GPU/VRAM, Python version, Node version, ComfyUI version, steps to reproduce, expected behavior, and sanitized logs.

## Pull requests

1. Fork the repository and create a focused branch.
2. Keep machine-specific configuration in `config/config.local.json`.
3. Never commit models, outputs, runtime caches, logs, or private images.
4. Run `npm run lint`, `npx tsc --noEmit`, and `npm test`.
5. Explain what changed, why, user impact, and validation performed.

Small, focused pull requests are easier to review. New integrations should fail gracefully when optional software or models are unavailable.

## Workflow adapters

Workflow contributions must document required ComfyUI nodes and model filenames, validate user inputs, cap unsafe dimensions/settings, use local-only endpoints by default, and include a test that does not require downloading model weights.

By contributing, you agree that your contribution is licensed under the MIT License.
