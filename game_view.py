# game_view.py
import ui
import console
import clipboard
import chess
from scene import SceneView

from chess_scene import ChessScene
from openings import opening_options


OPENING_OPTIONS = opening_options()

BAR_HEIGHT = 50
BOTTOM_BAR_HEIGHT = 150
ICON_SIZE = 32
ICON_PADDING_X = 10


# ============================================================
# Settings View
# ============================================================
class SettingsView(ui.View):
    def __init__(
        self,
        initial_vs_ai: bool = True,
        initial_ai_color=chess.BLACK,
        initial_level: int = 1,
        initial_opening_choice=None,
        initial_practice_tier: str = "beginner",
        can_change_opening: bool = True,
        initial_show_sugg_arrows: bool = True,
        initial_cloud_eval: bool = False,
        on_done=None,
    ):
        super().__init__()
        self.name = "Settings"
        self.background_color = "white"
        self.on_done = on_done

        self.can_change_opening = bool(can_change_opening)
        self._opening_choice = initial_opening_choice
        self._show_suggestion_arrows = bool(initial_show_sugg_arrows)
        self._cloud_eval_enabled = bool(initial_cloud_eval)

        # --- Controls ---
        self.sw_vs_ai = ui.Switch(value=bool(initial_vs_ai))
        self.sw_vs_ai.action = self._update_enabled_states

        self.lbl_vs_ai = ui.Label(text="Play vs AI", font=("<System>", 16))

        self.seg_ai_color = ui.SegmentedControl()
        self.seg_ai_color.segments = ["AI plays Black", "AI plays White"]
        self.seg_ai_color.selected_index = 0 if initial_ai_color == chess.BLACK else 1

        self.lbl_level = ui.Label(text="AI Level", font=("<System>", 16))

        self.sl_level = ui.Slider()
        lvl = max(1, min(5, int(initial_level)))
        self.sl_level.value = (lvl - 1) / 4.0
        self.sl_level.action = self._on_level_slider_changed

        self.lbl_level_value = ui.Label(text=str(lvl), font=("<System-Mono>", 16))
        self.lbl_level_value.alignment = ui.ALIGN_RIGHT

        self.lbl_opening = ui.Label(text="Opening practice", font=("<System>", 16))

        self.btn_opening = ui.Button(title=self._opening_title(initial_opening_choice))
        self.btn_opening.action = self._on_pick_opening
        self.btn_opening.background_color = (0.95, 0.95, 0.95)
        self.btn_opening.corner_radius = 8

        self.lbl_tier = ui.Label(text="Practice depth", font=("<System>", 16))

        self.seg_tier = ui.SegmentedControl()
        self.seg_tier.segments = ["Beginner", "Master"]
        self.seg_tier.selected_index = 1 if (initial_practice_tier == "master") else 0

        self.lbl_show_sugg_arrows = ui.Label(text="Show Suggestion Arrows", font=("<System>", 16))

        self.sw_show_sugg_arrows = ui.Switch(value=bool(initial_show_sugg_arrows))
        self.sw_show_sugg_arrows.action = self._on_show_suggestion_arrows_changed

        self.lbl_cloud_eval = ui.Label(text="Cloud Eval", font=("<System>", 16))

        self.sw_cloud_eval = ui.Switch(value=bool(initial_cloud_eval))
        self.sw_cloud_eval.action = self._on_cloud_eval_changed

        self.btn_apply = ui.Button(title="Apply")
        self.btn_apply.action = self._on_apply
        self.btn_apply.background_color = (0.2, 0.55, 1.0)
        self.btn_apply.tint_color = "white"
        self.btn_apply.corner_radius = 8

        self.btn_cancel = ui.Button(title="Cancel")
        self.btn_cancel.action = self._on_cancel
        self.btn_cancel.background_color = (0.9, 0.9, 0.9)
        self.btn_cancel.corner_radius = 8

        for v in (
            self.lbl_vs_ai, self.sw_vs_ai, self.seg_ai_color,
            self.lbl_level, self.sl_level, self.lbl_level_value,
            self.lbl_opening, self.btn_opening,
            self.lbl_tier, self.seg_tier,
            self.lbl_show_sugg_arrows, self.sw_show_sugg_arrows,
            self.lbl_cloud_eval, self.sw_cloud_eval,
            self.btn_apply, self.btn_cancel,
        ):
            self.add_subview(v)

        self._update_enabled_states(None)

    def _opening_title(self, choice):
        for title, key in OPENING_OPTIONS:
            if key == choice:
                return title
        return "Free play"

    def _level_int(self) -> int:
        return int(round(self.sl_level.value * 4)) + 1  # 1..5

    def _on_level_slider_changed(self, sender):
        self.lbl_level_value.text = str(self._level_int())

    def _update_enabled_states(self, sender):
        vs_ai_enabled = bool(self.sw_vs_ai.value)
        self.seg_ai_color.enabled = vs_ai_enabled
        self.sl_level.enabled = vs_ai_enabled

        self.btn_opening.enabled = self.can_change_opening
        self.btn_opening.alpha = 1.0 if self.can_change_opening else 0.4
        self.lbl_opening.text = "Opening practice" if self.can_change_opening else "Opening practice (reset to change)"

    def _on_pick_opening(self, sender):
        if not self.can_change_opening:
            return
        tv = ui.TableView()
        tv.name = "Choose Opening"
        tv.data_source = _OpeningPickerDataSource(self, tv)
        tv.delegate = tv.data_source
        tv.row_height = 44
        tv.present("sheet")

    def _on_show_suggestion_arrows_changed(self, sender):
        self._show_suggestion_arrows = bool(sender.value)
    
    def _on_cloud_eval_changed(self, sender):
        self._cloud_eval_enabled = bool(sender.value)
    
    def _on_apply(self, sender):
        vs_ai = bool(self.sw_vs_ai.value)
        ai_color = chess.BLACK if self.seg_ai_color.selected_index == 0 else chess.WHITE
        level = self._level_int()
        opening_choice = self._opening_choice
        practice_tier = "master" if self.seg_tier.selected_index == 1 else "beginner"
        show_arrows = bool(self._show_suggestion_arrows)
        cloud_eval = bool(self._cloud_eval_enabled)

        if callable(self.on_done):
            self.on_done(
                vs_ai,
                ai_color,
                level,
                opening_choice,
                practice_tier,
                show_arrows,
                cloud_eval
            )
        self.close()

    def _on_cancel(self, sender):
        self.close()

    def layout(self):
        w = self.width
        x = 20
        y = 20

        self.lbl_vs_ai.frame = (x, y, w - 120, 32)
        self.sw_vs_ai.frame = (w - 70, y, 51, 31)

        y += 50
        self.seg_ai_color.frame = (x, y, w - 40, 32)

        y += 55
        self.lbl_level.frame = (x, y, w - 140, 32)
        self.lbl_level_value.frame = (w - 100, y, 80, 32)

        y += 40
        self.sl_level.frame = (x, y, w - 40, 34)

        y += 55
        self.lbl_opening.frame = (x, y, w - 40, 32)

        y += 40
        self.btn_opening.frame = (x, y, w - 40, 44)

        y += 60
        self.lbl_tier.frame = (x, y, w - 40, 32)

        y += 40
        self.seg_tier.frame = (x, y, w - 40, 32)

        y += 55
        self.lbl_show_sugg_arrows.frame = (x, y, w - 120, 32)
        self.sw_show_sugg_arrows.frame = (w - 70, y, 51, 31)

        y += 55
        self.lbl_cloud_eval.frame = (x, y, w - 120, 32)
        self.sw_cloud_eval.frame = (w - 70, y, 51, 31)

        y += 70
        self.btn_apply.frame = (x, y, w - 40, 44)

        y += 54
        self.btn_cancel.frame = (x, y, w - 40, 44)


