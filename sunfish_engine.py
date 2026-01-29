# sunfish_engine.py
import random
import time
import chess

VAL = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

PST_P = [
      0,  0,  0,  0,  0,  0,  0,  0,
     50, 50, 50, 50, 50, 50, 50, 50,
     10, 10, 20, 30, 30, 20, 10, 10,
      5,  5, 10, 25, 25, 10,  5,  5,
      0,  0,  0, 20, 20,  0,  0,  0,
      5, -5,-10,  0,  0,-10, -5,  5,
      5, 10, 10,-20,-20, 10, 10,  5,
      0,  0,  0,  0,  0,  0,  0,  0,
]
PST_N = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
]
PST_B = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
]
PST_R = [
      0,  0,  0,  0,  0,  0,  0,  0,
      5, 10, 10, 10, 10, 10, 10,  5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
      0,  0,  0,  5,  5,  0,  0,  0,
]
PST_Q = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20,
]
PST_K = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20,
]

PST = {
    chess.PAWN: PST_P,
    chess.KNIGHT: PST_N,
    chess.BISHOP: PST_B,
    chess.ROOK: PST_R,
    chess.QUEEN: PST_Q,
    chess.KING: PST_K,
}

MATE_SCORE = 100_000


class SunfishEngine:
    """
    iOS/Pythonista-stability focused alpha-beta engine.

    Contract:
      - choose_move(board, level=...) -> (move_or_none, score_stm_int)
      - eval_position(board, level=...) -> score_stm_int

    score_stm_int: from side-to-move perspective (+ = side to move better)

    Key stability tactics:
      - No per-node sorting; use bucketed move ordering.
      - Real tiny yields (sleep > 0) at a frequent cadence.
      - Iterative deepening at root (safe breakpoints).
      - Small bounded transposition table to reduce midgame blowups.
    """

    # ---------------------------
    # Tunables for iOS stability
    # ---------------------------
    TT_MAX = 80_000              # bounded memory; bump if you have headroom
    TT_CLEAR_EVERY_N_SEARCHES = 12  # periodic TT clear to avoid unbounded dict churn
    TIME_CHECK_MASK = 0x3FF      # check clock every 1024 nodes
    YIELD_MASK = 0xFFF          # yield every 4096 nodes
    YIELD_SLEEP_S = 0.0005      # real yield (0.5ms). Increase if you want "more bulletproof"

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self._deadline = 1e9
        self._nodes = 0
        self._search_count = 0

        # Transposition table: key -> (depth, flag, value)
        # flag: 0 exact, 1 lowerbound, 2 upperbound
        self._tt = {}

        # Reusable move buffers (avoid per-node list allocations as much as possible)
        self._buf_promos = []
        self._buf_caps = []
        self._buf_quiets = []

    # ---------------------------
    # Public API
    # ---------------------------
    def choose_move(self, board: chess.Board, level: int = 3):
        if board.is_game_over():
            return None, self._terminal_score_stm(board)

        time_limit_s = self._time_limit_for_level(level)
        self._begin_search(time_limit_s)

        depth, top_n, noise = self._level_params(int(level))
        moves = self._gen_ordered_moves(board)
        if not moves:
            return None, int(self._evaluate(board))

        best_mv = moves[0]
        best_score = -10**9

        # Iterative deepening at root: safer on iOS, gives frequent breakpoints.
        # If we time out, we keep last best.
        for d in range(1, depth + 1):
            if self._time_up():
                break

            alpha = -10**9
            beta = 10**9
            best_this_depth = -10**9
            best_mv_this_depth = best_mv

            # Reorder root moves each iteration by last iteration's scores (optional light touch)
            # We'll just use current ordering to keep it simple and allocation-free.

            for mv in moves:
                board.push(mv)
                score = -self._alphabeta(board, d - 1, -beta, -alpha)
                board.pop()

                if score > best_this_depth:
                    best_this_depth = int(score)
                    best_mv_this_depth = mv

                if score > alpha:
                    alpha = int(score)

                if self._time_up():
                    break

            # Commit results from this completed depth
            if best_this_depth != -10**9:
                best_mv = best_mv_this_depth
                best_score = int(best_this_depth)

        # If we never got a depth result, fall back
        if best_score == -10**9:
            return moves[0], int(self._evaluate(board))

        # Optional "human-like" noise at low levels: pick from top_n using a *cheap* re-score list.
        # We DO NOT sort big lists; we only consider a small prefix.
        if noise > 0 and top_n > 1:
            chunk = moves[:max(1, int(top_n))]
            best_mv = self._pick_noisy_best(board, chunk, depth=max(1, depth), noise=int(noise))

        return best_mv, int(best_score)

    def eval_position(self, board: chess.Board, *, level: int = 3) -> int:
        if board.is_game_over():
            return self._terminal_score_stm(board)

        time_limit_s = self._time_limit_for_level(level)
        self._begin_search(time_limit_s)

        depth, _top_n, _noise = self._level_params(int(level))
        moves = self._gen_ordered_moves(board)
        if not moves:
            return int(self._evaluate(board))

        best = -10**9
        alpha = -10**9
        beta = 10**9

        # Iterative deepening (eval-only)
        for d in range(1, depth + 1):
            if self._time_up():
                break

            best_this_depth = -10**9
            alpha = -10**9
            beta = 10**9

            for mv in moves:
                board.push(mv)
                score = -self._alphabeta(board, d - 1, -beta, -alpha)
                board.pop()

                if score > best_this_depth:
                    best_this_depth = int(score)
                if score > alpha:
                    alpha = int(score)

                if self._time_up():
                    break

            if best_this_depth != -10**9:
                best = int(best_this_depth)

        if best == -10**9:
            return int(self._evaluate(board))
        return int(best)

    # ---------------------------
    # Search lifecycle
    # ---------------------------
    def _begin_search(self, time_limit_s: float) -> None:
        self._nodes = 0
        self._deadline = time.perf_counter() + float(time_limit_s)

        # Bounded TT maintenance (stability > theoretical strength)
        self._search_count += 1
        if self._search_count % self.TT_CLEAR_EVERY_N_SEARCHES == 0:
            self._tt.clear()
        elif len(self._tt) > self.TT_MAX:
            # Hard cap: clear rather than slow shrink (more predictable)
            self._tt.clear()

    # ---------------------------
    # Internals
    # ---------------------------
    def _terminal_score_stm(self, board: chess.Board) -> int:
        if board.is_checkmate():
            return -MATE_SCORE
        return 0

    def _time_limit_for_level(self, level: int) -> float:
        time_limits = {1: 0.06, 2: 0.18, 3: 0.54, 4: 1.5, 5: 5.0}
        return float(time_limits.get(int(level), 0.22))

    def _level_params(self, level: int):
        # (depth, top_n, noise)
        if level <= 1:
            return (1, 5, 120)
        if level == 2:
            return (2, 4, 70)
        if level == 3:
            return (3, 2, 25)
        if level == 4:
            return (4, 1, 0)
        return (5, 1, 0)

    def _time_up(self) -> bool:
        """
        iOS-friendly pacing:
          - yield every ~4096 nodes using a tiny nonzero sleep
          - check deadline every ~1024 nodes
        """
        self._nodes += 1

        # Yield regularly (real yield)
        if (self._nodes & self.YIELD_MASK) == 0:
            time.sleep(self.YIELD_SLEEP_S)

        # Deadline check
        if (self._nodes & self.TIME_CHECK_MASK) == 0:
            return time.perf_counter() > self._deadline

        return False

    # ---------------------------
    # Move ordering (no sorting)
    # ---------------------------
    def _gen_ordered_moves(self, board: chess.Board):
        """
        Bucket move ordering with minimal allocation:
          promotions -> captures -> quiets

        Returns a single list (reused buffers internally).
        """
        promos = self._buf_promos
        caps = self._buf_caps
        quiets = self._buf_quiets
        promos.clear()
        caps.clear()
        quiets.clear()

        # Iterate legal moves once
        for mv in board.legal_moves:
            if mv.promotion:
                promos.append(mv)
            elif board.is_capture(mv):
                caps.append(mv)
            else:
                quiets.append(mv)

        # Promotions: keep queens first (tiny local partition, no sort)
        # Most promotions are rare; do a cheap stable arrangement.
        if promos:
            q = []
            rest = []
            for m in promos:
                if m.promotion == chess.QUEEN:
                    q.append(m)
                else:
                    rest.append(m)
            promos[:] = q + rest

        # Captures: cheap MVV-ish ordering without full sort
        # We do a small number of bins by captured piece type.
        if caps:
            bins = {chess.QUEEN: [], chess.ROOK: [], chess.BISHOP: [], chess.KNIGHT: [], chess.PAWN: [], None: []}
            for m in caps:
                cap = board.piece_at(m.to_square)
                pt = cap.piece_type if cap else None
                bins.get(pt, bins[None]).append(m)
            caps[:] = (
                bins[chess.QUEEN] + bins[chess.ROOK] + bins[chess.BISHOP] +
                bins[chess.KNIGHT] + bins[chess.PAWN] + bins[None]
            )

        # Final ordered list
        return promos + caps + quiets

    def _pick_noisy_best(self, board: chess.Board, moves, *, depth: int, noise: int):
        """
        Evaluate only a small move chunk and pick the best after adding noise.
        Uses the SAME alpha-beta, but limited to this chunk, and never sorts big lists.
        """
        scored = []
        alpha = -10**9
        beta = 10**9

        for mv in moves:
            board.push(mv)
            score = -self._alphabeta(board, depth - 1, -beta, -alpha)
            board.pop()

            scored.append((int(score), mv))
            if score > alpha:
                alpha = int(score)

            if self._time_up():
                break

        if not scored:
            return moves[0]

        # Find best with noise without sorting:
        best_mv = scored[0][1]
        best_noisy = scored[0][0] + self.rng.randint(-noise, noise)

        for s, mv in scored[1:]:
            v = int(s) + self.rng.randint(-noise, noise)
            if v > best_noisy:
                best_noisy = v
                best_mv = mv

        return best_mv

    # ---------------------------
    # Alpha-beta + TT
    # ---------------------------
    def _alphabeta(self, board: chess.Board, depth: int, alpha: int, beta: int) -> int:
        # Hard stop
        if self._time_up():
            return int(self._evaluate(board))

        # Terminal-ish
        if board.is_checkmate():
            return -MATE_SCORE
        if board.is_stalemate() or board.is_insufficient_material():
            return 0

        # Tiny extension: being in check is tactically sharp; extend 1 ply (bounded)
        if depth <= 0:
            if board.is_check():
                depth = 1
            else:
                return int(self._evaluate(board))

        # Transposition lookup
        key = board._transposition_key()  # python-chess internal zobrist key
        tt = self._tt.get((key, depth))
        if tt is not None:
            tt_depth, flag, val = tt
            if tt_depth == depth:
                if flag == 0:
                    return int(val)
                if flag == 1 and val >= beta:
                    return int(val)
                if flag == 2 and val <= alpha:
                    return int(val)

        moves = self._gen_ordered_moves(board)
        if not moves:
            return int(self._evaluate(board))

        a0 = alpha
        best = -10**9

        for mv in moves:
            board.push(mv)
            score = -self._alphabeta(board, depth - 1, -beta, -alpha)
            board.pop()

            if score > best:
                best = int(score)
            if best > alpha:
                alpha = int(best)
            if alpha >= beta:
                break

            if self._time_up():
                break

        # Store TT (bounded, safe)
        flag = 0  # exact
        if best <= a0:
            flag = 2  # upperbound
        elif best >= beta:
            flag = 1  # lowerbound

        # Keep TT small and predictable
        if len(self._tt) < self.TT_MAX:
            self._tt[(key, depth)] = (depth, flag, int(best))

        return int(best)

    # ---------------------------
    # Eval
    # ---------------------------
    def _evaluate(self, board: chess.Board) -> int:
        """
        Evaluate from side-to-move perspective.
        Uses piece_map() (already good) and PST.
        """
        score = 0
        turn = board.turn
        pm = board.piece_map()

        for sq, p in pm.items():
            v = VAL[p.piece_type]
            pst = PST[p.piece_type]
            idx = sq if p.color == chess.WHITE else chess.square_mirror(sq)
            v += pst[idx]
            score += v if p.color == turn else -v

        return int(score)
