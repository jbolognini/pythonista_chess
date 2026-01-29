# engine_service.py
import threading
import time
import traceback
from dataclasses import dataclass

import ui
import chess


@dataclass(frozen=True)
class AiJob:
    fen: str
    level: int
    gen: int


@dataclass(frozen=True)
class EvalJob:
    fen: str
    level: int
    gen: int


class EngineService:
    """
    Single-threaded local engine service (sequential).
    - Owns the engine instance and runs ALL engine work on one worker thread.
    - Coalesces requests: keeps only the newest pending AI job and newest pending eval job.
    - Prioritizes AI over eval.
    - Returns scores in *White perspective* (+ = White better).

    Debug:
      - Set DEBUG=True to print job flow + timings and counters.
      - Set DROP_EVAL_WHEN_AI_PENDING=True to prove/disprove duplicated-search overload.

    Engine contract:
      - choose_move(board, level=...) -> (move_or_none, score_stm_int)
      - eval_position(board, level=...) -> score_stm_int
        where score_stm_int is from side-to-move perspective (+ = side to move better).
    """

    # --- reversible debug switches (no architecture pollution) ---
    DEBUG = False
    DROP_EVAL_WHEN_AI_PENDING = True

    def __init__(
        self,
        *,
        engine_factory,
        on_ai_result,
        on_eval_result,
        name: str = "EngineService",
        yield_idle_s: float = 0.02,
    ):
        self.name = str(name)
        self._engine_factory = engine_factory
        self._engine = None

        self._on_ai_result = on_ai_result
        self._on_eval_result = on_eval_result

        self._yield_idle_s = float(yield_idle_s)

        self._lock = threading.Lock()
        self._running = False

        # latest-only pending jobs
        self._pending_ai = None   # AiJob | None
        self._pending_eval = None # EvalJob | None

        self._worker = None

        # debug counters (only used when DEBUG=True)
        self._dbg_ai_req = 0
        self._dbg_eval_req = 0
        self._dbg_ai_run = 0
        self._dbg_eval_run = 0

    # ----------------------------
    # Debug helper
    # ----------------------------
    def _dbg(self, msg: str) -> None:
        if self.DEBUG:
            print(f"[{self.name}] {msg}")

    # ----------------------------
    # Lifecycle
    # ----------------------------
    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._pending_ai = None
            self._pending_eval = None

        self._dbg_ai_req = 0
        self._dbg_eval_req = 0
        self._dbg_ai_run = 0
        self._dbg_eval_run = 0

        # Create engine instance inside the worker thread (thread confinement).
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._pending_ai = None
            self._pending_eval = None

    # ----------------------------
    # Requests (thread-safe)
    # ----------------------------
    def request_ai(self, *, fen: str, level: int, gen: int) -> None:
        """
        Request an AI move for this position. AI jobs overwrite any previous pending AI job.
        AI jobs are always processed before eval jobs.
        """
        job = AiJob(fen=str(fen), level=int(level), gen=int(gen))
        with self._lock:
            self._pending_ai = job
            if self.DEBUG:
                self._dbg_ai_req += 1
                n = self._dbg_ai_req
        if self.DEBUG:
            self._dbg(f"REQ AI   gen={job.gen} lvl={job.level} req#{n}")

    def request_eval(self, *, fen: str, level: int, gen: int) -> None:
        """
        Request an eval for this position. Eval jobs overwrite any previous pending eval job.
        """
        job = EvalJob(fen=str(fen), level=int(level), gen=int(gen))
        with self._lock:
            self._pending_eval = job
            if self.DEBUG:
                self._dbg_eval_req += 1
                n = self._dbg_eval_req
        if self.DEBUG:
            self._dbg(f"REQ EVAL gen={job.gen} lvl={job.level} req#{n}")

    # ----------------------------
    # Worker
    # ----------------------------
    def _worker_loop(self):
        # Build engine in worker thread (safe ownership).
        try:
            self._engine = self._engine_factory()
        except Exception:
            print(f"[{self.name}] Failed to construct engine:\n{traceback.format_exc()}")
            with self._lock:
                self._running = False
            return

        while True:
            with self._lock:
                if not self._running:
                    break

                # Priority: AI first
                job_ai = self._pending_ai
                if job_ai is not None:
                    self._pending_ai = None

                    # Debug experiment: prove duplicated-search overload by dropping eval
                    # whenever an AI job is pending.
                    if self.DROP_EVAL_WHEN_AI_PENDING:
                        self._pending_eval = None

                    job = job_ai
                    kind = "ai"
                else:
                    job_eval = self._pending_eval
                    if job_eval is not None:
                        self._pending_eval = None
                        job = job_eval
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
                print(f"[{self.name}] Job error:\n{traceback.format_exc()}")

        # clean shutdown
        self._engine = None

    # ----------------------------
    # Job runners
    # ----------------------------
    def _run_ai_job(self, job: AiJob) -> None:
        if self.DEBUG:
            self._dbg_ai_run += 1
            run_n = self._dbg_ai_run
            t0 = time.perf_counter()
            self._dbg(f"RUN AI   gen={job.gen} lvl={job.level} run#{run_n}")

        board = chess.Board(job.fen)
        mv, score_stm = self._engine.choose_move(board, level=job.level)

        # Convert to White perspective (+ = White better)
        white_cp = self._stm_to_white_cp(score_stm, board.turn)

        if self.DEBUG:
            dt = time.perf_counter() - t0
            self._dbg(f"DONE AI  gen={job.gen} dt={dt:.3f}s white_cp={int(white_cp)}")

        def apply():
            cb = self._on_ai_result
            if callable(cb):
                cb(gen=job.gen, fen=job.fen, move=mv, white_cp=int(white_cp))

        ui.delay(apply, 0)

    def _run_eval_job(self, job: EvalJob) -> None:
        if self.DEBUG:
            self._dbg_eval_run += 1
            run_n = self._dbg_eval_run
            t0 = time.perf_counter()
            self._dbg(f"RUN EVAL gen={job.gen} lvl={job.level} run#{run_n}")

        board = chess.Board(job.fen)
        score_stm = int(self._engine.eval_position(board, level=job.level))
        white_cp = self._stm_to_white_cp(score_stm, board.turn)

        if self.DEBUG:
            dt = time.perf_counter() - t0
            self._dbg(f"DONE EVAL gen={job.gen} dt={dt:.3f}s white_cp={int(white_cp)}")

        def apply():
            cb = self._on_eval_result
            if callable(cb):
                cb(gen=job.gen, fen=job.fen, white_cp=int(white_cp))

        ui.delay(apply, 0)

    @staticmethod
    def _stm_to_white_cp(score_stm: int, side_to_move_is_white: bool) -> int:
        # score_stm: + good for side to move
        # convert to + good for White
        return int(score_stm) if side_to_move_is_white else -int(score_stm)
