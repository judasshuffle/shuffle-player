"""Generate NEW demo assets only, refusing existing destinations."""
import math
from pathlib import Path
import sqlite3
import struct
import wave


def generate(music, database):
    music, database = Path(music), Path(database)
    if music.exists() or database.exists():
        raise RuntimeError("Fixture destinations must not exist")
    music.mkdir(parents=True)
    database.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(database)
    con.execute("CREATE TABLE tracks(path TEXT PRIMARY KEY,artist TEXT,album TEXT,title TEXT,duration REAL,year INTEGER)")
    for number, (title, frequency) in enumerate((("Copper Pulse", 220), ("Night Orbit", 330), ("Signal Garden", 440)), 1):
        path = music / (title + ".wav")
        with wave.open(str(path), "wb") as wav:
            wav.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            wav.writeframes(b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * frequency * i / 22050)
                * (0.2 + 0.8 * max(0, math.sin(2 * math.pi * 2 * i / 22050))))) for i in range(22050 * 16)))
        con.execute("INSERT INTO tracks VALUES(?,?,?,?,?,?)", ("/mnt/lossless/" + path.name,
                    "Preview Synth", "Synthetic Sessions", title, 16, 2026))
    con.execute("INSERT INTO tracks VALUES(?,?,?,?,?,?)", ("/mnt/lossless/Missing.wav", "Preview Synth", "Synthetic Sessions", "Missing Track", 16, 2026))
    con.commit()
    con.close()
    database.chmod(0o444)


if __name__ == "__main__":
    generate("/mnt/lossless", "/data/jukebox.db")
