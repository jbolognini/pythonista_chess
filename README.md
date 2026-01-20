# Chess Practice App — Progress & Design Notes

## High-Level Overview

This app is a chess training and play environment with a strong focus on opening practice that blends:

- free play vs AI (Sunfish-based)
- structured opening training (guided, corrective)
- optional cloud guidance (Lichess cloud eval) + local book hints
- human-oriented learning (ideas, traps, punishments)

The core goal is not just to memorize moves, but to build understanding of:
- opening ideas
- typical structures
- tactical motifs
- common beginner mistakes and how they are punished

---

## Architectural Mental Model

### Centralization + Separation of Responsibilities

The code is organized around a **single source of truth** for chess rules, practice enforcement, and “what the UI should say”:

**Game logic (`ChessGame`)**
- Owns the authoritative `chess.Board`
- Owns opening selection + practice model compilation + expected-move enforcement
- Owns theory/book lookup helpers
- Owns move application methods (human/AI), undo/redo stacks, import/export
- Produces HUD strings (row 1–4) so UI can stay dumb

**Scene orchestration (`ChessScene`)**
- Owns rendering objects (board, HUD, promotion overlay)
- Owns threading and “background work” lifecycle:
  - AI move worker
  - cloud eval request scheduling
- Owns *state transitions* after position changes (refresh overlays, clear selection, queue evaluations, etc.)
- Calls into `ChessGame` for all chess/training decisions

**UIKit / views (`game_view.py`)**
- Owns top bar + settings/import/export sheets
- Treats the Scene as the interactive “game surface”
- Reads only safe, public state via scene/game methods (not internals)

**Rendering (`chess_ui.py`)**
- Owns geometry and drawing (squares, pieces, legal marks, suggestion arrows)
- No chess/training decisions; it renders whatever `ChessGame` and `ChessScene` decide

---

## Current Feature Set

### Play & Interaction
- Tap-to-select + tap-to-move
- Legal move dots and capture rings
- Board flip (play as White/Black perspective)
- Undo / redo / reset
- Import PGN or FEN; export PGN or FEN

### Promotion
- Underpromotion chooser (Q/R/B/N) shown only when required
- Move is only committed after selecting a promotion piece

### AI (Sunfish)
- Local AI opponent powered by a more robust Sunfish engine
- Adjustable difficulty (1–5)
- AI can play either side

### Opening book + “theory”
- Polyglot book support for non-practice play (“in theory / out of book”)
- Book randomness control (weighted-ish selection)

### Cloud guidance (Lichess)
- Optional Lichess cloud evaluation
- Multi-PV display in HUD
- Suggestion arrows can be driven by:
  - cloud PVs (when enabled and available)
  - local book moves (fallback / when cloud disabled)

### Suggestion arrows
- Up to two arrows rendered with relative weighting (best vs second-best)
- Arrow colors encode the source (cloud/book/engine)
- Centralized suggestion generation in `ChessGame.compute_suggest_moves()`

---

## Opening Practice System

### Practice Mode Concept

When an opening is selected, the game enters practice mode, which provides:

- guidance from move 0 (including the very first move)
- structured opening lines
- controlled branching
- instructional notes explaining why moves are played

Practice is opening-specific and tiered (e.g. beginner vs master).

### Practice Data Model

Openings are defined using a line-based model, not a hand-authored move tree.

Each opening contains:
- a human-readable title
- one or more tiers (currently beginner + master)
- each tier is a list of training items

Each training item contains:
- a unique ID
- tags (solid, trap, punishment, etc.)
- a full SAN move sequence
- per-move instructional notes explaining intent or punishment

This format is:
- easy to author
- easy to expand incrementally
- easy to reason about during debugging

Lines are compiled at runtime into a position-key → expected-moves map.

### Practice Phases

The game tracks a conceptual practice phase:

- FREE — no opening selected
- READY — opening selected, guidance available
- IN THEORY — past practice model but still in book
- OUT OF THEORY — no known continuation (engine play)

