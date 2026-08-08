import zipfile
import json
from pathlib import Path

lottie_path = Path(r"d:\Project ELLA\ella-bot\assets\shinebg.lottie")
print("Lottie file size:", lottie_path.stat().st_size, "bytes")

if zipfile.is_zipfile(lottie_path):
    with zipfile.ZipFile(lottie_path) as z:
        print("Zip namelist:", z.namelist())
        for name in z.namelist():
            if name.endswith(".json"):
                try:
                    data = json.loads(z.read(name))
                    print("JSON file:", name)
                    if isinstance(data, dict):
                        print("  fr (fps):", data.get("fr"))
                        print("  ip (start frame):", data.get("ip"))
                        print("  op (end frame):", data.get("op"))
                        print("  w:", data.get("w"))
                        print("  h:", data.get("h"))
                        print("  layers count:", len(data.get("layers", [])))
                except Exception as e:
                    print("Error reading json:", name, e)
else:
    print("Not a zip file")
