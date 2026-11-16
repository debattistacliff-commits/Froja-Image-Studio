import os
import sys
import wave
import argparse
from pathlib import Path

import numpy as np


PRIVATE_PACKAGES = Path(r"G:\WanGP_Private\KokoroRuntime\packages")
KOKORO_MODEL = Path(r"G:\WanGP_Private\Kokoro-82M\kokoro-v1_0.pth")
KOKORO_CONFIG = Path(r"G:\WanGP_Private\Kokoro-82M\config.json")
KOKORO_VOICE = Path(r"G:\WanGP_Private\Kokoro-82M\voices\bm_george.pt")
OUTPUT = Path(r"G:\Archive\JarvisVoiceAssistant\CivilAI-ImageStudio\outputs\video-editor\froja_talking_voice.wav")
DEFAULT_TEXT = (
    "Hello, welcome to Froja. Today we are testing a completely local way "
    "to bring a portrait to life, with natural speech and visible movement."
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Froja offline Kokoro speech")
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--output", default=str(OUTPUT))
    parser.add_argument("--voice", default=str(KOKORO_VOICE))
    parser.add_argument("--speed", type=float, default=0.96)
    args = parser.parse_args()
    os.environ["HF_HUB_OFFLINE"] = "1"
    sys.path.insert(0, str(PRIVATE_PACKAGES))

    import torch
    from kokoro import KModel, KPipeline

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = KModel(
        repo_id="hexgrad/Kokoro-82M",
        config=str(KOKORO_CONFIG),
        model=str(KOKORO_MODEL),
    ).to(device).eval()
    pipeline = KPipeline(lang_code="b", model=model, device=device)

    chunks = []
    for result in pipeline(args.text, voice=args.voice, speed=max(0.6, min(1.4, args.speed))):
        if result.audio is not None:
            chunks.append(result.audio.detach().float().cpu().numpy())
    if not chunks:
        raise RuntimeError("Kokoro produced no audio")

    audio = np.concatenate(chunks)
    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        audio = audio / max(peak, 1.0)
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype("<i2")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(pcm.tobytes())
    print(f"FROJA_TTS_OK={output}")
    print(f"SAMPLES={len(pcm)} DURATION={len(pcm) / 24000:.3f}")


if __name__ == "__main__":
    main()
