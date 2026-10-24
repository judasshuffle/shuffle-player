"""Capture only default speaker loopback for objective dropout inspection."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / '.capture'))
import json
import time
import wave
import numpy as np
import soundcard as sc

speaker = sc.default_speaker()
loopback = sc.get_microphone(id=speaker.id, include_loopback=True)
assert loopback.isloopback, 'Refuse microphone capture'
rate = 48000
blocks = []
started = time.time()
print('Output-only capture: ' + speaker.name, flush=True)
with loopback.recorder(samplerate=rate, channels=2, blocksize=4800) as recorder:
    for second in range(125):
        blocks.append(recorder.record(numframes=rate))
        if second % 30 == 29:
            print('Captured %d seconds' % (second+1), flush=True)
audio = np.concatenate(blocks)
with wave.open(str(Path(__file__).parent / 'scheduler-output.wav'), 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes((np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes())
windows = audio.reshape(-1, 480, 2)
rms = np.sqrt(np.mean(windows**2, axis=(1, 2)))
quiet = rms < 0.00001
runs = []
begin = None
for i, flag in enumerate(np.r_[quiet, False]):
    if flag and begin is None:
        begin = i
    elif not flag and begin is not None:
        if i-begin >= 2:
            runs.append({'at_s': begin*.01, 'duration_s': (i-begin)*.01})
        begin = None
report = {'started_unix': started, 'duration_s': len(audio)/rate,
    'device': speaker.name, 'peak': float(np.max(np.abs(audio))),
    'rms': float(np.sqrt(np.mean(audio**2))),
    'near_silent_runs_at_least_20ms': runs,
    'note': 'Quiet runs are candidates, not proof of dropouts; music can contain silence. Clicks require listening.'}
path = Path(__file__).parent / 'scheduler-capture-results.json'
path.write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2), flush=True)
