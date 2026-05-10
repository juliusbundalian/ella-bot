import os

for root, _, files in os.walk("src/ella_bot"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            new_content = content.replace("from src.ella_bot", "from ella_bot").replace("import src.ella_bot", "import ella_bot")
            
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Removed src. prefix in {path}")
