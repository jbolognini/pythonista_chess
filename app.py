import ui
from game_view import GameView

class Menu(ui.View):
    def __init__(self):
        super().__init__()
        self.name = "Bol Chess"
        self.background_color = "white"

        # Title
        self.title_label = ui.Label()
        self.title_label.text = "Bol Chess"
        self.title_label.font = ("<System-Bold>", 28)
        self.title_label.alignment = ui.ALIGN_CENTER
        self.title_label.text_color = "#222"
        self.title_label.flex = "W"
        self.add_subview(self.title_label)

        # Subtitle (optional but nice)
        self.subtitle = ui.Label()
        self.subtitle.text = "Opening practice & engine play"
        self.subtitle.font = ("<System>", 14)
        self.subtitle.alignment = ui.ALIGN_CENTER
        self.subtitle.text_color = "#666"
        self.subtitle.flex = "W"
        self.add_subview(self.subtitle)

        # New Game button
        self.btn_new = ui.Button(title="New Game")
        self.btn_new.font = ("<System-Bold>", 16)
        self.btn_new.background_color = "#2d7df6"
        self.btn_new.tint_color = "white"
        self.btn_new.corner_radius = 10
        self.btn_new.action = self.new_game
        self.add_subview(self.btn_new)

    def layout(self):
        w = self.width

        self.title_label.frame = (0, 60, w, 36)
        self.subtitle.frame = (0, 100, w, 20)

        self.btn_new.frame = (
            (w - 220) / 2,
            160,
            220,
            48
        )

    def new_game(self, sender):
        GameView().present(
            style="full_screen",
            orientations=('portrait', 'portrait-upside-down'),
        )

Menu().present(
    "full_screen",
    orientations=('portrait', 'portrait-upside-down'),
)