class _OpeningPickerDataSource(object):
    def __init__(self, parent: SettingsView, tableview: ui.TableView):
        self.parent = parent
        self.tv = tableview

    def tableview_number_of_rows(self, tv, section):
        return len(OPENING_OPTIONS)

    def tableview_cell_for_row(self, tv, section, row):
        title, key = OPENING_OPTIONS[row]
        cell = ui.TableViewCell()
        cell.text_label.text = title
        if key == self.parent._opening_choice:
            cell.accessory_type = "checkmark"
        return cell

    def tableview_did_select(self, tv, section, row):
        title, key = OPENING_OPTIONS[row]
        self.parent._opening_choice = key
        self.parent.btn_opening.title = title
        tv.close()


class _MovesListDataSource(object):
    """
    Compact move list: one ROW per full move (move number + White SAN + Black SAN),
    with separate tappable buttons so White/Black jump work reliably.

    - Tapping White button jumps to white ply for that move (if exists)
    - Tapping Black button jumps to black ply for that move (if exists)
    - Highlights the currently active ply
    """

    def __init__(self, gv: "GameView"):
        self.gv = gv

    # ---------------- internal helpers ----------------
    def _game(self):
        s = getattr(self.gv, "scene", None)
        if s is None or not getattr(s, "ready", False):
            return None
        return s.game

    def _num_rows(self, moves_len: int) -> int:
        return (moves_len + 1) // 2  # 2 plies per full move

    def _ply_exists(self, moves_len: int, ply_1based: int) -> bool:
        return 1 <= ply_1based <= moves_len
    
    def _strip_move_prefix(self, san: str) -> str:
        s = (san or "").strip()
        if not s:
            return s
    
        # Remove leading "12." or "12..." if present
        i = 0
        n = len(s)
    
        # digits
        while i < n and s[i].isdigit():
            i += 1
        if i == 0:
            return s  # no leading digits
    
        # dot(s)
        if i < n and s[i] == ".":
            i += 1
            if i < n and s[i] == ".":
                i += 1
                if i < n and s[i] == ".":
                    i += 1
    
            # optional space after the prefix
            while i < n and s[i] == " ":
                i += 1
    
            return s[i:].strip()
    
        return s

    # ---------------- cell building ----------------
    def _ensure_subviews(self, cell: ui.TableViewCell):
        cv = cell.content_view
        if getattr(cell, "_ml_created", False):
            return cell._ml_no, cell._ml_wbtn, cell._ml_bbtn

        # Move number label
        lbl_no = ui.Label()
        lbl_no.font = ("<System-Mono>", 13)
        lbl_no.text_color = "#333"
        lbl_no.alignment = ui.ALIGN_RIGHT

        # White move button
        wbtn = ui.Button()
        wbtn.font = ("<System>", 13)
        wbtn.tint_color = "#222"
        wbtn.background_color = (0, 0, 0, 0)
        wbtn.corner_radius = 6
        wbtn.action = self._on_tap_white

        # Black move button
        bbtn = ui.Button()
        bbtn.font = ("<System>", 13)
        bbtn.tint_color = "#222"
        bbtn.background_color = (0, 0, 0, 0)
        bbtn.corner_radius = 6
        bbtn.action = self._on_tap_black

        cv.add_subview(lbl_no)
        cv.add_subview(wbtn)
        cv.add_subview(bbtn)

        cell._ml_created = True
        cell._ml_no = lbl_no
        cell._ml_wbtn = wbtn
        cell._ml_bbtn = bbtn

        return lbl_no, wbtn, bbtn

    def _layout_subviews(self, tv: ui.TableView, cell: ui.TableViewCell):
        lbl_no, wbtn, bbtn = self._ensure_subviews(cell)

        row_h = tv.row_height or 34
        total_w = tv.width or self.gv.moves_tv.width

        pad_x = 8
        no_w = 44
        gap = 10
        col_w = max(0, (total_w - pad_x * 2 - no_w - gap) / 2.0)

        lbl_no.frame = (pad_x, 0, no_w, row_h)
        wbtn.frame = (pad_x + no_w + gap, 2, col_w - 4, row_h - 4)
        bbtn.frame = (pad_x + no_w + gap + col_w, 2, col_w - 4, row_h - 4)

    # ---------------- jump actions ----------------
    def _enter_review(self):
        try:
            self.gv._enter_review_mode()
        except Exception:
            pass

    def _jump_to_ply(self, ply_1based: int):
        self._enter_review()
        self.gv.scene.jump_to_ply(ply_1based)
        self.gv._update_review_controls()
        self.gv._update_toolbar_enabled()

    def _on_tap_white(self, sender):
        ply = int(getattr(sender, "ply", 0) or 0)
        if ply > 0:
            self._jump_to_ply(ply)

    def _on_tap_black(self, sender):
        ply = int(getattr(sender, "ply", 0) or 0)
        if ply > 0:
            self._jump_to_ply(ply)

    # ---------------- datasource ----------------
    def tableview_number_of_rows(self, tv, section):
        g = self._game()
        moves = g.san_move_list() if g else []
        return self._num_rows(len(moves))

    def tableview_cell_for_row(self, tv, section, row):
        cell = ui.TableViewCell()
        cell.background_color = "#f2f2f2"
        cell.content_view.background_color = "#f2f2f2"

        # IMPORTANT: hide the default built-in label so we don't get "double text"
        cell.text_label.text = ""
        if cell.detail_text_label is not None:
            cell.detail_text_label.text = ""
    
        self._layout_subviews(tv, cell)
        lbl_no, wbtn, bbtn = cell._ml_no, cell._ml_wbtn, cell._ml_bbtn

        g = self._game()
        if not g:
            lbl_no.text = ""
            wbtn.title = ""
            bbtn.title = ""
            wbtn.enabled = False
            bbtn.enabled = False
            return cell

        moves = g.san_move_list()
        n = len(moves)

        # indices into ply list
        wi = row * 2       # 0-based ply index for White
        bi = wi + 1        # 0-based ply index for Black

        # move number display
        lbl_no.text = f"{row + 1}."

        w_san = self._strip_move_prefix(moves[wi]) if wi < n else ""
        b_san = self._strip_move_prefix(moves[bi]) if bi < n else ""

        # 1-based ply numbers for jumping
        w_ply = wi + 1
        b_ply = bi + 1

        wbtn.title = w_san
        bbtn.title = b_san

        wbtn.ply = w_ply if self._ply_exists(n, w_ply) else 0
        bbtn.ply = b_ply if self._ply_exists(n, b_ply) else 0

        wbtn.enabled = bool(wbtn.ply)
        bbtn.enabled = bool(bbtn.ply)

        # highlight active ply
        cur_ply = g.current_ply()          # position after cur_ply plies
        active_idx = cur_ply - 1           # last played move index in moves list (0-based), -1 if none

        # reset
        wbtn.background_color = (0, 0, 0, 0)
        bbtn.background_color = (0, 0, 0, 0)

        if active_idx == wi:
            wbtn.background_color = (0.85, 0.92, 1.0)
        elif active_idx == bi:
            bbtn.background_color = (0.85, 0.92, 1.0)

        return cell

    # ---------------- delegate ----------------
    def tableview_did_select(self, tv, section, row):
        # Row tap doesn't know x position; do nothing to avoid wrong jumps.
        # User taps White/Black button explicitly.
        tv.selected_row = (-1, -1)

