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

MATE_SCORE = 100000


class SunfishEngine:
    """
    Tiny alpha-beta chess engine (pure Python) tuned for Pythonista / iOS stability.

    Key iOS optimizations:
      - perf_counter timing
      - time checks only every N nodes (not every node)
      - cheap move ordering (no push/is_check/pop)
      - eval via piece_map() (not scanning 64 squares)
      - occasional time.sleep(0) yield to reduce iOS watchdog risk
    """
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self._deadline = 1e9
        self._nodes = 0

    def choose_move(self, board: chess.Board, level: int = 3) -> chess.Move | None:
        if board.is_game_over():
            return None

        time_limits = {1: 0.06, 2: 0.18, 3: 0.54, 4: 1.5, 5: 5.0}
        self._nodes = 0
        self._deadline = time.perf_counter() + time_limits.get(int(level), 0.22)

        depth, top_n, noise = self._level_params(int(level))

        moves = list(board.legal_moves)
        if not moves:
            return None

        # Cheap ordering: captures/promotions first
        moves.sort(key=lambda m: self._move_order_key(board, m), reverse=True)

        scored = []
        alpha = -10**9
        beta = 10**9

        for mv in moves:
            board.push(mv)
            score = -self._alphabeta(board, depth - 1, -beta, -alpha)
            board.pop()

            scored.append((score, mv))
            if score > alpha:
                alpha = score

            if self._time_up():
                break

        if not scored:
            return moves[0]

        scored.sort(key=lambda x: x[0], reverse=True)

        best_chunk = scored[:max(1, top_n)]
        if noise > 0:
            best_chunk = [(s + self.rng.randint(-noise, noise), m) for (s, m) in best_chunk]
            best_chunk.sort(key=lambda x: x[0], reverse=True)

        return best_chunk[0][1]

    def eval_position(self, board: chess.Board, *, level: int = 3) -> int:
        """
        Returns an eval in centipawns from side-to-move perspective,
        using the same search settings as choose_move().
    
        Positive => side to move is better.
        """
        if board.is_game_over():
            if board.is_checkmate():
                return -MATE_SCORE
            return 0
    
        time_limits = {1: 0.06, 2: 0.18, 3: 0.54, 4: 1.5, 5: 5.0}
        self._nodes = 0
        self._deadline = time.perf_counter() + time_limits.get(int(level), 0.22)
    
        depth, _top_n, _noise = self._level_params(int(level))
    
        alpha = -10**9
        beta = 10**9
        best = -10**9
    
        moves = list(board.legal_moves)
        if not moves:
            return self._evaluate(board)
    
        moves.sort(key=lambda m: self._move_order_key(board, m), reverse=True)
    
        for mv in moves:
            board.push(mv)
            score = -self._alphabeta(board, depth - 1, -beta, -alpha)
            board.pop()
    
            if score > best:
                best = score
            if score > alpha:
                alpha = score
    
            if self._time_up():
                break
    
        if best == -10**9:
            return self._evaluate(board)
    
        return int(best)

    def _level_params(self, level: int):
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
        Check deadline only every 256 nodes, and occasionally yield.
        This reduces timing overhead a lot and helps iOS stay happy.
        """
        self._nodes += 1

        # Yield very occasionally (every 16384 nodes)
        if (self._nodes & 0x3FFF) == 0:
            time.sleep(0)

        # Deadline check (every 256 nodes)
        if (self._nodes & 0xFF) == 0:
            return time.perf_counter() > self._deadline

        return False

    def _move_order_key(self, board: chess.Board, mv: chess.Move) -> int:
        """
        Fast move ordering. Avoid push/is_check/pop (too expensive on iOS).
        """
        score = 0

        if mv.promotion:
            # Prefer queen promotions strongly
            score += 9_000 + (mv.promotion * 10)

        if board.is_capture(mv):
            cap = board.piece_at(mv.to_square)
            # MVV-ish: prefer capturing valuable pieces
            score += 10_000 + (VAL[cap.piece_type] if cap else 0)

        # Small preference for castling (helps early game)
        if board.is_castling(mv):
            score += 100

        return score

    def _alphabeta(self, board: chess.Board, depth: int, alpha: int, beta: int) -> int:
        if self._time_up():
            return self._evaluate(board)

        if board.is_checkmate():
            # side to move is mated => bad for side to move
            return -MATE_SCORE + (6 - depth)
        if board.is_stalemate() or board.is_insufficient_material():
            return 0

        if depth <= 0:
            return self._evaluate(board)

        moves = list(board.legal_moves)
        if not moves:
            return self._evaluate(board)

        moves.sort(key=lambda m: self._move_order_key(board, m), reverse=True)

        best = -10**9
        for mv in moves:
            board.push(mv)
            score = -self._alphabeta(board, depth - 1, -beta, -alpha)
            board.pop()

            if score > best:
                best = score
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break

            if self._time_up():
                break

        return best

    def _evaluate(self, board: chess.Board) -> int:
        """
        Evaluate from side-to-move perspective.
        Uses piece_map() to avoid scanning all 64 squares.
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

        return score
