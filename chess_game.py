# chess_game.py
import io
import random
from dataclasses import dataclass

import chess
import chess.pgn
import chess.polyglot

from openings import OPENING_ORDER, practice_opening_title, opening_options, practice_items

PROMOTION_PIECES = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)
MATE_CP = 200_000


# ---------------------------------------------------
# Captured material (derived from current board state)
# ---------------------------------------------------
@dataclass(frozen=True)
class CapturedMaterial:
    """Missing pieces for each color, expressed as piece symbols.

    - missing_black: lowercase symbols (pieces White has captured)
    - missing_white: uppercase symbols (pieces Black has captured)
    """

    missing_white: list[str]  # e.g. ["Q","P","P"]  (White pieces missing from board)
    missing_black: list[str]  # e.g. ["q","p","p"]  (Black pieces missing from board)


# ---------------------------------------------------
# Suggestion model (cloud/book)
# ---------------------------------------------------
@dataclass(frozen=True)
class SuggestMove:
    uci: str
    source: str            # "cloud" | "book" | "engine"
    cp: int | None = None  # centipawns
    mate: int | None = None


def suggest_score_cp(sm: SuggestMove) -> int:
    """Higher is better for side to move."""
    if sm.mate is not None:
        sign = 1 if sm.mate > 0 else -1
        return sign * (MATE_CP - 1000 * abs(sm.mate))
    return int(sm.cp or 0)


def arrow_weights(best: SuggestMove, second: SuggestMove | None) -> tuple[float, float]:
    b = suggest_score_cp(best)
    s = suggest_score_cp(second) if second else b
    d = max(0, b - s)

    t = min(1.0, d / 300.0)   # saturate at ~300cp
    w1 = 0.55 + 0.35 * t      # 0.55..0.90
    w2 = 1.0 - w1             # 0.45..0.10
    return w1, w2