# ============================================================
# Import View
# ============================================================
class ImportView(ui.View):
    def __init__(self, on_load=None):
        super().__init__()
        self.name = "Import PGN / FEN"
        self.background_color = "white"
        self.on_load = on_load

        self.top_bar = ui.View()
        self.top_bar.background_color = "#f2f2f2"
        self.add_subview(self.top_bar)

        self.btn_cancel = ui.Button(title="Cancel")
        self.btn_cancel.action = self._on_cancel
        self.top_bar.add_subview(self.btn_cancel)

        self.btn_load = ui.Button(title="Load")
        self.btn_load.action = self._on_load
        self.btn_load.tint_color = (0.2, 0.55, 1.0)
        self.top_bar.add_subview(self.btn_load)

        self.lbl = ui.Label(text="Paste PGN or FEN below:")
        self.lbl.font = ("<System>", 15)
        self.lbl.text_color = "#333"
        self.add_subview(self.lbl)

        self.text_box = ui.View()
        self.text_box.background_color = "#f0f0f0"
        self.text_box.corner_radius = 8
        self.add_subview(self.text_box)

        self.text_view = ui.TextView()
        self.text_view.font = ("<System>", 14)
        self.text_view.background_color = "#f0f0f0"
        self.text_view.autocapitalization_type = ui.AUTOCAPITALIZE_NONE
        self.text_view.autocorrection_type = False
        self.text_view.spellchecking_type = False
        self.text_box.add_subview(self.text_view)

    def layout(self):
        w, h = self.width, self.height
        top_h = 44
        pad = 16

        self.top_bar.frame = (0, 0, w, top_h)
        self.btn_cancel.frame = (pad, 0, 90, top_h)
        self.btn_load.frame = (w - pad - 90, 0, 90, top_h)

        y = top_h + 16
        self.lbl.frame = (pad, y, w - 2 * pad, 20)

        y += 28
        box_h = int(h * 0.33)
        self.text_box.frame = (pad, y, w - 2 * pad, box_h)

        inner_pad = 8
        self.text_view.frame = (
            inner_pad,
            inner_pad,
            self.text_box.width - 2 * inner_pad,
            self.text_box.height - 2 * inner_pad,
        )

    def touch_began(self, touch):
        self.text_view.end_editing()

    def _on_load(self, sender):
        self.text_view.end_editing()
        text = (self.text_view.text or "").strip()
        if callable(self.on_load):
            self.on_load(text)
        self.close()

    def _on_cancel(self, sender):
        self.text_view.end_editing()
        self.close()


