# font_test_scene.py
# Standalone Scene that displays many LabelNodes with different fonts.
# Run in Pythonista. Tap the screen to toggle between sample texts/sizes.

import ui
from scene import Scene, SceneView, LabelNode

# Useful: print available font names (large list)
# In Pythonista this is the authoritative list you can use.
def print_available_fonts():
    fonts = ui.list_fonts()
    print(f"Total fonts: {len(fonts)}")
    for f in fonts:
        print(f)

# A curated set of fonts worth testing for your "+2" annotation use case.
# NOTE: Some "<System-...>" pseudo-fonts may not exist in older Pythonista builds;
# those will silently fall back and look unchanged.
FONT_CANDIDATES = [
    # System pseudo-fonts (may vary by Pythonista version)
    "<System>",
    "<System-Bold>",
    "<System-Italic>",
    "<System-Mono>",
    "<System-Mono-Bold>",
    "<System-Rounded>",
    "<System-Rounded-Bold>",

    # Common installed fonts (typically present)
    "HelveticaNeue",
    "HelveticaNeue-Medium",
    "HelveticaNeue-Bold",
    "HelveticaNeue-Italic",

    "AvenirNext-Regular",
    "AvenirNext-Medium",
    "AvenirNext-DemiBold",
    "AvenirNext-Bold",

    "SFProText-Regular",      # may exist depending on iOS / Pythonista
    "SFProText-Semibold",
    "SFProText-Bold",

    "Menlo-Regular",
    "Menlo-Bold",

    "Courier",
    "Courier-Bold",
]

class FontTestScene(Scene):
    def setup(self):
        self.background_color = "#3A3A3A"  # similar dark gray

        # Toggle states
        self._toggle = 0
        self._make_labels()

        # Print fonts to console once (comment out if annoying)
        #print_available_fonts()

    def _make_labels(self):
        # Clear existing labels
        if hasattr(self, "labels"):
            for n in self.labels:
                n.remove_from_parent()

        self.labels = []
        w, h = self.size.w, self.size.h

        # Choose sample text + size
        if self._toggle == 0:
            sample_text = "+2  00:00  Material"
            size = 9
        elif self._toggle == 1:
            sample_text = "+2"
            size = 10
        else:
            sample_text = "1234567890 +2"
            size = 12

        # Layout in columns
        col_w = w / 2
        x_left = col_w * 0.1
        x_right = col_w * 1.1

        y = h - 60
        line_h = 34

        # Header
        header = LabelNode("Font test (tap to cycle samples)", position=(w/2, h-24))
        header.font = ("<System-Bold>", 18)
        header.color = "white"
        self.add_child(header)
        self.labels.append(header)

        # Render font candidates
        for i, font_name in enumerate(FONT_CANDIDATES):
            x = x_left if (i % 2 == 0) else x_right
            if i % 2 == 0 and i != 0:
                y -= line_h

            label = LabelNode(f"{font_name}: {sample_text}", position=(x, y))
            # LabelNode anchor is center by default; make it feel like a left-aligned list
            label.anchor_point = (0, 0.5)

            # Try the font; if Pythonista can't resolve it, it may silently fall back.
            label.font = (font_name, size)
            label.color = "white"

            self.add_child(label)
            self.labels.append(label)

        # Footer note
        note = LabelNode("If multiple lines look identical, those font names are not being resolved in this build.", position=(w/2, 22))
        note.font = ("<System>", 14)
        note.color = "white"
        self.add_child(note)
        self.labels.append(note)

    def touch_began(self, touch):
        self._toggle = (self._toggle + 1) % 3
        self._make_labels()

def main():
    v = SceneView()
    v.scene = FontTestScene()
    v.present("fullscreen")

if __name__ == "__main__":
    main()
