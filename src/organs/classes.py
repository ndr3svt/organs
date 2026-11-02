"""Class list. Index 0 is background. Append new classes at the END so existing mask indices stay valid.
Swatch colors are shared by the UI and the masks."""

CLASSES = ["animal", "plant", "fungal", "metaphor", "scifi"]

# class name -> mask index (0 = background)
CLASS_INDEX = {name: i + 1 for i, name in enumerate(CLASSES)}

# swatch colors for the drawing tool and review previews
SWATCH = {
    "animal": (214, 69, 80),
    "plant": (67, 160, 71),
    "fungal": (230, 170, 40),
    "metaphor": (66, 135, 245),
    "scifi": (156, 90, 214),
}

NUM_CLASSES = len(CLASSES) + 1  # including background