# ============================================================
# Game View
# ============================================================
class GameView(ui.View):
    def __init__(self):
        super().__init__()
        self.name = "Chess Practice App"
        self.background_color = "white"

        # Top bar (toolbar)
        self.bar = ui.View(frame=(0, 0, 0, BAR_HEIGHT))
        self.bar.flex = "W"
        self.bar.background_color = "#f2f2f2"
        self.add_subview(self.bar)
        
        # Bottom bar
        self.bottom_bar = ui.View()
        self.bottom_bar.background_color = "#f2f2f2"
        self.bottom_bar.flex = "WT"
        self.add_subview(self.bottom_bar)
                
        # Bottom bar: moves list
        self.moves_tv = ui.TableView()
        self.moves_tv.background_color = "#f2f2f2"
        self.moves_tv.row_height = 34
        self.moves_tv.separator_color = (0, 0, 0, 0.12)

        self._moves_ds = _MovesListDataSource(self)
        self.moves_tv.data_source = self._moves_ds
        self.moves_tv.delegate = self._moves_ds

        self.bottom_bar.add_subview(self.moves_tv)

        # --- Bottom bar review controls ---
        self.btn_moves_done  = self._add_icon_btn(self.bottom_bar, "iob:close_32", self._on_moves_done, "Cancel review", enabled=False)
        self.btn_moves_fork  = self._add_icon_btn(self.bottom_bar, "iob:play_32",  self._on_moves_fork, "Play from here", enabled=False)
        
        self.btn_review_back  = self._add_icon_btn(self.bottom_bar, "iob:ios7_rewind_32",       self._on_review_back, "Back (review)", enabled=False)
        self.btn_review_fwd   = self._add_icon_btn(self.bottom_bar, "iob:ios7_fastforward_32",  self._on_review_forward, "Forward (review)", enabled=False)
        
        self.btn_review_begin = self._add_icon_btn(self.bottom_bar, "iob:ios7_skipbackward_32", self._on_review_begin, "Beginning (review)", enabled=False)
        self.btn_review_end   = self._add_icon_btn(self.bottom_bar, "iob:ios7_skipforward_32",  self._on_review_end, "End (review)", enabled=False)
        
        # --- Top bar toolbar buttons ---
        self.btn_undo     = self._add_icon_btn(self.bar, "iob:ios7_undo_32", self._on_undo,     "Undo", enabled=False)
        self.btn_redo     = self._add_icon_btn(self.bar, "iob:ios7_redo_32", self._on_redo,     "Redo", enabled=False)
        self.btn_reset    = self._add_icon_btn(self.bar, "iob:ios7_trash_32", self._on_reset,    "Reset", enabled=True)
        self.btn_flip     = self._add_icon_btn(self.bar, "iob:arrow_swap_32", self._on_flip,     "Flip Board", enabled=True)
        self.btn_import   = self._add_icon_btn(self.bar, "iob:ios7_download_32", self._on_import,   "Import PGN or FEN", enabled=True)
        self.btn_export   = self._add_icon_btn(self.bar, "iob:share_32",         self._on_export, "Export PGN or FEN", enabled=True)
        self.btn_settings = self._add_icon_btn(self.bar, "iob:ios7_gear_32", self._on_settings, "Settings", enabled=True)

        # Scene view
        self.scene = ChessScene()
        self.scene_view = SceneView(frame=(0, BAR_HEIGHT, 0, 0))
        self.scene_view.scene = self.scene
        self.scene_view.flex = "WH"
        self.add_subview(self.scene_view)

        self.scene.on_ui_state_change = self._update_toolbar_enabled

        # Always start toolbar in a safe disabled state; scene will notify when ready
        self._update_review_controls()
        self._update_toolbar_enabled()
        self._refresh_moves_list()

    # ---- lifecycle ----
    def will_close(self):
        try:
            self.scene.stop()
        except Exception:
            pass
    
    # ---- helpers ----
    def _scene_ready_game(self):
        s = self.scene
        if not getattr(s, "ready", False):
            return None
        return s.game

    def _add_icon_btn(self, parent_view, icon_name, action, label, *, enabled=True):
        b = ui.Button()
        b.image = ui.Image.named(icon_name)
        b.tint_color = "#333"
        b.action = action
        b.accessibility_label = label
        parent_view.add_subview(b)
        self._set_enabled(b, enabled)
        return b
    
    def layout(self):
        self.bar.frame = (0, 0, self.width, BAR_HEIGHT)
        self.bottom_bar.frame = (0, self.height - BOTTOM_BAR_HEIGHT, self.width, BOTTOM_BAR_HEIGHT)
        
        # SceneView gets sandwiched
        self.scene_view.frame = (
            0,
            BAR_HEIGHT,
            self.width,
            self.height - BAR_HEIGHT - BOTTOM_BAR_HEIGHT
        )

        y = (BAR_HEIGHT - ICON_SIZE) / 2
        gap = 28

        # Left group: Undo, Redo, Reset, Flip
        left_x = ICON_PADDING_X
        self.btn_undo.frame = (left_x, y, ICON_SIZE, ICON_SIZE)
        left_x += ICON_SIZE + gap
        self.btn_redo.frame = (left_x, y, ICON_SIZE, ICON_SIZE)
        left_x += ICON_SIZE + gap
        self.btn_reset.frame = (left_x, y, ICON_SIZE, ICON_SIZE)
        left_x += ICON_SIZE + gap
        self.btn_flip.frame = (left_x, y, ICON_SIZE, ICON_SIZE)

        # Right group: Export, Import, Settings
        right_x = self.width - ICON_PADDING_X - ICON_SIZE
        self.btn_settings.frame = (right_x, y, ICON_SIZE, ICON_SIZE)
        right_x -= ICON_SIZE + gap
        self.btn_import.frame = (right_x, y, ICON_SIZE, ICON_SIZE)
        right_x -= ICON_SIZE + gap
        self.btn_export.frame = (right_x, y, ICON_SIZE, ICON_SIZE)
        
        # Bottom bar layout: Cancel and Fork buttons + list
        # Bottom bar layout: moves list + 2-col controls strip (3 rows)
        pad = 10
        btn_h = 40
        row_gap = 8
        col_gap = 8
        col_w = 44
        strip_w = pad + col_w + col_gap + col_w + pad

        # Moves list gets the remaining width
        self.moves_tv.frame = (0, 0, self.bottom_bar.width - strip_w, self.bottom_bar.height)

        # Control strip origin (top-left)
        sx = self.moves_tv.width + pad
        sy = 0

        # Row 1: Cancel | Fork
        self.btn_moves_done.frame = (sx, sy, col_w, btn_h)
        self.btn_moves_fork.frame = (sx + col_w + col_gap, sy, col_w, btn_h)

        # Row 2: Back | Forward
        sy2 = sy + btn_h + row_gap
        self.btn_review_back.frame = (sx, sy2, col_w, btn_h)
        self.btn_review_fwd.frame  = (sx + col_w + col_gap, sy2, col_w, btn_h)

        # Row 3: Begin | End
        sy3 = sy2 + btn_h + row_gap
        self.btn_review_begin.frame = (sx, sy3, col_w, btn_h)
        self.btn_review_end.frame   = (sx + col_w + col_gap, sy3, col_w, btn_h)
        
    def _set_enabled(self, button: ui.Button, enabled: bool):
        button.enabled = bool(enabled)
        button.alpha = 1.0 if enabled else 0.35
    
    def _refresh_moves_list(self):
        if not getattr(self.scene, "ready", False):
            return
        self.moves_tv.reload()

    def _update_toolbar_enabled(self):
        g = self._scene_ready_game()

        if g is None:
            # Pre-setup: disable anything that depends on move history
            self._set_enabled(self.btn_undo, False)
            self._set_enabled(self.btn_redo, False)
            return

        # While reviewing history, freeze undo/redo to avoid confusing interactions
        if self.scene.review_mode:
            self._set_enabled(self.btn_undo, False)
            self._set_enabled(self.btn_redo, False)
        else:
            self._set_enabled(self.btn_undo, g.can_undo())
            self._set_enabled(self.btn_redo, g.can_redo())
                
        self._refresh_moves_list()

    # --------------------------------------------------------
    # Move list / review mode
    # --------------------------------------------------------
    def _update_review_controls(self):
        """
        Review controls policy:
          - All review buttons are only enabled while scene.review_mode is True
          - Within review mode:
              * Back/Begin enabled if we are not already at ply 0
              * Fwd/End enabled if we are not already at the end (total_ply)
          - Cancel/Fork are enabled any time we're in review mode
        """
        in_review = self._review_nav_enabled()
    
        # All review controls (Cancel/Fork + nav)
        review_buttons = (
            self.btn_moves_done,
            self.btn_moves_fork,
            self.btn_review_back,
            self.btn_review_fwd,
            self.btn_review_begin,
            self.btn_review_end,
        )
    
        if not in_review:
            for b in review_buttons:
                self._set_enabled(b, False)
            return
    
        # In review mode: base enable
        for b in review_buttons:
            self._set_enabled(b, True)
    
        # Now refine nav enable based on where we are in the line
        g = self.scene.game
        cur = int(g.current_ply())
        end = int(g.total_ply())
    
        can_back = (cur > 0)
        can_fwd  = (cur < end)
    
        self._set_enabled(self.btn_review_back,  can_back)
        self._set_enabled(self.btn_review_begin, can_back)
        self._set_enabled(self.btn_review_fwd, can_fwd)
        self._set_enabled(self.btn_review_end, can_fwd)
        
    def _enter_review_mode(self):
        if not self.scene.ready:
            return
        self.scene.begin_review_mode()
        self._update_review_controls()
        self._update_toolbar_enabled()
    
    def _exit_review_mode(self):
        if not self.scene.ready:
            return
        self.scene.end_review_mode()
        self._update_review_controls()
        self._update_toolbar_enabled()
    
    def _fork_review_mode(self):
        if not self.scene.ready:
            return
        self.scene.fork_review_mode()
        self._update_review_controls()
        self._update_toolbar_enabled()
    
    def _on_moves_done(self, sender):
        self._exit_review_mode()
        
    def _on_moves_fork(self, sender):
        self._fork_review_mode()

    def _review_nav_enabled(self):
        return bool(getattr(self.scene, "ready", False) and self.scene.review_mode)

    def _on_review_back(self, sender):
        if not self._review_nav_enabled():
            return
        g = self.scene.game
        cur = g.current_ply()
        self.scene.jump_to_ply(max(0, cur - 1))
        self._update_review_controls()
        self._update_toolbar_enabled()

    def _on_review_forward(self, sender):
        if not self._review_nav_enabled():
            return
        g = self.scene.game
        cur = g.current_ply()
        end = g.total_ply()
        self.scene.jump_to_ply(min(end, cur + 1))
        self._update_review_controls()
        self._update_toolbar_enabled()

    def _on_review_begin(self, sender):
        if not self._review_nav_enabled():
            return
        self.scene.jump_to_ply(0)
        self._update_review_controls()
        self._update_toolbar_enabled()

    def _on_review_end(self, sender):
        if not self._review_nav_enabled():
            return
        g = self.scene.game
        self.scene.jump_to_ply(g.total_ply())
        self._update_review_controls()
        self._update_toolbar_enabled()
        
    # --------------------------------------------------------
    # Toolbar actions
    # --------------------------------------------------------
    def _on_undo(self, sender):
        if self._scene_ready_game() is None:
            return
        self.scene.undo()

    def _on_redo(self, sender):
        if self._scene_ready_game() is None:
            return
        self.scene.redo()

    def _on_reset(self, sender):
        if self._scene_ready_game() is None:
            return
        r = console.alert(
            "Reset game?",
            "This will clear the board.",
            "Reset",
            "Cancel",
            hide_cancel_button=True,
        )
        if r != 1:
            return
        self.scene.reset()

    def _on_flip(self, sender):
        if self._scene_ready_game() is None:
            return
        self.scene.flip_board()

    def _on_import(self, sender):
        if self._scene_ready_game() is None:
            return

        def do_import(text: str):
            ok, msg = self.scene.import_text(text)
            if not ok:
                console.alert("Import failed", msg, "OK")

        ImportView(on_load=do_import).present("sheet")

    def _on_export(self, sender):
        if self._scene_ready_game() is None:
            return
        ExportView(get_text_fn=self.scene.export_text).present("sheet")

    def _on_settings(self, sender):
        g = self._scene_ready_game()
        if g is None:
            return

        can_change_opening = g.board_is_fresh()

        def apply_settings(vs_ai, ai_color, level, opening_choice, practice_tier, show_sugg_arrows, cloud_eval):
            self.scene.apply_settings(
                vs_ai=vs_ai,
                ai_color=ai_color,
                ai_level=level,
                opening_choice=opening_choice,
                practice_tier=practice_tier,
                show_sugg_arrows=show_sugg_arrows,
                cloud_eval=cloud_eval,
            )

        SettingsView(
            initial_vs_ai=g.vs_ai,
            initial_ai_color=g.ai_color,
            initial_level=g.ai_level,
            initial_opening_choice=g.opening_choice,
            initial_practice_tier=g.practice_tier,
            can_change_opening=can_change_opening,
            initial_show_sugg_arrows=g.show_sugg_arrows,
            initial_cloud_eval=g.cloud_eval_enabled,
            on_done=apply_settings,
        ).present("sheet")


