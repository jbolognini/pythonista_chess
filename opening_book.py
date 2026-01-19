import random
import chess
import chess.polyglot

class OpeningBook:
    def __init__(self, book_path: str, seed: int | None = None):
        self.book_path = book_path
        self.rng = random.Random(seed)

    def pick(self, board: chess.Board, randomness: float = 0.2) -> chess.Move | None:
        # randomness: 0 = always highest weight, 1 = fully weighted random
        try:
            with chess.polyglot.open_reader(self.book_path) as reader:
                entries = list(reader.find_all(board))
        except Exception:
            return None

        if not entries:
            return None

        # Sort by weight (higher = more common/better in the book)
        entries.sort(key=lambda e: e.weight, reverse=True)

        if randomness <= 0:
            return entries[0].move

        # Weighted random among top moves
        top = entries[: min(8, len(entries))]
        weights = [e.weight for e in top]
        # Blend: sometimes choose best, sometimes sample
        if self.rng.random() > randomness:
            return top[0].move
        return self.rng.choices([e.move for e in top], weights=weights, k=1)[0]
