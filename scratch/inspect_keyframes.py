import json
import zipfile
from pathlib import Path

lottie_path = Path(r"d:\Project ELLA\ella-bot\assets\Lightray.lottie")
with zipfile.ZipFile(lottie_path) as z:
    data = json.loads(z.read("a/Main Scene.json"))

print("Animation metadata:")
print("  fr (FPS):", data.get("fr"))
print("  ip (in point / start frame):", data.get("ip"))
print("  op (out point / end frame):", data.get("op"))
print("  w x h:", data.get("w"), "x", data.get("h"))

print("\nLayers count:", len(data.get("layers", [])))
for i, layer in enumerate(data.get("layers", [])):
    print(f"\nLayer {i}: name='{layer.get('nm')}', type={layer.get('ty')}")
    ks = layer.get("ks", {})
    for prop in ["r", "o", "p", "s", "a"]:
        if prop in ks:
            val = ks[prop]
            if isinstance(val, dict) and "k" in val:
                k = val["k"]
                if isinstance(k, list) and len(k) > 0 and isinstance(k[0], dict) and "t" in k[0]:
                    print(f"  {prop} keyframes:")
                    for item in k:
                        if isinstance(item, dict) and "t" in item:
                            print(f"    t={item.get('t')}, start={item.get('s')}, end={item.get('e')}")
                else:
                    print(f"  {prop} static value:", k)
