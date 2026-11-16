# Froja Private Video Studio

This experimental integration is disabled by default and is not part of the public Froja release.

Froja communicates with a separately installed WanGP runtime through `extensions/wangp_private_bridge.py`. WanGP code and model weights are not copied into Froja. The bridge uses WanGP's documented Python API and keeps the runtime in its own Python environment.

Before any public release, re-check the current WanGP Community License, preserve its notices, disclose the optional integration in Froja's About page and documentation, and contact the WanGP maintainer if commercial embedding is contemplated.

The current safety profiles are intentionally capped at 832 × 480, MiniMax H3's four-second minimum and one job at a time for a 12 GB RTX 4070 Ti. Text-to-video and image-to-video are the first validation targets. Video editing and audio/reference modes are visible design placeholders until their model-specific schemas are verified.
