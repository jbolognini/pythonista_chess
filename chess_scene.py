# chess_scene.py
import math
import traceback
import ui
import chess
from scene import Scene, ShapeNode

from chess_game import ChessGame
from chess_ui import BoardRenderer, HudView, PromotionOverlay, EvalBarView
from engine_service import EngineService

from sunfish_engine import SunfishEngine
from lichess_engine import LichessCloudEngine


REVIEW_OVERLAY_ALPHA = 0.20

# Eval normalization (print now; later drives eval bar animation)
EVAL_TANH_SCALE_CP = 400.0   # bigger = bar moves less
EVAL_CLAMP_CP = 2000         # clamp to avoid insane swings


class ChessScene(Scene):
    """
    Scene orchestrates:
      - UI/rendering
      - Cloud request lifecycle (network)
      - Local engine service jobs (AI + eval)
      - Review mode policy

    Key rules:
      - Local eval is requested after ANY position change (moves + navigation + review).
      - AI takes priority over eval (EngineService enforces this).
      - Stale protection uses (gen, fen) checks.
    """

    def __init__(self):
        super().__init__()

        # Core game state
        self.game = ChessGame()
        self.ready = False

        # UI callback (optional)
        self.on_ui_state_change = None

        # Engines
        self.engine_service: EngineService | None = None
        self._cloud_engine: LichessCloudEngine | None = None

        # HUD state
        self._ai_thinking = False

        # Eval bar state (future)
        self.eval_white_cp = None
        self.eval_norm = None

        # Local engine generations (stale protection)
        self._ai_gen = 0
        self._eval_gen = 0

        # Cloud state
        self._cloud_generation = 0
        self._cloud_last_fen = None
        self._cloud_inflight = False

        # Review mode
        self.review_mode = False
        self._review_entry_ply = None
        self._review_entry_selected = None

    # --------------------------------------------------
    # Scene lifecycle
    # --------------------------------------------------
    def setup(self):
        # ----- Engines -----
        self._cloud_engine = LichessCloudEngine()

        self.engine_service = EngineService(
            engine_factory=SunfishEngine,
            on_ai_result=self._on_ai_result,
            on_eval_result=self._on_eval_result,
            name="LocalEngine",
        )
        self.engine_service.start()

        # ----- Rendering -----
        self.board_view = BoardRenderer(self)
        self.hud = HudView(self, z=200)
        self.promo = PromotionOverlay(self, z=210)
        self.eval_bar = EvalBarView(self, z=140)

        # ----- Selection / promotion -----
        self.selected = None
        self._promo_active = False
        self._promo_from = None
        self._promo_to = None

        # ----- Review overlay -----
        self._review_overlay = ShapeNode()
        self._review_overlay.z_position = 150
        self._review_overlay.alpha = 0.0
        self._review_overlay.fill_color = (0, 0, 0)
        self._review_overlay.stroke_color = (0, 0, 0)
        self._review_overlay.line_width = 0
        self._review_overlay.anchor_point = (0, 0)  # bottom-left anchor
        self.add_child(self._review_overlay)

        # Initial draw + initial analysis
        self.ready = True
        self.redraw_all()
        self._on_position_changed(reason="initial", allow_ai=True)

    def stop(self):
        """Call when the scene/view is being dismissed to stop background work."""
        if self.engine_service:
            try:
                self.engine_service.stop()
            finally:
                self.engine_service = None

        self._cloud_generation += 1
        self._cloud_inflight = False
        self._cloud_last_fen = None

        self._ai_thinking = False

    # --------------------------------------------------
    # Layout / drawing
    # --------------------------------------------------
    def did_change_size(self):
        if not self.ready:
            return
        self.redraw_all()
    
    def update(self, dt=None):
        if not dt:
            dt = 1.0 / 60.0
        self.eval_bar.step(dt)
    
    def redraw_all(self):
        self.board_view.compute_geometry()
        self.board_view.draw_squares()
        self.board_view.sync_pieces(self.game.board)
        self.eval_bar.layout_from_board(self.board_view, margin=10, width=14)
        self.board_view.refresh_overlays(self.game.board, self.selected)

        # Review overlay geometry
        s = self.board_view.square_size
        ox, oy = self.board_view.origin
        self._review_overlay.position = (ox, oy)
        self._review_overlay.path = ui.Path.rect(0, 0, 8 * s, 8 * s)
        self._review_overlay.alpha = REVIEW_OVERLAY_ALPHA if self.review_mode else 0.0

        self.hud.layout()
        self.refresh_hud()

    def flip_board(self):
        if not self.ready:
            return
        self.board_view.toggle_flipped()
        self.redraw_all()

    def refresh_hud(self):
        self.hud.update(
            game=self.game,
            ai_thinking=self._ai_thinking,
            promo_active=self._promo_active,
        )
        self._notify_ui()

    def _notify_ui(self):
        cb = self.on_ui_state_change
        if callable(cb):
            cb()

    # -----------------------------------------------
    # Centralized position change hook
    # -----------------------------------------------
    def _on_position_changed(self, *, reason: str = "", allow_ai: bool = True):
        """
        Call after ANY board change:
          - move commit (human/AI)
          - undo/redo
          - jump_to_ply
          - import/reset
          - review navigation

        Policy:
          - Always request local eval (including review mode)
          - Cloud eval only when enabled and not in review mode
          - AI only when allowed and not in review mode
        """
        # Invalidate in-flight local work (ignore stale results)
        self._ai_gen += 1
        self._eval_gen += 1
        self._ai_thinking = False

        # Clear selection/promo UI
        self.selected = None
        self._clear_promotion_ui()

        # Sync board visuals
        self.board_view.sync_pieces(self.game.board)
        self.board_view.refresh_overlays(self.game.board, self.selected)

        # Cloud lifecycle
        self._clear_cloud_eval()
        self._queue_cloud_eval()

        # Always request local eval (non-blocking)
        self._request_engine_eval()

        # AI (optional)
        if allow_ai and not self.review_mode:
            self._schedule_ai_if_needed()

        self.refresh_hud()

    # --------------------------------------------------
    # Settings
    # --------------------------------------------------
    def apply_settings(
        self,
        *,
        vs_ai,
        ai_color,
        ai_level,
        opening_choice,
        practice_tier,
        show_sugg_arrows,
        cloud_eval,
    ):
        if not self.ready:
            return

        self.game.set_ai_settings(vs_ai=vs_ai, ai_color=ai_color, ai_level=ai_level)
        self.board_view.set_flipped(vs_ai and ai_color == chess.WHITE)

        self.game.set_opening(opening_choice)
        self.game.set_practice_tier(practice_tier)
        self.game.set_show_sugg_arrows(show_sugg_arrows)
        self.game.set_cloud_eval(cloud_eval)

        self.redraw_all()
        self._on_position_changed(reason="settings", allow_ai=True)

    # --------------------------------------------------
    # Local eval (EngineService)
    # --------------------------------------------------
    def _request_engine_eval(self):
        if not self.engine_service:
            return
    
        fen = self.game.board.fen()
        level = int(self.game.ai_level)
        gen = int(self._eval_gen)
    
        self.game.clear_eval(pending=True)
        self.eval_bar.set_pending(True)
    
        self.engine_service.request_eval(
            fen=fen,
            level=level,
            gen=gen,
        )
        
    def _on_eval_result(self, *, fen: str, white_cp: int, gen: int):
        if int(gen) != int(self._eval_gen):
            return
        if fen != self.game.board.fen():
            return
    
        cp = max(-EVAL_CLAMP_CP, min(EVAL_CLAMP_CP, int(white_cp)))
    
        self.game.set_eval(white_cp=cp, source="engine", fen=fen)
    
        self.eval_bar.set_pending(False)
        self.eval_bar.set_target_from_cp(
            cp,
            tanh_scale_cp=EVAL_TANH_SCALE_CP,
        )
        
    # --------------------------------------------------
    # AI scheduling (EngineService)
    # --------------------------------------------------
    def _schedule_ai_if_needed(self):
        if not self.engine_service:
            return
        if not self.game.vs_ai:
            return

        b = self.game.board
        if b.is_game_over():
            return
        if b.turn != self.game.ai_color:
            return

        self._ai_thinking = True
        self.refresh_hud()

        fen = b.fen()
        level = int(self.game.ai_level)
        gen = int(self._ai_gen)

        try:
            self.engine_service.request_ai(fen=fen, level=level, gen=gen)
        except Exception:
            self._ai_thinking = False
            self.refresh_hud()
            print("[AI]", traceback.format_exc())

    def _on_ai_result(self, *, gen: int, fen: str, move: chess.Move | None, white_cp: int | None = None, **_kw):
        # Clear thinking regardless; then ignore stale
        self._ai_thinking = False

        if self.review_mode:
            self.refresh_hud()
            return
        if int(gen) != int(self._ai_gen):
            self.refresh_hud()
            return
        if fen != self.game.board.fen():
            self.refresh_hud()
            return

        if move and self.game.apply_ai_move(move):
            self._on_position_changed(reason="ai_move", allow_ai=True)
        else:
            self.refresh_hud()

    # -----------------------------------------------
    # Review / history navigation mode
    # -----------------------------------------------
    def begin_review_mode(self):
        if not self.ready or self.review_mode:
            return

        self.review_mode = True
        self._review_overlay.alpha = REVIEW_OVERLAY_ALPHA
        self._review_entry_ply = len(self.game.board.move_stack)
        self._review_entry_selected = self.selected

        # In review mode we still want analysis => eval after this toggle
        self._on_position_changed(reason="begin_review", allow_ai=False)

    def fork_review_mode(self):
        """Exit review mode and resume normal behavior from the current board position."""
        if not self.ready or not self.review_mode:
            return

        self.review_mode = False
        self._review_overlay.alpha = 0.0

        self._on_position_changed(reason="fork_review", allow_ai=True)

    def end_review_mode(self):
        """Cancel review: revert to entry position and resume normal behavior."""
        if not self.ready or not self.review_mode:
            return

        entry = self._review_entry_ply
        sel = self._review_entry_selected
        self._review_entry_ply = None
        self._review_entry_selected = None

        self.review_mode = False
        self._review_overlay.alpha = 0.0

        if entry is not None:
            self.game.jump_to_ply(int(entry))

        # optional selection restore
        self.selected = sel if entry is not None else None
        self.board_view.refresh_overlays(self.game.board, self.selected)

        self._on_position_changed(reason="end_review", allow_ai=True)

    # -----------------------------------------------
    # Cloud eval
    # -----------------------------------------------
    def _queue_cloud_eval(self):
        if self.game.practice_phase == "READY":
            return
        if not self.game.cloud_eval_enabled:
            return
        if self.review_mode:
            return

        fen = self.game.board.fen()
        if fen == self._cloud_last_fen or self._cloud_inflight:
            return

        self._cloud_last_fen = fen
        self._cloud_inflight = True
        gen = self._cloud_generation
        self._cloud_eval_background(fen, gen)

    @ui.in_background
    def _cloud_eval_background(self, fen, gen):
        # If cloud got turned off after we queued, unwind cleanly
        if not self.game.cloud_eval_enabled:
            def apply_disabled():
                if gen != self._cloud_generation:
                    return
                self._cloud_inflight = False
                self.game.cloud_eval_pending = False
                self.game.suggested_moves = (
                    self.game.compute_suggest_moves(max_moves=2)
                    if self.game.show_sugg_arrows
                    else []
                )
                self.board_view.refresh_overlays(self.game.board, self.selected)
                self.refresh_hud()

            ui.delay(apply_disabled, 0)
            return

        result = None
        try:
            if self._cloud_engine is None:
                raise RuntimeError("Cloud engine missing (setup not run?)")
            result = self._cloud_engine.eval(fen, multipv=3)
        except Exception:
            result = None

        def apply():
            if gen != self._cloud_generation:
                self._cloud_inflight = False
                self._queue_cloud_eval()
                return

            self._cloud_inflight = False
            self.game.cloud_eval = result
            self.game.cloud_eval_pending = False
            self.game.suggested_moves = self.game.compute_suggest_moves(max_moves=2)
            self.board_view.refresh_overlays(self.game.board, self.selected)
            self.refresh_hud()

        ui.delay(apply, 0)

    def _clear_cloud_eval(self):
        """
        Central policy:
          - Practice READY: no cloud work
          - Cloud disabled: book suggestions (if arrows enabled)
          - Cloud enabled: mark pending and clear arrows until result arrives
        """
        if self.game.practice_phase == "READY":
            return

        self._cloud_generation += 1
        self._cloud_last_fen = None
        self.game.cloud_eval = None

        if not self.game.cloud_eval_enabled:
            self.game.cloud_eval_pending = False
            self.game.suggested_moves = (
                self.game.compute_suggest_moves(max_moves=2)
                if self.game.show_sugg_arrows
                else []
            )
            self.board_view.refresh_overlays(self.game.board, self.selected)
            return

        self.game.cloud_eval_pending = True
        self.game.suggested_moves = []

    # --------------------------------------------------
    # Game lifecycle
    # --------------------------------------------------
    def reset(self):
        if not self.ready:
            return
        self.game.reset()
        self._on_position_changed(reason="reset", allow_ai=True)

    def undo(self):
        if not self.ready:
            return
        if not self.game.can_undo():
            return
        self.game.undo_plies(2 if self.game.vs_ai else 1)
        self._on_position_changed(reason="undo", allow_ai=True)

    def redo(self):
        if not self.ready:
            return
        if not self.game.can_redo():
            return
        self.game.redo_plies(2 if self.game.vs_ai else 1)
        self._on_position_changed(reason="redo", allow_ai=True)

    def jump_to_ply(self, ply_index: int):
        if not self.ready:
            return False
        ok = self.game.jump_to_ply(ply_index)
        if not ok:
            self._on_position_changed(reason="jump_fail", allow_ai=False)
            return False
        self._on_position_changed(reason="jump", allow_ai=True)
        return True

    # --------------------------------------------------
    # Promotion
    # --------------------------------------------------
    def _clear_promotion_ui(self):
        self._promo_active = False
        self._promo_from = None
        self._promo_to = None
        self.promo.clear()
        self.hud.set_row1_override(None)

    def _show_promotion_ui(self, from_sq, to_sq, pieces):
        self._promo_active = True
        self._promo_from = from_sq
        self._promo_to = to_sq
        self.hud.set_row1_override("Choose promotion")
        self.refresh_hud()
        self.promo.show(from_sq, to_sq, pieces)

    def _on_promotion_choice(self, piece_type):
        if not self._promo_active or self._promo_from is None or self._promo_to is None:
            return
        mv = chess.Move(self._promo_from, self._promo_to, promotion=piece_type)
        self._clear_promotion_ui()
        if self.game.make_human_move(mv):
            self._on_position_changed(reason="promotion", allow_ai=True)

    # --------------------------------------------------
    # Input
    # --------------------------------------------------
    def touch_ended(self, touch):
        if not self.ready:
            return

        if self._promo_active:
            self.promo.handle_touch(touch.location)
            return

        sq = self.board_view.pos_to_square(*touch.location)
        if sq is None:
            return

        # Review mode: allow selection/exploration, but DO NOT commit moves.
        if self.review_mode:
            if self.selected is None:
                piece = self.game.board.piece_at(sq)
                if piece and piece.color == self.game.board.turn:
                    self.selected = sq
                self.board_view.refresh_overlays(self.game.board, self.selected)
                self.refresh_hud()
                return

            if sq == self.selected:
                self.selected = None
                self.board_view.refresh_overlays(self.game.board, self.selected)
                self.refresh_hud()
                return

            piece2 = self.game.board.piece_at(sq)
            if piece2 and piece2.color == self.game.board.turn:
                self.selected = sq
                self.board_view.refresh_overlays(self.game.board, self.selected)
                self.refresh_hud()
                return

            self.selected = None
            self.board_view.refresh_overlays(self.game.board, self.selected)
            self.refresh_hud()
            return

        # Normal play mode
        if self.selected is None:
            piece = self.game.board.piece_at(sq)
            if piece and piece.color == self.game.board.turn:
                self.selected = sq
                self.board_view.refresh_overlays(self.game.board, self.selected)
                self.refresh_hud()
            return

        if sq == self.selected:
            self.selected = None
            self.board_view.refresh_overlays(self.game.board, self.selected)
            self.refresh_hud()
            return

        promo = self.game.legal_promotion_pieces(self.selected, sq)
        if promo:
            self._show_promotion_ui(self.selected, sq, promo)
            return

        mv = chess.Move(self.selected, sq)
        if self.game.make_human_move(mv):
            self._on_position_changed(reason="human_move", allow_ai=True)
            return

        piece2 = self.game.board.piece_at(sq)
        self.selected = sq if piece2 and piece2.color == self.game.board.turn else None
        self.board_view.refresh_overlays(self.game.board, self.selected)
        self.refresh_hud()

    # --------------------------------------------------
    # Import / Export
    # --------------------------------------------------
    def import_text(self, text):
        ok, msg = self.game.import_pgn_or_fen(text)
        if not ok:
            return False, msg

        # Import forces vs_ai off (UI convenience)
        self.game.set_ai_settings(
            vs_ai=False,
            ai_color=self.game.ai_color,
            ai_level=self.game.ai_level,
        )

        self._on_position_changed(reason="import", allow_ai=False)
        return True, msg

    def export_text(self, mode):
        return self.game.export_pgn() if mode == "pgn" else self.game.export_fen()