# ============================================================
# Export View
# ============================================================
class ExportView(ui.View):
    def __init__(self, *, get_text_fn, on_close=None):
        super().__init__()
        self.name = "Export"
        self.background_color = "white"
        self._get_text_fn = get_text_fn
        self._on_close = on_close

        self.btn_copy = ui.Button(title="Copy")
        self.btn_copy.action = self._on_copy

        self.btn_close = ui.Button(title="Close")
        self.btn_close.action = self._on_close_tapped

        self.seg_mode = ui.SegmentedControl()
        self.seg_mode.segments = ["FEN", "PGN"]
        self.seg_mode.selected_index = 0
        self.seg_mode.action = self._refresh

        self.text = ui.TextView()
        self.text.editable = False
        self.text.background_color = (0.95, 0.95, 0.95)
        self.text.font = ("<System-Mono>", 13)

        for v in (self.btn_copy, self.btn_close, self.seg_mode, self.text):
            self.add_subview(v)

        self._refresh(None)

    def layout(self):
        w, h = self.width, self.height
        pad = 12
        top = 10
        btn_w = 80
        btn_h = 34

        self.btn_close.frame = (pad, top, btn_w, btn_h)
        self.btn_copy.frame = (w - pad - btn_w, top, btn_w, btn_h)

        self.seg_mode.frame = (pad, top + btn_h + 8, w - 2 * pad, 32)

        y = top + btn_h + 8 + 32 + 10
        self.text.frame = (pad, y, w - 2 * pad, h - y - pad)

    def _current_mode(self) -> str:
        return "fen" if self.seg_mode.selected_index == 0 else "pgn"

    def _refresh(self, sender):
        mode = self._current_mode()
        self.text.text = (self._get_text_fn(mode) or "").strip()

    def _on_copy(self, sender):
        t = (self.text.text or "").strip()
        if t:
            clipboard.set(t)

    def _on_close_tapped(self, sender):
        if callable(self._on_close):
            self._on_close()
        self.close()