# ---------------------------------------------------------
# Game
# ---------------------------------------------------------
class ChessGame:
    """
    Core game state + practice/theory/book logic.

    UI-agnostic: Scene owns rendering, input, threading, and cloud request lifecycle.

    Engine note:
      - ChessGame does NOT call local engines directly. Local engine work is performed by EngineService.
      - ChessGame stores eval and other derived analysis as pure state.
    """

    def __init__(self):
        self.board = chess.Board()

        # History
        self.redo_stack: list[chess.Move] = []

        # Eval (White perspective: + = White better)
        self.eval_cp: int | None = None
        self.eval_source: str | None = None   # "engine" | "cloud" | ...
        self.eval_fen: str | None = None      # fen that produced eval_cp
        self.eval_pending: bool = False       # optional, helps UI show "thinking" later

        # Suggestions / cloud
        self.suggested_moves: list[SuggestMove] = []
        self.cloud_eval_pending = False
        self.cloud_eval = None
        self.cloud_eval_enabled = False
        self.show_sugg_arrows = True

        # AI/mode settings
        self.vs_ai = True
        self.ai_color = chess.BLACK
        self.ai_level = 1

        # Book settings
        self.use_book = True
        self.book_path = "assets/polyglot/dara.bin"
        self.book_randomness = 0.25

        # Practice/opening selection
        self.opening_choice = None
        self.opening_title = None
        self.practice_phase = "FREE"  # FREE / READY / IN_THEORY / OUT_OF_THEORY

        self._theory_started = False
        self.opening_lead_in_plies = 4

        self._practice_lib = None
        self._practice_notes = {}
        self.practice_tier = "beginner"      # "beginner" or "master"
        self.practice_show_hints = False
        self._practice_feedback = ""

    # =========================================================
    # Small UI-facing helpers (keeps Scene decoupled)
    # =========================================================
    def can_undo(self) -> bool:
        return bool(self.board.move_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def current_ply(self) -> int:
        return len(self.board.move_stack)

    def total_ply(self) -> int:
        # Includes undone moves as well
        return len(self.board.move_stack) + len(self.redo_stack)

    def _full_line_moves(self) -> list[chess.Move]:
        # board.move_stack is played; redo_stack holds undone moves with "next redo" at the END.
        # Full line = played + remaining, where remaining is redo_stack reversed.
        return list(self.board.move_stack) + list(reversed(self.redo_stack))

    def board_is_fresh(self) -> bool:
        return self.board.fen() == chess.Board().fen()

    # =========================================================
    # Captured material (derived from current board state)
    # =========================================================
    def captured_material(self) -> CapturedMaterial:
        """Return missing pieces for each color based on current board state.

        Computes from the current board only (supports FEN import, jump_to_ply, undo/redo).
        Missing Black = pieces White has captured (lowercase).
        Missing White = pieces Black has captured (uppercase).
        """
        start = {
            chess.PAWN: 8,
            chess.KNIGHT: 2,
            chess.BISHOP: 2,
            chess.ROOK: 2,
            chess.QUEEN: 1,
        }

        cur_white = {pt: 0 for pt in start}
        cur_black = {pt: 0 for pt in start}

        for p in self.board.piece_map().values():
            if p.piece_type == chess.KING:
                continue
            if p.color == chess.WHITE:
                if p.piece_type in cur_white:
                    cur_white[p.piece_type] += 1
            else:
                if p.piece_type in cur_black:
                    cur_black[p.piece_type] += 1

        missing_white_counts = {pt: max(0, start[pt] - cur_white[pt]) for pt in start}
        missing_black_counts = {pt: max(0, start[pt] - cur_black[pt]) for pt in start}

        # Order: Q, R, B, N, P (major pieces first, pawns last)
        order = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]

        missing_white: list[str] = []
        missing_black: list[str] = []

        for pt in order:
            c_w = missing_white_counts[pt]
            if c_w:
                sym_w = chess.Piece(pt, chess.WHITE).symbol()  # uppercase
                missing_white.extend([sym_w] * c_w)

            c_b = missing_black_counts[pt]
            if c_b:
                sym_b = chess.Piece(pt, chess.BLACK).symbol()  # lowercase
                missing_black.extend([sym_b] * c_b)

        return CapturedMaterial(missing_white=missing_white, missing_black=missing_black)

    # ==============================================
    # Eval state (owned by game; computed elsewhere)
    # ==============================================
    def set_eval(self, *, white_cp: int | None, source: str | None, fen: str | None = None) -> None:
        """
        Store a local eval in centipawns from White perspective (+ = White better).
        """
        self.eval_cp = int(white_cp) if white_cp is not None else None
        self.eval_source = str(source) if source else None
        self.eval_fen = str(fen) if fen else None
        self.eval_pending = False

    def clear_eval(self, *, pending: bool = False) -> None:
        self.eval_cp = None
        self.eval_source = None
        self.eval_fen = None
        self.eval_pending = bool(pending)

    # =========================================================
    # Configuration
    # =========================================================
    def set_ai_settings(self, *, vs_ai: bool, ai_color, ai_level: int) -> None:
        self.vs_ai = bool(vs_ai)
        self.ai_color = ai_color
        self.ai_level = int(ai_level)

    def configure_book(self, *, use_book: bool = True, book_path=None, randomness: float = 0.25) -> None:
        self.use_book = bool(use_book)
        if book_path is not None:
            self.book_path = str(book_path)
        self.book_randomness = float(randomness)

    def set_opening(self, opening_choice):
        if opening_choice and (not self.board_is_fresh()):
            return False
        self.opening_choice = opening_choice
        self.opening_title = practice_opening_title(opening_choice)
        self._theory_started = False
        self._practice_lib = None
        self._practice_notes = {}
        self._practice_feedback = ""
        self.update_practice_phase()
        return True

    def set_practice_tier(self, tier: str) -> None:
        tier = (tier or "beginner").lower()
        self.practice_tier = "master" if tier == "master" else "beginner"
        self._practice_lib = None
        self._practice_notes = {}
        self.update_practice_phase()

    def set_show_sugg_arrows(self, enabled: bool) -> None:
        self.show_sugg_arrows = bool(enabled)

    def set_cloud_eval(self, enabled: bool) -> None:
        self.cloud_eval_enabled = bool(enabled)

    @staticmethod
    def opening_options():
        return opening_options()

    # =========================================================
    # Lifecycle / history
    # =========================================================
    def reset(self) -> None:
        self.board.reset()
        self._clear_redo()
        self._theory_started = False
        self._practice_feedback = ""
        self.practice_show_hints = False
        self.update_practice_phase()

    def jump_to_ply(self, target_ply: int) -> bool:
        """
        Jump to an absolute ply index in the current line (including undone moves).
        0 = starting position
        total_ply() = end of line

        This rebuilds the board deterministically and reconstitutes redo_stack.
        """
        try:
            t = int(target_ply)
        except Exception:
            return False

        full = self._full_line_moves()
        if t < 0 or t > len(full):
            return False

        # Rebuild board from scratch
        b = chess.Board()
        for mv in full[:t]:
            if mv not in b.legal_moves:
                # If something got inconsistent (e.g., imported weirdness), fail safely.
                return False
            b.push(mv)

        self.board = b

        # Remaining moves become redo stack; order must allow redo_plies() to pop next move
        remaining = full[t:]                      # next moves in forward order
        self.redo_stack = list(reversed(remaining))  # so pop() yields next

        # Clear transient practice/theory state and recompute phase
        self._theory_started = False
        self._practice_feedback = ""
        self.update_practice_phase()
        return True

    def undo_plies(self, plies: int = 1) -> None:
        for _ in range(int(plies)):
            if not self.board.move_stack:
                break
            mv = self.board.pop()
            self.redo_stack.append(mv)
        self._theory_started = False
        self.update_practice_phase()

    def redo_plies(self, plies: int = 1) -> None:
        for _ in range(int(plies)):
            if not self.redo_stack:
                break
            mv = self.redo_stack.pop()
            if mv in self.board.legal_moves:
                self.board.push(mv)
        self.update_practice_phase()

    def _clear_redo(self) -> None:
        self.redo_stack.clear()

    def san_move_list(self) -> list[str]:
        """
        Returns a list of display strings, one per ply, for the *full line* (played + redo).
        Example items: "1. e4", "... c5", "2. Nf3", "... d6"
        """
        full = self._full_line_moves()
        out: list[str] = []
        b = chess.Board()

        for i, mv in enumerate(full):
            ply = i + 1
            move_no = (ply + 1) // 2
            is_white = (ply % 2 == 1)

            try:
                san = b.san(mv)
            except Exception:
                san = mv.uci()

            prefix = f"{move_no}. " if is_white else "... "
            out.append(prefix + san)

            # advance
            if mv in b.legal_moves:
                b.push(mv)
            else:
                break

        return out

    # =========================================================
    # Practice/theory state
    # =========================================================
    def update_practice_phase(self) -> None:
        """
        - FREE: no opening selected
        - READY: practice model applies (guided)
        - IN_THEORY: practice no longer applies, but polyglot has moves
        - OUT_OF_THEORY: practice no longer applies, and polyglot has no moves
        """
        if not self.opening_choice:
            self.practice_phase = "FREE"
            self._theory_started = False
            return

        if len(self.board.move_stack) == 0:
            self.practice_phase = "READY"
            self._theory_started = False
            return

        if self.practice_model_applicable(self.board):
            self.practice_phase = "READY"
            self._theory_started = False
            return

        self._theory_started = True
        self.practice_phase = "IN_THEORY" if self.has_book_moves(self.board) else "OUT_OF_THEORY"

    def compute_suggest_moves(self, *, max_moves: int = 2) -> list[SuggestMove]:
        """
        Suggestions are sourced from (in order):
          1) Cloud (if enabled and available)
          2) Book (polyglot)
        """
        b = self.board

        # 1) Cloud
        if self.cloud_eval_enabled:
            ce = self.cloud_eval
            if ce and getattr(ce, "status", None) == "ok":
                out: list[SuggestMove] = []
                for pv in (getattr(ce, "pvs", None) or [])[:max_moves]:
                    uci = getattr(pv, "best_uci", None)
                    if not uci:
                        continue
                    out.append(
                        SuggestMove(
                            uci=uci,
                            source="cloud",
                            cp=getattr(pv, "cp", None),
                            mate=getattr(pv, "mate", None),
                        )
                    )
                    if len(out) >= max_moves:
                        break
                if out:
                    return out

        # 2) Book
        entries = self.polyglot_entries(b) or []
        leg = [e for e in entries if e.move in b.legal_moves]
        if leg:
            leg.sort(key=lambda e: e.weight, reverse=True)
            top = leg[:max_moves]

            def weight_to_cp(w: int) -> int:
                return int(50 * (w ** 0.5))

            return [SuggestMove(uci=e.move.uci(), source="book", cp=weight_to_cp(e.weight)) for e in top]

        return []

    # =========================================================
    # Practice model compilation
    # =========================================================
    def pos_key(self, b: chess.Board) -> str:
        turn = "w" if b.turn == chess.WHITE else "b"
        return f"{b.board_fen()} {turn}"

    def practice_library(self) -> dict[str, dict[str, list[str]]]:
        """
        Returns: {opening_key: {pos_key: [uci_moves...]}} (cached)
        Also builds notes index: self._practice_notes[(opening_key, pos_key, uci)] = note
        """
        if self._practice_lib is not None:
            return self._practice_lib

        tier = self.practice_tier
        lib: dict[str, dict[str, list[str]]] = {}
        self._practice_notes = {}

        for opening_key in OPENING_ORDER:
            items = practice_items(opening_key, tier=tier)
            lib[opening_key] = self._compile_practice_items(opening_key, items)

        self._practice_lib = lib
        return lib

    def _compile_practice_items(self, opening_key: str, items: list[dict]) -> dict[str, list[str]]:
        tree: dict[str, set[str]] = {}

        for item in items:
            san_line = item.get("moves") or []
            if not san_line:
                continue

            b = chess.Board()
            for ply_index, san in enumerate(san_line):
                try:
                    mv = b.parse_san(san)
                except Exception:
                    mv = None

                if mv is None:
                    break

                k = self.pos_key(b)
                uci = mv.uci()
                tree.setdefault(k, set()).add(uci)

                note = self._note_for_item_move(item, ply_index=ply_index, san_move=san)
                if note:
                    self._practice_notes[(opening_key, k, uci)] = note

                b.push(mv)

        return {k: sorted(list(v)) for k, v in tree.items()}

    def _note_for_item_move(self, item: dict, *, ply_index: int, san_move: str) -> str:
        notes = item.get("notes") or item.get("why")
        if not notes:
            return ""

        if isinstance(notes, dict) and ply_index in notes:
            v = notes.get(ply_index)
            return str(v) if v else ""

        if isinstance(notes, dict) and san_move in notes:
            v = notes.get(san_move)
            return str(v) if v else ""

        return ""

    def practice_model_applicable(self, board: chess.Board) -> bool:
        if not self.opening_choice:
            return False
        tree = self.practice_library().get(self.opening_choice)
        if not tree:
            return False

        k = self.pos_key(board)
        candidates = tree.get(k) or []
        for uci in candidates:
            try:
                mv = chess.Move.from_uci(uci)
            except Exception:
                continue
            if mv in board.legal_moves:
                return True
        return False

    def practice_opening_reply(self, b: chess.Board):
        """Return (move, forced) for the practice model."""
        if not self.opening_choice:
            return None, False
        tree = self.practice_library().get(self.opening_choice)
        if not tree:
            return None, False

        k = self.pos_key(b)
        candidates = tree.get(k)
        if not candidates:
            return None, False

        legal = []
        for uci in candidates:
            try:
                mv = chess.Move.from_uci(uci)
            except Exception:
                continue
            if mv in b.legal_moves:
                legal.append(mv)

        if not legal:
            return None, False
        return random.choice(legal), True

    def practice_feedback_for_attempt(self, attempted_move: chess.Move, board: chess.Board | None = None) -> str:
        b = board or self.board
        if not self.opening_choice:
            return ""

        tree = self.practice_library().get(self.opening_choice)
        if not tree:
            return ""

        k = self.pos_key(b)
        expected_uci = tree.get(k) or []
        if not expected_uci:
            return ""

        if attempted_move.uci() in expected_uci:
            return ""

        note = ""
        for uci in expected_uci:
            note = self._practice_notes.get((self.opening_choice, k, uci), "")
            if note:
                break

        return f"Miss. {note}" if note else "Miss."

    def practice_expected_moves_text(self, board: chess.Board | None = None) -> str:
        b = board or self.board
        if not self.opening_choice:
            return ""

        if (not self.practice_show_hints) and (not self._practice_feedback):
            if len(b.move_stack) > 0:
                return ""

        tree = self.practice_library().get(self.opening_choice)
        if not tree:
            return ""

        k = self.pos_key(b)
        candidates = tree.get(k) or []
        if not candidates:
            return ""

        sans: list[str] = []
        for uci in candidates:
            try:
                mv = chess.Move.from_uci(uci)
            except Exception:
                continue
            if mv in b.legal_moves:
                try:
                    sans.append(b.san(mv))
                except Exception:
                    pass

        if not sans:
            return ""

        if len(sans) == 1:
            return f"Expected: {sans[0]}"
        return "Expected: " + ", ".join(sans[:6])

    # =========================================================
    # Polyglot book
    # =========================================================
    def polyglot_entries(self, board: chess.Board):
        if not self.use_book:
            return []
        path = self.book_path
        if not path:
            return []
        try:
            with chess.polyglot.open_reader(path) as r:
                return list(r.find_all(board))
        except Exception:
            return []

    def has_book_moves(self, board: chess.Board) -> bool:
        if not self.use_book:
            return False
        return bool(self.polyglot_entries(board))

    # =========================================================
    # Moves
    # =========================================================
    def legal_promotion_pieces(self, from_sq: int, to_sq: int) -> list[int]:
        p = self.board.piece_at(from_sq)
        if not p or p.piece_type != chess.PAWN:
            return []
        if chess.square_rank(to_sq) not in (0, 7):
            return []

        out: list[int] = []
        legal = self.board.legal_moves
        for pt in PROMOTION_PIECES:
            if chess.Move(from_sq, to_sq, promotion=pt) in legal:
                out.append(pt)
        return out

    def make_human_move(self, mv: chess.Move) -> bool:
        """
        Practice behavior:
          - If the practice model applies here, only expected moves are allowed.
          - Unexpected legal moves are blocked and a feedback note is latched.
        """
        self._practice_feedback = ""

        if mv not in self.board.legal_moves:
            return False

        if self.opening_choice and self.practice_model_applicable(self.board):
            tree = self.practice_library().get(self.opening_choice) or {}
            k = self.pos_key(self.board)
            expected = tree.get(k) or []
            if expected and (mv.uci() not in expected):
                self._practice_feedback = self.practice_feedback_for_attempt(mv, self.board) or "Miss."
                return False

        self.board.push(mv)
        self._clear_redo()
        self.update_practice_phase()
        return True

    def apply_ai_move(self, mv: chess.Move) -> bool:
        if mv not in self.board.legal_moves:
            return False
        self.board.push(mv)
        self._clear_redo()
        self.update_practice_phase()
        return True

    def choose_forced_or_book_move(
        self,
        *,
        randomness: float | None = None,
        board: chess.Board | None = None,
    ):
        """
        Returns (move, source) for non-engine choices, or (None, None) if engine is required.

        source: "forced" | "book" | None
        """
        if randomness is None:
            randomness = self.book_randomness
        b = board or self.board

        mv, forced = self.practice_opening_reply(b)
        if forced and mv:
            return mv, "forced"

        entries = self.polyglot_entries(b)
        if entries:
            entries = sorted(entries, key=lambda e: e.weight, reverse=True)
            if len(entries) == 1 or randomness <= 0:
                return entries[0].move, "book"

            if random.random() < randomness:
                return random.choice(entries).move, "book"
            return entries[0].move, "book"

        return None, None

    # =========================================================
    # Import / Export
    # =========================================================
    def import_pgn_or_fen(self, text: str, *, keep_history: bool = True) -> tuple[bool, str]:
        if not text or not text.strip():
            return False, "Empty input."

        self._clear_redo()
        s = text.strip()

        if self._looks_like_fen(s):
            return self._import_fen(s)
        return self._import_pgn(s, keep_history=keep_history)

    def _looks_like_fen(self, s: str) -> bool:
        parts = s.split()
        return (len(parts) == 6) and ("/" in parts[0]) and (parts[1] in ("w", "b"))

    def _import_fen(self, fen: str) -> tuple[bool, str]:
        try:
            self.board = chess.Board(fen)
        except Exception as e:
            return False, f"Invalid FEN: {e}"

        self._after_import()
        return True, "FEN loaded."

    def _import_pgn(self, pgn_text: str, *, keep_history: bool = True) -> tuple[bool, str]:
        try:
            game = chess.pgn.read_game(io.StringIO(pgn_text))
        except Exception as e:
            return False, f"Invalid PGN: {e}"

        if game is None:
            return False, "Could not parse PGN."

        start_board = game.board()

        if keep_history:
            self.board = start_board
            for mv in game.mainline_moves():
                self.board.push(mv)
        else:
            tmp = start_board
            for mv in game.mainline_moves():
                tmp.push(mv)
            self.board = chess.Board(tmp.fen())

        self._after_import()
        return True, "PGN loaded."

    def _after_import(self) -> None:
        self._theory_started = False
        self._practice_feedback = ""
        self.practice_show_hints = False
        self.update_practice_phase()

    def export_fen(self) -> str:
        return self.board.fen()

    def export_pgn(self) -> str:
        game = chess.pgn.Game()
        node = game
        for mv in self.board.move_stack:
            node = node.add_variation(mv)

        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        return game.accept(exporter).strip()

    # =========================================================
    # HUD text helpers (UI-agnostic)
    # =========================================================
    def _cloud_eval_hud_text(self, board: chess.Board) -> str:
        ce = self.cloud_eval
        if not ce:
            return "—"

        if ce.status == "ok" and ce.pvs:
            parts = []
            for pv in ce.pvs[:3]:
                mv = chess.Move.from_uci(pv.best_uci)
                san = board.san(mv) if mv in board.legal_moves else pv.best_uci

                if pv.mate is not None:
                    score = f"(M{pv.mate})"
                elif pv.cp is not None:
                    score = f"({pv.cp/100:+.2f})"
                else:
                    score = ""

                parts.append(f"{san}{score}")
            return f'Cloud: {"  ".join(parts) if parts else "—"}'

        if ce.status == "rate_limited":
            return "Cloud: wait"
        if ce.status == "offline":
            return "Cloud: offline"
        if ce.status == "timeout":
            return "Cloud: timeout"
        if ce.status == "http_error" and ce.http_code is not None:
            return f"Cloud HTTP {ce.http_code}"
        if ce.status == "bad_json":
            return "Cloud: bad JSON"
        if ce.status == "error":
            return "Cloud: error"

        return "—"

    def hud_row1_text(self, *, ai_thinking: bool = False, promo_active: bool = False) -> str:
        if promo_active:
            return "Choose promotion"
        if ai_thinking:
            return "AI thinking..."

        b = self.board
        if b.is_checkmate():
            winner = "Black" if b.turn == chess.WHITE else "White"
            return f"Checkmate — {winner} wins"
        if b.is_stalemate():
            return "Stalemate — draw"

        turn = "White" if b.turn == chess.WHITE else "Black"
        return f"{turn} to move — CHECK" if b.is_check() else f"{turn} to move"

    def hud_row2_text(self) -> str:
        if not self.opening_choice:
            if self.has_book_moves(self.board):
                return "In book"
            else:
                return "Free play"

        title = self.opening_title or str(self.opening_choice)
        phase = self.practice_phase

        if phase == "READY":
            tag = "Ready"
        elif phase == "IN_THEORY":
            tag = "In theory"
        elif phase == "OUT_OF_THEORY":
            tag = "Out of book (engine)"
        else:
            tag = "Free play"

        return f"{title} • {tag}"

    def hud_row3_text(self, *, max_moves: int = 12) -> str:
        fb = self._practice_feedback or ""
        if fb:
            return fb

        if self.practice_phase == "READY":
            return "—"

        entries = self.polyglot_entries(self.board)
        if not entries:
            return "—"

        entries = sorted(entries, key=lambda e: e.weight, reverse=True)[:max_moves]
        tmp = self.board.copy()
        moves: list[str] = []
        for e in entries:
            mv = e.move
            try:
                san = tmp.san(mv)
            except Exception:
                san = mv.uci()
            moves.append(san)
        return "  ".join(moves)

    def hud_row4_text(self) -> str:
        # Practice helper takes precedence (and hides cloud eval)
        if self.practice_phase == "READY":
            hints_on = self.practice_show_hints
            missed = bool((self._practice_feedback or "").strip())

            if (not hints_on) and (not missed):
                return "—"

            exp = self.practice_expected_moves_text(self.board)
            return exp if exp else "—"

        if self.cloud_eval_enabled and self.cloud_eval_pending:
            return "Cloud: ..."

        return self._cloud_eval_hud_text(self.board)

