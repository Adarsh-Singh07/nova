"""Benchmark script to measure latency of audio processing, STT, and TTS on CPU."""

from __future__ import annotations

import time

import numpy as np

from nova.audio.vad import EnergyVAD
from nova.stt.whisper_engine import WhisperEngine
from nova.tts.piper_engine import PiperEngine, TTSDiskCache


def benchmark() -> dict[str, float]:
    print("=== NOVA Performance & Latency Benchmark ===")
    results: dict[str, float] = {}

    # 1. VAD Frame Processing Latency (30ms frame = 480 samples)
    vad = EnergyVAD()
    frame = (0.1 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.03, 480, endpoint=False))).astype(
        np.float32
    )

    t0 = time.perf_counter()
    for _ in range(1000):
        vad.is_speech(frame)
    vad_lat_ms = ((time.perf_counter() - t0) / 1000.0) * 1000.0
    print(f"1. VAD 30ms Frame Latency: {vad_lat_ms:.4f} ms")
    results["vad_frame_ms"] = vad_lat_ms

    # 2. TTS Cache Hit vs Cold Synthesis
    cache = TTSDiskCache()
    engine = PiperEngine(cache=cache)

    # Prime synthesis
    phrase = "Turning volume up."
    t0 = time.perf_counter()
    cold_wav = engine.synthesize(phrase)
    cold_lat_ms = (time.perf_counter() - t0) * 1000.0
    print(f"2. TTS Cold Synthesis ({len(cold_wav)} bytes): {cold_lat_ms:.2f} ms")
    results["tts_cold_ms"] = cold_lat_ms

    # Cache hit
    t0 = time.perf_counter()
    _ = engine.synthesize(phrase)
    cache_lat_ms = (time.perf_counter() - t0) * 1000.0
    print(f"3. TTS Disk Cache Hit Replay: {cache_lat_ms:.4f} ms")
    results["tts_cache_hit_ms"] = cache_lat_ms

    # 3. faster-whisper STT Inference on CPU (tiny.en)
    print("4. Testing faster-whisper (tiny.en, int8)...")
    stt = WhisperEngine(model_size="tiny.en", compute_type="int8")
    t0 = time.perf_counter()
    stt.load_model()
    load_time_sec = time.perf_counter() - t0
    print(f"   Model Load Time: {load_time_sec:.2f} s")
    results["stt_model_load_s"] = load_time_sec

    # 2-second synthesized audio clip for inference benchmark
    sample_rate = 16000
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    synthetic_audio = (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)

    t0 = time.perf_counter()
    _ = stt.transcribe(synthetic_audio)
    stt_inf_ms = (time.perf_counter() - t0) * 1000.0
    print(f"   STT Inference (2.0s audio): {stt_inf_ms:.2f} ms")
    results["stt_inference_2s_ms"] = stt_inf_ms

    total_est_ms = vad_lat_ms + stt_inf_ms + cache_lat_ms
    print(f"\nEstimated End-to-End Latency (PTT release to Action): {total_est_ms:.2f} ms")
    print(f"Target Budget (<= 1500 ms): {'PASS' if total_est_ms <= 1500.0 else 'FAIL'}")

    return results


if __name__ == "__main__":
    benchmark()
