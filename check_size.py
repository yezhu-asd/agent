import os
from pathlib import Path

root = Path(r'E:\wu\xidian\job\java\agent\CampusCare')
sizes = []
for d in root.iterdir():
    if d.is_dir():
        total = 0
        for f in d.rglob('*'):
            if f.is_file():
                total += f.stat().st_size
        sizes.append((total, d.name))

sizes.sort(key=lambda x: -x[0])
for size, name in sizes:
    mb = size / 1024 / 1024
    if mb > 10:
        print(f"{mb:>8.1f} MB  {name}")
    else:
        print(f"{mb:>8.1f} MB  {name}")
