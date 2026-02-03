#!/usr/bin/env python3
"""
Create a composite image showing v0.15 features
"""

from PIL import Image

# Load screenshots
costs = Image.open('/Users/leo/.local/share/codex-dual/screenshots/costs.png')
templates = Image.open('/Users/leo/.local/share/codex-dual/screenshots/templates.png')
export_img = Image.open('/Users/leo/.local/share/codex-dual/screenshots/export.png')

# Resize to 700px width (as shown in README)
width = 700
def resize_to_width(img, target_width):
    ratio = target_width / img.width
    new_height = int(img.height * ratio)
    return img.resize((target_width, new_height), Image.Resampling.LANCZOS)

costs_small = resize_to_width(costs, width)
templates_small = resize_to_width(templates, width)
export_small = resize_to_width(export_img, width)

# Create vertical composite
total_height = costs_small.height + templates_small.height + export_small.height + 40  # 20px spacing each
composite = Image.new('RGB', (width, total_height), (10, 10, 15))  # Dark background

# Paste images with spacing
y_offset = 0
composite.paste(costs_small, (0, y_offset))
y_offset += costs_small.height + 20

composite.paste(templates_small, (0, y_offset))
y_offset += templates_small.height + 20

composite.paste(export_small, (0, y_offset))

# Save
output_path = '/Users/leo/.local/share/codex-dual/screenshots/webui-v015-features.png'
composite.save(output_path, optimize=True)
print(f"✅ Created composite image: {output_path}")
print(f"   Size: {composite.width}x{composite.height}")
