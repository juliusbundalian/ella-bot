import io
from pathlib import Path
import pygame

pygame.init()
pygame.display.set_mode((1, 1))

svg_path = Path(r"d:\Project ELLA\ella-bot\assets\ic_settings.svg")
svg_text = svg_path.read_text(encoding="utf-8")

# Tint to #FFFAF3 and set size to 48px
svg_tinted = svg_text.replace('fill="#FFFFFF"', 'fill="#FFFAF3"').replace('height="24px"', 'height="48px"').replace('width="24px"', 'width="48px"')
icon_surf = pygame.image.load(io.BytesIO(svg_tinted.encode("utf-8"))).convert_alpha()

print("Icon size:", icon_surf.get_size())
print("Icon loaded successfully!")
