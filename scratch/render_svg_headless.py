import os
import subprocess
from pathlib import Path

svg_path = Path(r"d:\Project ELLA\ella-bot\assets\Main Menu (1).svg").resolve()

# We render the SVG directly with transparent background stretching edge-to-edge (1024x600 native viewBox)
html_content = f"""<!DOCTYPE html>
<html>
<head>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: 100%; height: 100%; background: transparent; overflow: hidden; }}
img {{ width: 100vw; height: 100vh; object-fit: fill; display: block; }}
</style>
</head>
<body>
<img src="{svg_path.as_uri()}" />
</body>
</html>"""

temp_html = Path(r"d:\Project ELLA\ella-bot\scratch\render_svg.html")
temp_html.write_text(html_content, encoding="utf-8")

# Find Edge
msedge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(msedge_path):
    msedge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

out_png = Path(r"d:\Project ELLA\ella-bot\assets\Main Menu 1080p Transparent.png")

cmd = [
    msedge_path,
    "--headless",
    "--disable-gpu",
    "--default-background-color=00000000",
    "--window-size=1024,600",
    f"--screenshot={out_png}",
    temp_html.as_uri(),
]

print("Executing Chrome/Edge headless rendering...")
subprocess.run(cmd, check=True)
print("SUCCESS! Rendered transparent overlay to:", out_png)