The phase influences:
- whether guidance is shown
- whether cloud eval is requested
- what the HUD displays

### Intended Training Behavior

#### Correct Move
- The move is applied
- Training continues
- No feedback is shown

#### Incorrect Move (Current Behavior)
- If the current position is covered by the practice model, unexpected (but legal) moves are **blocked**
- A short “miss” note is latched for the HUD so the user can retry immediately
- The board remains unchanged

This mirrors how humans learn best:
mistake → explanation → correction → repetition

---

## Current State (What Works)

- Opening practice infrastructure exists
- Practice lines compile correctly
- Expected moves can be detected per position
- Instructional notes are stored per move
- Practice enforcement can block incorrect moves (when the practice model applies)
- HUD can display expected moves (when hints are on or after a miss)
- AI integrates with practice openings (forced replies when applicable)
- Cloud eval + local book feed suggestion arrows
- Import/export and standard play loop are stable

---

## Current Gaps / What Is Incomplete

### Opening Trainers
- The opening trainer content is still incomplete / under active authoring
- Coverage depth varies by opening and tier
- Some “punish common mistakes” lines still need to be filled out and validated

---

## Future Ideas (User-Owned)

- Board editor
- Time controls
- AI personality
- Permanent settings stored to a JSON state file

## Additional Standard Chess App Features (Not Yet Implemented)

- Move list / notation panel with clickable navigation
- Step backward / forward through moves
- Jump to start / end of game
- Analysis mode for exploring variations without affecting the main game
- Evaluation bar showing side advantage
- Post-game summary (opening reached, theory exit point, major mistakes)
- Move quality labels (inaccuracy / mistake / blunder)
- Per-opening progress tracking and completion stats
- Board color themes and highlight customization
- Multiple piece sets
- Optional sound effects and haptic feedback
- Local save / load of games and sessions
- Annotated PGN export with instructional comments
- Quick copy / paste of FEN and PGN
- Automatic board flip based on side to move
- Non-clocked time tracking per side
- Optional threat or attacked-piece highlighting

---

## Module Map (Current Files)

### app.py
- App entry point / presentation glue
- Creates the main UI view and presents it

### game_view.py
- Top-level UIKit UI: toolbar + modal sheets
- Settings sheet (vs AI, AI side/level, opening practice selection, tier, arrows, cloud)
- Import PGN/FEN sheet and export PGN/FEN sheet
- Owns enabling/disabling toolbar buttons based on scene/game state

### chess_scene.py
- The orchestrator for gameplay:
  - constructs `ChessGame`, engines, and renderers
  - owns AI worker loop + cloud eval scheduling
  - owns centralized “after move / after position changed” state transitions
  - owns promotion flow (show chooser, commit on selection)
- Keeps UI responsive by doing AI/cloud work off the main thread

### chess_game.py
- Core rules + training model:
  - authoritative board state
  - practice model compilation, enforcement, feedback strings
  - book lookup helpers and suggestion generation
  - undo/redo, reset, import/export
  - centralized HUD row text generators

### chess_ui.py
- Rendering / drawing primitives:
  - board layout + square nodes
  - piece sprite syncing
  - legal move marks (dots/rings)
  - suggestion arrows (up to two) drawn from `game.suggested_moves`
  - promotion overlay UI (Q/R/B/N)

### sunfish_engine.py
- Local AI engine (Sunfish-derived)
- Handles search/evaluation and difficulty scaling

### lichess_engine.py
- Cloud evaluation integration (Lichess cloud analysis)
- Returns multi-PV results used for HUD text + suggestion arrows
- Includes local caching to avoid repeated network calls for the same position

### opening_book.py
- Local opening-book helper (Polyglot)
- Lightweight caching layer for book lookups to reduce repeated disk reads
- Used as a fast “theory” fallback when cloud is disabled/unavailable

### openings.py
- Opening library + practice line definitions
- Functions to list openings, titles, and tiered practice items
- Stores the training content (SAN lines + notes)
