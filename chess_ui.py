import ui
import chess
from scene import Scene, SpriteNode, ShapeNode, LabelNode, Texture

from chess_game import SuggestMove, arrow_weights

PIECE_SPRITES = {
    "P": "wp.png", "N": "wn.png", "B": "wb.png", "R": "wr.png", "Q": "wq.png", "K": "wk.png",
    "p": "bp.png", "n": "bn.png", "b": "bb.png", "r": "br.png", "q": "bq.png", "k": "bk.png",
}


class HudView:
    """Four-row HUD (turn/opening/extra/hint)."""

    def __init__(self, scene: Scene, z: int = 200):
        self.scene = scene
        self.z = z

        self.label_turn = LabelNode("")
        self.label_turn.font = ("<System>", 24)
        self.label_turn.z_position = z
        scene.add_child(self.label_turn)

        self.label_opening = LabelNode("")
        self.label_opening.font = ("<System>", 16)
        self.label_opening.z_position = z
        scene.add_child(self.label_opening)

        self.label_extra = LabelNode("")
        self.label_extra.font = ("<System>", 10)
        self.label_extra.z_position = z
        scene.add_child(self.label_extra)

        self.label_hint = LabelNode("")
        self.label_hint.font = ("<System>", 10)
        self.label_hint.z_position = z
        scene.add_child(self.label_hint)

        self._turn_override = None

    def layout(self) -> None:
        top = self.scene.size.h
        cx = self.scene.size.w / 2.0
        self.label_turn.position = (cx, top - 18)
        self.label_opening.position = (cx, top - 42)
        self.label_extra.position = (cx, top - 66)
        self.label_hint.position = (cx, top - 90)

    def set_row1_override(self, text=None) -> None:
        self._turn_override = text

    def turn_line_text(self, *, game, promo_active: bool, ai_thinking: bool) -> str:
        if self._turn_override:
            return self._turn_override
        return game.hud_row1_text(ai_thinking=ai_thinking, promo_active=promo_active)

    def update(self, *, game, ai_thinking: bool, promo_active: bool) -> None:
        self.label_turn.text = self.turn_line_text(
            game=game,
            promo_active=promo_active,
            ai_thinking=ai_thinking,
        )
        self.label_opening.text = game.hud_row2_text()
        self.label_extra.text = game.hud_row3_text()
        self.label_hint.text = game.hud_row4_text()


class PromotionOverlay:
    """Simple under-promotion UI (Q/R/B/N) drawn above the board."""

    def __init__(self, scene: Scene, z: int = 210):
        self.scene = scene
        self.z = z

        self.active = False
        self.from_sq = None
        self.to_sq = None

        self._bg = None
        self._nodes = []  # list of (piece_type, SpriteNode)

    def clear(self):
        if self._bg is not None:
            self._bg.remove_from_parent()
            self._bg = None
        for _, n in self._nodes:
            n.remove_from_parent()
        self._nodes = []
        self.active = False
        self.from_sq = None
        self.to_sq = None

    def show(self, from_sq: int, to_sq: int, piece_types):
        # piece_types are chess piece_type ints (QUEEN/ROOK/BISHOP/KNIGHT)
        self.clear()
        self.active = True
        self.from_sq = from_sq
        self.to_sq = to_sq

        # Determine promoting side from the pawn on from_sq.
        # Assumes scene.game exists by the time promotion UI is shown.
        board = self.scene.game.board
        color_prefix = "w"
        pawn = board.piece_at(from_sq)
        if pawn is not None and pawn.color == chess.BLACK:
            color_prefix = "b"

        # translucent background bar
        p = ui.Path.rect(-160, -50, 320, 100)
        bg = ShapeNode(p)
        bg.fill_color = (0.55, 0.55, 0.55, 1.0)
        bg.stroke_color = (0, 0, 0, 0)
        bg.z_position = self.z
        self.scene.add_child(bg)
        self._bg = bg

        # position above board center
        cx = self.scene.size.w / 2.0
        top = self.scene.size.h
        bg.position = (cx, top - 120)

        # icon row
        xs = [cx - 120, cx - 40, cx + 40, cx + 120]

        order = {chess.QUEEN: 0, chess.ROOK: 1, chess.BISHOP: 2, chess.KNIGHT: 3}
        pts = sorted(list(piece_types), key=lambda pt: order.get(pt, 99))

        # Assumes BoardRenderer has already created scene._tex
        texmap = self.scene._tex

        for i, pt in enumerate(pts[:4]):
            fn = {
                chess.QUEEN:  f"{color_prefix}q.png",
                chess.ROOK:   f"{color_prefix}r.png",
                chess.BISHOP: f"{color_prefix}b.png",
                chess.KNIGHT: f"{color_prefix}n.png",
            }.get(pt)
            if not fn:
                continue

            node = SpriteNode(texmap[fn])
            node.z_position = self.z + 1
            node.position = (xs[i], top - 120)
            node.size = (72, 72)
            self.scene.add_child(node)
            self._nodes.append((pt, node))

    def handle_touch(self, pos):
        """Return True if a promotion choice was selected and dispatched to the scene."""
        if not self.active:
            return False

        x, y = pos
        for pt, n in self._nodes:
            if abs(x - n.position[0]) <= n.size.w / 2 and abs(y - n.position[1]) <= n.size.h / 2:
                # Keep existing contract: PromotionOverlay dispatches selection to the scene.
                self.scene._on_promotion_choice(pt)
                return True

        # No cancel semantics here (promotion is mandatory).
        return False


