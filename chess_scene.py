# chess_scene.py
import threading
import time
import traceback
import math

import chess
import ui
from scene import Scene, ShapeNode

from chess_game import ChessGame
from chess_ui import BoardRenderer, HudView, PromotionOverlay
from lichess_engine import LichessCloudEngine
from sunfish_engine import SunfishEngine

REVIEW_OVERLAY_ALPHA = 0.20
EVAL_TANH_SCALE_CP = 400.0 # bigger = bar moves less; smaller = confirms faster
EVAL_CLAMP_CP = 2000 # clamp to avoid insane swings

class ChessScene(Scene):
    def __init__(self):
        super().__init__()
        # Always-present core state (prevents AttributeError races)
        self.game = ChessGame()

        # Scene lifecycle flags
        self.ready = False

        # UI callbacks (set by host view)
        self.on_ui_state_change = None

        # Worker controls (initialized in setup)
        self._ai_worker_running = False

    # --------------------------------------------------
    # Scene lifecycle
    # --------------------------------------------------
    def setup(self):
        # ----- Engines / services -----
        self.engine = SunfishEngine()
        self._cloud_engine = LichessCloudEngine()
        self.game.engine = self.engine

        # ----- Rendering -----
        self.board_view = BoardRenderer(self)
        self.hud = HudView(self, z=200)
        self.promo = PromotionOverlay(self, z=210)

        # ----- Selection / promotion -----
        self.selected = None
        self._promo_active = False
        self._promo_from = None
        self._promo_to = None

        # ----- AI worker state -----
        self._ai_lock = threading.Lock()
        self._ai_generation = 0
        self._ai_thinking = False
        self._ai_job = None

        self._ai_worker_running = True
        self._ai_worker = threading.Thread(target=self._ai_worker_loop, daemon=True)
        self._ai_worker.start()

        # ----- Cloud eval state -----
        self._cloud_generation = 0
        self._cloud_last_fen = None
        self._cloud_inflight = False
        
        # ----- Review Mode -----
        self.review_mode = False
        self._review_entry_ply = None
        self._review_entry_selected = None
        # A translucent review overlay
        self._review_overlay = ShapeNode()
        self._review_overlay.z_position = 150
        self._review_overlay.alpha = 0.00
        self._review_overlay.fill_color = (0, 0, 0)
        self._review_overlay.stroke_color = (0, 0, 0)
        self._review_overlay.line_width = 0
        self._review_overlay.anchor_point = (0, 0)  # bottom-left anchor
        self.add_child(self._review_overlay)

        # Initial draw + initial cloud
        self.ready = True
        self.redraw_all()
        self._after_move_committed(initial=True)  # sets cloud pending + queues if needed

    def stop(self):
        """Call this when the scene/view is being dismissed to stop background work."""
        self._ai_worker_running = False
        with self._ai_lock:
            self._ai_job = None
            self._ai_thinking = False
            self._ai_generation += 1

    # --------------------------------------------------
    # Layout / drawing
    # --------------------------------------------------
    def did_change_size(self):
        if not self.ready:
            return
        self.redraw_all()

    def redraw_all(self):
        self.board_view.compute_geometry()
        self.board_view.draw_squares()
        self.board_view.sync_pieces(self.game.board)
        self.board_view.refresh_overlays(self.game.board, self.selected)
        
        # Update review mode overlay
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
    # Centralized state transitions
    # -----------------------------------------------
    def _invalidate_ai(self):
        with self._ai_lock:
            self._ai_generation += 1
            self._ai_job = None
            self._ai_thinking = False
        self.refresh_hud()

    def _eval_white_cp(self, board: chess.Board) -> int:
        """
        Fast eval in centipawns, normalized to White perspective (+ = White better).
        Uses SunfishEngine._evaluate() which is from side-to-move perspective.
        """
        # terminal positions
        if board.is_checkmate():
            return -EVAL_CLAMP_CP if board.turn == chess.WHITE else EVAL_CLAMP_CP
        if board.is_stalemate() or board.is_insufficient_material():
            return 0
    
        # side-to-move eval -> White perspective
        stm_cp = int(self.engine.eval_position(board, level=self.game.ai_level))
        white_cp = stm_cp if board.turn == chess.WHITE else -stm_cp
    
        # clamp
        if white_cp > EVAL_CLAMP_CP:
            white_cp = EVAL_CLAMP_CP
        elif white_cp < -EVAL_CLAMP_CP:
            white_cp = -EVAL_CLAMP_CP
    
        return white_cp
    
    def _print_eval(self, tag: str = ""):
        """
        Call after moves to print eval and keep normalized value around for an eval bar.
        """
        if self.review_mode:
            return
    
        b = self.game.board
        white_cp = self._eval_white_cp(b)
        norm = float(math.tanh(float(white_cp) / float(EVAL_TANH_SCALE_CP)))
    
        # optional: store for future eval bar
        self.eval_white_cp = white_cp
        self.eval_norm = norm
    
        suffix = f" [{tag}]" if tag else ""
        print(f"EVAL{suffix}: {white_cp:+d} cp   norm: {norm:+.3f}")
    
    def _after_position_changed(self):
        """Pure UI sync after the board state changed."""
        self.selected = None
        self._clear_promotion_ui()
        self.board_view.sync_pieces(self.game.board)
        self.board_view.refresh_overlays(self.game.board, self.selected)
        self.refresh_hud()

    def _after_move_committed(self, *, initial: bool = False):
        """
        Central "post-commit" hook:
          - clears & marks cloud pending (or book arrows when cloud disabled)
          - queues cloud eval if appropriate
          - schedules AI reply if appropriate
        """
        if not initial:
            # AI jobs become stale after a committed move
            self._invalidate_ai()

        self._clear_cloud_eval()
        self._queue_cloud_eval()
        self.refresh_hud()
        self._schedule_ai_if_needed()
        self._print_eval()

    # -----------------------------------------------
    # Review / history navigation mode
    # -----------------------------------------------
    def begin_review_mode(self):
        """Freeze AI + cloud while the user is navigating move history."""
        if not self.ready or self.review_mode:
            return
    
        self.review_mode = True
        self._review_overlay.alpha = REVIEW_OVERLAY_ALPHA
        
        # Remember where we entered review mode (so end_review_mode can "cancel")
        self._review_entry_ply = len(self.game.board.move_stack)
        self._review_entry_selected = self.selected
    
        # Stop any pending/active AI job so it can't apply into a historical position
        self._invalidate_ai()
    
        # Stop cloud churn while reviewing (and clear arrows/text as you prefer)
        self._clear_cloud_eval()
    
        self.refresh_hud()
    
    def fork_review_mode(self):
        """Exit review mode and resume normal behavior from the current board position."""
        if not self.ready or not self.review_mode:
            return
        self.review_mode = False
        self._review_overlay.alpha = 0.0
    
        # Resume cloud/AI behavior naturally from the current position
        self._clear_cloud_eval()
        self._queue_cloud_eval()
        self.refresh_hud()
        self._schedule_ai_if_needed()

    def end_review_mode(self):
        """Cancel review: revert to entry position and resume normal behavior."""
        if not self.ready or not self.review_mode:
            return
    
        entry = self._review_entry_ply
        self._review_entry_ply = None
    
        self.review_mode = False
        self._review_overlay.alpha = 0.0
    
        # Revert board back to where we entered review mode
        if entry is not None:
            ok = self.game.jump_to_ply(int(entry))
            # Even if jump fails, force UI to sync to whatever state we're in
            self._after_position_changed()
        else:
            # If we somehow didn't record, just resync
            self._after_position_changed()
    
        # Restore selection if you want (optional)
        self.selected = self._review_entry_selected if entry is not None else None
        self._review_entry_selected = None
        self.board_view.refresh_overlays(self.game.board, self.selected)
    
        # Resume cloud/AI behavior naturally from the restored position
        self._after_move_committed()

    # -----------------------------------------------
    # Settings
    # -----------------------------------------------
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

        self._invalidate_ai()

        self.game.set_ai_settings(vs_ai=vs_ai, ai_color=ai_color, ai_level=ai_level)
        self.board_view.set_flipped(vs_ai and ai_color == chess.WHITE)

        self.game.set_opening(opening_choice)
        self.game.set_practice_tier(practice_tier)
        self.game.set_show_sugg_arrows(show_sugg_arrows)
        self.game.set_cloud_eval(cloud_eval)

        # Force cloud state to recompute consistently via centralized hook
        self.redraw_all()
        self._after_move_committed()

    # --------------------------------------------------
    # AI scheduling + worker
    # --------------------------------------------------
    def _schedule_ai_if_needed(self):
        """
        Only decides whether to start an AI job.
        Does NOT touch cloud state.
        """
        if not self.game.vs_ai:
            return
        if self.review_mode:
            return

        b = self.game.board
        if b.is_game_over():
            return

        if b.turn != self.game.ai_color:
            return

        with self._ai_lock:
            if self._ai_thinking:
                return
            self._ai_thinking = True
            gen = self._ai_generation
            self._ai_job = (b.fen(), self.game.ai_level, gen)

        self.refresh_hud()

    def _ai_worker_loop(self):
        while self._ai_worker_running:
            with self._ai_lock:
                job = self._ai_job
                self._ai_job = None

            if job is None:
                time.sleep(0.02)
                continue

            fen, level, gen = job
            mv = None

            try:
                board = chess.Board(fen)
                mv, _ = self.game.choose_ai_move(
                    level=level,
                    engine=self.engine,
                    randomness=self.game.book_randomness,
                    board=board,
                )
            except Exception:
                print("[AI]", traceback.format_exc())

            ui.delay(lambda mv=mv, gen=gen: self._apply_ai_move(mv, gen), 0)

    def _apply_ai_move(self, mv, gen):
        # Prevent late AI result
        if self.review_mode:
            with self._ai_lock:
                self._ai_thinking = False
            self.refresh_hud()
            return
        
        with self._ai_lock:
            if gen != self._ai_generation:
                self._ai_thinking = False
                self.refresh_hud()
                return
            self._ai_thinking = False

        if mv and self.game.apply_ai_move(mv):
            self._after_position_changed()
            # AI move committed → one centralized post-commit
            self._after_move_committed()
        else:
            self.refresh_hud()

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
                # Keep book arrows alive if enabled
                self.game.suggested_moves = (
                    self.game.compute_suggest_moves(max_moves=2)
                    if self.game.show_sugg_arrows
                    else []
                )
                self.board_view.refresh_overlays(self.game.board, self.selected)
                self.refresh_hud()
            ui.delay(apply_disabled, 0)
            return

        ce = self._cloud_engine.eval(fen, multipv=3)

        def apply():
            if gen != self._cloud_generation:
                self._cloud_inflight = False
                self._queue_cloud_eval()
                return

            self._cloud_inflight = False
            self.game.cloud_eval = ce
            self.game.cloud_eval_pending = False
            self.game.suggested_moves = self.game.compute_suggest_moves(max_moves=2)
            self.board_view.refresh_overlays(self.game.board, self.selected)
            self.refresh_hud()

        ui.delay(apply, 0)
        
    def _clear_cloud_eval(self):
        """
        Central policy:
          - Practice READY: no cloud work
          - Cloud disabled: book suggestions (if arrows enabled), no "Cloud: ..."
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
        self._after_position_changed()
        self._after_move_committed()

    def undo(self):
        if not self.ready:
            return
        if not self.game.can_undo():
            return
        self.game.undo_plies(2 if self.game.vs_ai else 1)
        self._after_position_changed()
        self._after_move_committed()

    def redo(self):
        if not self.ready:
            return
        if not self.game.can_redo():
            return
        self.game.redo_plies(2 if self.game.vs_ai else 1)
        self._after_position_changed()
        self._after_move_committed()

    def jump_to_ply(self, ply_index: int):
        if not self.ready:
            return False

        self._invalidate_ai()

        ok = self.game.jump_to_ply(ply_index)
        if not ok:
            # Even if jump fails, refresh to keep UI consistent
            self._after_position_changed()
            self.refresh_hud()
            return False

        self._after_position_changed()

        # We jumped; treat as “position change” but not necessarily a “new move committed”.
        # Still clear/requeue cloud eval so arrows/hud reflect the new position.
        self._clear_cloud_eval()
        self._queue_cloud_eval()

        # If we landed on AI-to-move, let the AI respond naturally
        self._schedule_ai_if_needed()
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
            self._after_position_changed()
            self._after_move_committed()

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
            # If nothing selected yet, behave normally: select own piece.
            if self.selected is None:
                piece = self.game.board.piece_at(sq)
                if piece and piece.color == self.game.board.turn:
                    self.selected = sq
                # Always refresh (tapping empty square clears nothing, just updates highlights)
                self.board_view.refresh_overlays(self.game.board, self.selected)
                self.refresh_hud()
                return
        
            # Something is selected already:
            # 1) If user tapped another of their own pieces, switch selection (normal behavior)
            # Tap same square again -> unselect (toggle)
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
        
            # 2) Otherwise user is attempting a move/capture.
            # In review mode we *block* the commit, but keep UI natural.
            # Clear selection after an attempted move to mirror normal "move attempt finishes interaction".
            self.selected = None
            self.board_view.refresh_overlays(self.game.board, self.selected)
            self.refresh_hud()
            return
    
        if self.selected is None:
            piece = self.game.board.piece_at(sq)
            if piece and piece.color == self.game.board.turn:
                self.selected = sq
                self.board_view.refresh_overlays(self.game.board, self.selected)
                self.refresh_hud()
            return
        # Tap same square again -> unselect (toggle)
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
            self._after_position_changed()
            self._after_move_committed()
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
        self._after_position_changed()
        self._after_move_committed()
        return True, msg

    def export_text(self, mode):
        return self.game.export_pgn() if mode == "pgn" else self.game.export_fen()
