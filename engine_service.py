# engine_service.py
import threading
import time
import traceback
from dataclasses import dataclass
from collections import OrderedDict

import chess


@dataclass(frozen=True)
class AiJob:
    """Request for an AI move."""
    fen: str
    level: int
    gen: int


@dataclass(frozen=True)
class EvalJob:
    """Request for a static position evaluation."""
    fen: str
    level: int
    gen: int


class EngineService:
    """
    Single-threaded local engine service.

    Responsibilities:
    - Own the chess engine instance.
    - Run all engine work on a dedicated worker thread.
    - Coalesce requests (latest-only semantics).
    - Prioritize AI moves over evaluations.
    - Deliver results via data-only callbacks.

    Architectural rules:
    - The engine service NEVER mutates UI or scene state.
    - Callbacks are data-only sinks.
    - The scene decides when results are applied (e.g. during update()).

    Caching:
    - Evaluation results are cached by a normalized position key derived from FEN:
        (board_fen, turn, castling_rights, ep_square)
      Halfmove/fullmove counters are excluded.
    - Each cached entry stores the best level computed so far for that position.
      Requests at a lower/equal level are served from cache; higher-level requests
      trigger a recompute and replace the cached value.

    Engine contract:
      - choose_move(board, level=...) -> (move | None, score_stm)
      - eval_position(board, level=...) -> score_stm
        where score_stm is from the side-to-move perspective (+ = good for side to move).
    """

    # Keep this modest; review scrubbing hits the same few hundred positions at most.
    DEFAULT_EVAL_CACHE_MAX = 512

    def __init__(
        self,
        *,
        engine_factory,
        on_ai_result,
        on_eval_result,
        name: str = "EngineService",
        yield_idle_s: float = 0.02,
        eval_cache_max: int | None = None,
    ):
        self.name = str(name)

        # Engine construction is deferred to the worker thread
        self._engine_factory = engine_factory
        self._engine = None

        # Data-only callbacks (owned by the scene)
        self._on_ai_result = on_ai_result
        self._on_eval_result = on_eval_result

        self._yield_idle_s = float(yield_idle_s)

        self._lock = threading.Lock()
        self._running = False

        # Latest-only pending jobs (coalesced)
        self._pending_ai: AiJob | None = None
        self._pending_eval: EvalJob | None = None

        self._worker: threading.Thread | None = None

        # Eval cache (LRU): key -> (best_level, white_cp)
        max_n = self.DEFAULT_EVAL_CACHE_MAX if eval_cache_max is None else int(eval_cache_max)
        self._eval_cache_max = max(0, max_n)
        self._eval_cache: OrderedDict[tuple, tuple[int, int]] = OrderedDict()

    # -----------------------------------------------
    # Lifecycle
    # -----------------------------------------------
    def start(self) -> None:
        """Start the worker thread if not already running."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._pending_ai = None
            self._pending_eval = None
            # Cache is session-scoped; keep it across start/stop only if you want.
            # For now, reset on start to keep behavior simple/predictable.
            self._eval_cache.clear()

        self._worker = threading.Thread(
            target=self._worker_loop,
            daemon=True,
        )
        self._worker.start()

    def stop(self) -> None:
        """Signal the worker thread to stop."""
        with self._lock:
            self._running = False
            self._pending_ai = None
            self._pending_eval = None
            # Keep cache intact on stop by default? Choose simplicity: clear it.
            self._eval_cache.clear()

    # -----------------------------------------------
    # Requests (thread-safe)
    # -----------------------------------------------
    def request_ai(self, *, fen: str, level: int, gen: int) -> None:
        """
        Request an AI move.
        Overwrites any previously pending AI request.
        """
        job = AiJob(
            fen=str(fen),
            level=int(level),
            gen=int(gen),
        )
        with self._lock:
            self._pending_ai = job

    def request_eval(self, *, fen: str, level: int, gen: int) -> None:
        """
        Request a static evaluation.

        If a cached eval exists for the same position at an equal or higher level,
        the callback is invoked immediately with the cached result and no worker
        job is scheduled.
        """
        fen = str(fen)
        level = int(level)
        gen = int(gen)

        key = self._eval_cache_key_from_fen(fen)
        if key is not None and self._eval_cache_max > 0:
            cached = None
            with self._lock:
                if self._running:
                    entry = self._eval_cache.get(key)
                    if entry is not None:
                        best_level, white_cp = entry
                        if best_level >= level:
                            # LRU touch
                            self._eval_cache.move_to_end(key, last=True)
                            cached = int(white_cp)
            if cached is not None:
                cb = self._on_eval_result
                if callable(cb):
                    cb(gen=gen, fen=fen, white_cp=int(cached))
                return

        job = EvalJob(
            fen=fen,
            level=level,
            gen=gen,
        )
        with self._lock:
            self._pending_eval = job

    # -----------------------------------------------
    # Worker loop
    # -----------------------------------------------
    def _worker_loop(self) -> None:
        """Main worker loop. Runs until stop() is called."""
        try:
            # Engine is constructed inside the worker thread
            self._engine = self._engine_factory()
        except Exception:
            print(
                f"[{self.name}] Failed to construct engine:\n"
                f"{traceback.format_exc()}"
            )
            with self._lock:
                self._running = False
            return

        while True:
            with self._lock:
                if not self._running:
                    break

                # Priority: AI first
                if self._pending_ai is not None:
                    job = self._pending_ai
                    self._pending_ai = None
                    self._pending_eval = None  # drop evals superseded by AI
                    kind = "ai"
                elif self._pending_eval is not None:
                    job = self._pending_eval
                    self._pending_eval = None
                    kind = "eval"
                else:
                    job = None
                    kind = None

            if job is None:
                time.sleep(self._yield_idle_s)
                continue

            try:
                if kind == "ai":
                    self._run_ai_job(job)
                else:
                    self._run_eval_job(job)
            except Exception:
                print(
                    f"[{self.name}] Job error:\n"
                    f"{traceback.format_exc()}"
                )

        # Clean shutdown
        self._engine = None

    # -----------------------------------------------
    # Job runners
    # -----------------------------------------------
    def _run_ai_job(self, job: AiJob) -> None:
        board = chess.Board(job.fen)
        move, score_stm = self._engine.choose_move(
            board,
            level=job.level,
        )

        white_cp = self._stm_to_white_cp(
            score_stm,
            board.turn,
        )

        cb = self._on_ai_result
        if callable(cb):
            cb(
                gen=job.gen,
                fen=job.fen,
                move=move,
                white_cp=int(white_cp),
            )

    def _run_eval_job(self, job: EvalJob) -> None:
        board = chess.Board(job.fen)
        score_stm = int(
            self._engine.eval_position(
                board,
                level=job.level,
            )
        )

        white_cp = int(self._stm_to_white_cp(score_stm, board.turn))

        # Update cache (dominance: keep best level per position key)
        key = self._eval_cache_key_from_board(board)
        if key is not None and self._eval_cache_max > 0:
            with self._lock:
                if self._running:
                    prev = self._eval_cache.get(key)
                    if prev is None or int(job.level) >= int(prev[0]):
                        self._eval_cache[key] = (int(job.level), int(white_cp))
                        self._eval_cache.move_to_end(key, last=True)
                        # LRU cap
                        while len(self._eval_cache) > self._eval_cache_max:
                            self._eval_cache.popitem(last=False)

        cb = self._on_eval_result
        if callable(cb):
            cb(
                gen=job.gen,
                fen=job.fen,
                white_cp=int(white_cp),
            )

    # -----------------------------------------------
    # Cache helpers
    # -----------------------------------------------
    @staticmethod
    def _eval_cache_key_from_board(board: chess.Board) -> tuple:
        """Return a normalized position key (excludes move counters)."""
        # (piece placement, side to move, castling rights, ep square)
        # ep_square is None or an int [0..63]
        try:
            return (
                board.board_fen(),
                bool(board.turn),
                board.castling_xfen(),
                board.ep_square,
            )
        except Exception:
            return None

    @classmethod
    def _eval_cache_key_from_fen(cls, fen: str) -> tuple | None:
        """Parse FEN and return the normalized cache key."""
        try:
            board = chess.Board(fen)
        except Exception:
            return None
        return cls._eval_cache_key_from_board(board)

    # -----------------------------------------------
    # Helpers
    # -----------------------------------------------
    @staticmethod
    def _stm_to_white_cp(
        score_stm: int,
        side_to_move_is_white: bool,
    ) -> int:
        """Convert a side-to-move score into White's perspective."""
        return int(score_stm) if side_to_move_is_white else -int(score_stm)