class BoardRenderer:
    """Board geometry + square nodes + piece sprites + move marks and overlays."""

    def __init__(self, scene: Scene):
        self.scene = scene

        self.square_size = 0.0
        self.origin = (0.0, 0.0)
        self.flipped = False  # if True, board is rotated 180° (a1 appears at top-right)

        self.square_nodes = [None] * 64  # ShapeNode per square
        self.piece_nodes = {}            # sq -> SpriteNode
        self._mark_pool = []             # pooled ShapeNodes for dots/rings

        self.sq_light = (0.93, 0.93, 0.93, 1.0)
        self.sq_dark = (0.55, 0.55, 0.55, 1.0)

        # textures (scene can share)
        self._tex = getattr(scene, "_tex", None)
        if self._tex is None:
            self._tex = {fn: Texture(f"assets/sprites/{fn}") for fn in PIECE_SPRITES.values()}
            scene._tex = self._tex

        # marker pool
        for _ in range(32):
            n = ShapeNode()
            n.z_position = 50
            n.alpha = 0.0
            scene.add_child(n)
            self._mark_pool.append(n)

        # arrow pool: 2 arrows, each has (shaft, head)
        self._arrow_nodes = []
        for _ in range(2):
            shaft = ShapeNode()
            shaft.z_position = 30
            shaft.alpha = 0.0
            scene.add_child(shaft)

            head = ShapeNode()
            head.z_position = 31
            head.alpha = 0.0
            scene.add_child(head)

            self._arrow_nodes.append((shaft, head))

    # ---- geometry ----

    def compute_geometry(self):
        w, h = self.scene.size.w, self.scene.size.h
        board_px = min(w, h) * 0.92
        s = board_px / 8.0
        ox = (w - 8 * s) / 2.0
        oy = (h - 8 * s) / 2.0 - 30
        self.square_size = s
        self.origin = (ox, oy)

    def square_to_pos(self, sq: int):
        ox, oy = self.origin
        s = self.square_size
        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        if self.flipped:
            file = 7 - file
            rank = 7 - rank
        return (ox + (file + 0.5) * s, oy + (rank + 0.5) * s)

    def pos_to_square(self, x: float, y: float):
        ox, oy = self.origin
        s = self.square_size
        file = int((x - ox) // s)
        rank = int((y - oy) // s)
        if file < 0 or file > 7 or rank < 0 or rank > 7:
            return None
        if self.flipped:
            file = 7 - file
            rank = 7 - rank
        return chess.square(file, rank)

    def set_flipped(self, flipped: bool):
        flipped = bool(flipped)
        if self.flipped == flipped:
            return
        self.flipped = flipped

    def toggle_flipped(self):
        self.set_flipped(not self.flipped)

    # ---- drawing ----

    def draw_squares(self):
        ox, oy = self.origin
        s = self.square_size

        for sq in chess.SQUARES:
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)

            if self.flipped:
                file = 7 - file
                rank = 7 - rank

            cx = ox + (file + 0.5) * s
            cy = oy + (rank + 0.5) * s

            base = self.sq_dark if (file + rank) % 2 == 0 else self.sq_light

            node = self.square_nodes[sq]
            if node is None:
                p = ui.Path.rect(-s / 2, -s / 2, s, s)
                node = ShapeNode(p)
                node.z_position = 0
                self.scene.add_child(node)
                self.square_nodes[sq] = node
            else:
                node.path = ui.Path.rect(-s / 2, -s / 2, s, s)

            node.position = (cx, cy)
            node.fill_color = base
            node.stroke_color = base
            node.line_width = 0

    def sync_pieces(self, board: chess.Board):
        desired = {}
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece:
                fn = PIECE_SPRITES.get(piece.symbol())
                if fn:
                    desired[sq] = fn

        for sq in list(self.piece_nodes.keys()):
            if sq not in desired:
                self.piece_nodes[sq].remove_from_parent()
                del self.piece_nodes[sq]

        for sq, fn in desired.items():
            node = self.piece_nodes.get(sq)
            if node is None:
                node = SpriteNode(self._tex[fn])
                node.z_position = 10
                node._fn = fn
                self.scene.add_child(node)
                self.piece_nodes[sq] = node
            else:
                if getattr(node, "_fn", None) != fn:
                    node.texture = self._tex[fn]
                    node._fn = fn

            node.position = self.square_to_pos(sq)
            node.size = (self.square_size * 0.9, self.square_size * 0.9)

    def _reset_square_colors(self):
        for sq in chess.SQUARES:
            n = self.square_nodes[sq]
            if n is None:
                continue
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            base = self.sq_dark if (file + rank) % 2 == 0 else self.sq_light
            n.fill_color = base
            n.stroke_color = base
            n.line_width = 0

    def clear_move_marks(self):
        for n in self._mark_pool:
            n.alpha = 0.0

    def show_legal_marks(self, board: chess.Board, from_sq):
        self.clear_move_marks()
        if from_sq is None:
            return

        dot_r = self.square_size * 0.12
        ring_r = self.square_size * 0.30
        ring_w = max(2, self.square_size * 0.06)

        i = 0
        for m in board.legal_moves:
            if m.from_square != from_sq:
                continue
            if i >= len(self._mark_pool):
                break

            to_sq = m.to_square
            cx, cy = self.square_to_pos(to_sq)
            node = self._mark_pool[i]
            i += 1

            is_capture = board.is_capture(m)

            if is_capture:
                node.path = ui.Path.oval(-ring_r, -ring_r, 2 * ring_r, 2 * ring_r)
                node.fill_color = (0, 0, 0, 0)
                node.stroke_color = (0.9, 0.2, 0.2, 0.85)
                node.line_width = ring_w
            else:
                node.path = ui.Path.oval(-dot_r, -dot_r, 2 * dot_r, 2 * dot_r)
                node.fill_color = (0.1, 0.6, 1.0, 0.55)
                node.stroke_color = (0, 0, 0, 0)
                node.line_width = 0

            node.position = (cx, cy)
            node.alpha = 1.0

    # ---- suggest arrows ----

    def clear_suggest_arrows(self):
        for shaft, head in self._arrow_nodes:
            shaft.alpha = 0.0
            head.alpha = 0.0

    def _arrow_paths(self, dx_scene: float, dy_scene: float, head_len: float, head_w: float, *, shaft_cut: float = 0.5):
        """
        Build (shaft_path, head_path, shaft_mid_scene, head_tip_local)

        - dx_scene, dy_scene are in SCENE coords (y up), from->to.
        - Returned paths are in PATH coords (UIKit-ish y down), centered for ShapeNode stability.
        - shaft_cut is fraction of head_len to shorten the shaft so it meets the head nicely.
        """
        dist = (dx_scene * dx_scene + dy_scene * dy_scene) ** 0.5
        if dist < 1e-6:
            return None, None, None, None

        # Unit direction in SCENE coords (y up)
        ux = dx_scene / dist
        uy = dy_scene / dist

        # Convert to PATH coords (y down)
        uxp = ux
        uyp = -uy

        # Perp in PATH coords
        px = -uyp
        py = uxp

        # ---------------- SHAFT ----------------
        cut = head_len * float(shaft_cut)

        # Shortened endpoint vector in SCENE coords
        sx_scene = dx_scene - ux * cut
        sy_scene = dy_scene - uy * cut

        # Midpoint for positioning shaft node in SCENE coords
        shaft_mid_scene = (sx_scene * 0.5, sy_scene * 0.5)

        # Path vector in PATH coords (y down)
        sxp = sx_scene
        syp = -sy_scene

        shaft_path = ui.Path()
        shaft_path.move_to(-sxp * 0.5, -syp * 0.5)
        shaft_path.line_to(sxp * 0.5, syp * 0.5)

        # ---------------- HEAD ----------------
        # Triangle with TIP at (0,0), base behind tip along -u
        tipx, tipy = 0.0, 0.0
        basex = -uxp * head_len
        basey = -uyp * head_len

        leftx = basex + px * (head_w * 0.5)
        lefty = basey + py * (head_w * 0.5)
        rightx = basex - px * (head_w * 0.5)
        righty = basey - py * (head_w * 0.5)

        # BBox-centering compensation (prevents angle-dependent drift)
        minx = min(tipx, leftx, rightx)
        maxx = max(tipx, leftx, rightx)
        miny = min(tipy, lefty, righty)
        maxy = max(tipy, lefty, righty)
        cx = (minx + maxx) * 0.5
        cy = (miny + maxy) * 0.5

        tipx2, tipy2 = tipx - cx, tipy - cy
        leftx2, lefty2 = leftx - cx, lefty - cy
        rightx2, righty2 = rightx - cx, righty - cy

        head_path = ui.Path()
        head_path.move_to(tipx2, tipy2)
        head_path.line_to(leftx2, lefty2)
        head_path.line_to(rightx2, righty2)
        head_path.close()

        head_tip_local = (tipx2, tipy2)
        return shaft_path, head_path, shaft_mid_scene, head_tip_local

    def _normalize_uci(self, uci: str, board: chess.Board) -> str:
        """Best-effort UCI normalization (kept tiny, no debug prints)."""
        u = (uci or "").strip()
        u = u.replace("–", "-").replace("—", "-").replace("−", "-")

        uu = u.upper()
        if uu in ("O-O", "0-0"):
            return "e1g1" if board.turn == chess.WHITE else "e8g8"
        if uu in ("O-O-O", "0-0-0"):
            return "e1c1" if board.turn == chess.WHITE else "e8c8"
        return u

    def draw_suggest_arrows(self, board: chess.Board):
        self.clear_suggest_arrows()

        # NOTE: this assumes the scene establishes `scene.game` as an invariant.
        game = self.scene.game
        if not game.show_sugg_arrows:
            return

        sugg = game.suggested_moves or []
        if not sugg:
            return

        parsed: list[tuple[SuggestMove, chess.Move]] = []
        for sm in sugg[:2]:
            uci = self._normalize_uci(getattr(sm, "uci", ""), board)
            try:
                mv = chess.Move.from_uci(uci)
            except Exception:
                continue

            # Keep one cheap safety check
            if mv in board.legal_moves:
                parsed.append((sm, mv))

        if not parsed:
            return

        best_sm = parsed[0][0]
        second_sm = parsed[1][0] if len(parsed) > 1 else None
        w1, w2 = arrow_weights(best_sm, second_sm)
        weights = [w1, w2]

        for i, (pair, w) in enumerate(zip(parsed, weights)):
            sm, mv = pair
            shaft, head = self._arrow_nodes[i]

            SIZE_STRENGTH = 1.8
            size_mul = w ** SIZE_STRENGTH

            p_from = self.square_to_pos(mv.from_square)
            p_to = self.square_to_pos(mv.to_square)

            dx = p_to[0] - p_from[0]
            dy = p_to[1] - p_from[1]

            alpha = 0.10 + 0.30 * w
            thickness = max(2.0, self.square_size * 0.10) * (0.6 + 0.8 * size_mul)

            src = getattr(sm, "source", "cloud")
            if src == "cloud":
                color = (0.2, 0.7, 1.0)
            elif src == "book":
                color = (0.2, 1.0, 0.5)
            else:
                color = (1.0, 0.6, 0.2)

            head_len = self.square_size * (0.28 + 0.22 * size_mul)
            head_w = head_len * (1.0 + 0.5 * size_mul)

            shaft_path, head_path, shaft_mid_scene, head_tip_local = self._arrow_paths(
                dx_scene=dx,
                dy_scene=dy,
                head_len=head_len,
                head_w=head_w,
                shaft_cut=1.0,
            )
            if shaft_path is None:
                continue

            # Shaft
            shaft.position = (p_from[0] + shaft_mid_scene[0], p_from[1] + shaft_mid_scene[1])
            shaft.path = shaft_path
            shaft.stroke_color = (color[0], color[1], color[2], alpha)
            shaft.fill_color = (0, 0, 0, 0)
            shaft.line_width = thickness
            shaft.alpha = 1.0

            # Head: position so TIP lands exactly at p_to
            tipx2, tipy2 = head_tip_local
            head.position = (p_to[0] - tipx2, p_to[1] + tipy2)
            head.path = head_path
            head.fill_color = (color[0], color[1], color[2], alpha)
            head.stroke_color = (0, 0, 0, 0)
            head.alpha = 1.0

    # ---- overlays ----

    def refresh_overlays(self, board: chess.Board, selected):
        self._reset_square_colors()

        if board.move_stack:
            m = board.peek()
            for sq in (m.from_square, m.to_square):
                n = self.square_nodes[sq]
                if n:
                    n.fill_color = (1.0, 0.9, 0.2, 0.25)

        if selected is not None:
            n = self.square_nodes[selected]
            if n:
                n.stroke_color = (0.1, 0.6, 1.0, 0.95)
                n.line_width = max(2, self.square_size * 0.06)

        if board.is_check():
            ksq = board.king(board.turn)
            if ksq is not None:
                n = self.square_nodes[ksq]
                if n:
                    n.fill_color = (1.0, 0.2, 0.2, 0.22)

        self.draw_suggest_arrows(board)
        self.show_legal_marks(board, selected)
