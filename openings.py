# openings.py
# Practice opening training data + helpers.
#
# Format:
# PRACTICE_OPENINGS[opening_key] = {
#     "title": ...,
#     "beginner": [ {id,tags,moves,notes}, ... ],
#     "master_addon": [ ... ],
# }
#
# Notes are indexed by ply (0-based within the line).

OPENING_TITLES = {
    "italian": "Italian Game",
    "scotch": "Scotch Game",
    "vienna": "Vienna Game",
    "kings_gambit": "King's Gambit",
    "danish_gambit": "Danish Gambit",
    "smith_morra": "Smith-Morra Gambit (vs Sicilian)",
    "london": "London System",
    "jobava_london": "Jobava London",
    "colle": "Colle System",
    "trompowsky": "Trompowsky Attack",
    "queens_gambit": "Queen's Gambit (as White)",
    "ruy_lopez": "Ruy Lopez",
    "scandinavian": "Scandinavian Defense",
    "caro_kann": "Caro-Kann Defense",
    "french": "French Defense",
    "pirc_modern": "Pirc/Modern (...d6 ...Nf6 ...g6)",
    "stafford": "Stafford Gambit (trap line)",
    "traxler": "Traxler Counterattack (Wilkes-Barre)",
    "dutch": "Dutch Defense",
    "kings_indian": "King's Indian Defense",
    "benoni": "Benoni Defense",
    "slav": "Slav Defense",
    "qgd": "Queen's Gambit Declined",
}

OPENING_ORDER = [
    "italian",
    "scotch",
    "vienna",
    "kings_gambit",
    "danish_gambit",
    "smith_morra",
    "london",
    "jobava_london",
    "colle",
    "trompowsky",
    "queens_gambit",
    "ruy_lopez",
    "scandinavian",
    "caro_kann",
    "french",
    "pirc_modern",
    "stafford",
    "traxler",
    "dutch",
    "kings_indian",
    "benoni",
    "slav",
    "qgd",
]

def opening_options():
    return [("Free play", None)] + [(OPENING_TITLES[k], k) for k in OPENING_ORDER]

def practice_opening_title(opening_key: str | None) -> str | None:
    if not opening_key:
        return None
    return OPENING_TITLES.get(opening_key, str(opening_key))

def practice_items(opening_key: str, *, tier: str = "beginner") -> list[dict]:
    info = PRACTICE_OPENINGS.get(opening_key) or {}
    base = list(info.get("beginner", []))
    if (tier or "beginner").lower() in ("master", "advanced"):
        base += list(info.get("master_addon", []))
    return base

def practice_lines(opening_key: str, *, tier: str = "beginner") -> list[list[str]]:
    return [it.get("moves", []) for it in practice_items(opening_key, tier=tier)]

PRACTICE_OPENINGS: dict[str, dict] = {}

PRACTICE_OPENINGS["italian"] = {
    "title": OPENING_TITLES["italian"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","Nf3","Nc6","Bc4","Bc5"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","Nf3","Nc6","Bc4","Nf6"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["scotch"] = {
    "title": OPENING_TITLES["scotch"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","Nf3","Nc6","d4","exd4","Nxd4"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["vienna"] = {
    "title": OPENING_TITLES["vienna"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","Nc3"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","Nc3","Nf6","f4"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["kings_gambit"] = {
    "title": OPENING_TITLES["kings_gambit"],
    "beginner": [
        {
            "id": "kg_solid_01_main_accept",
            "tags": ["solid", "accepted", "initiative"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","g5","h4",
                "g4","Ne5","Nf6"
            ],
            "notes": {
                0: "Claim the center and open lines for fast development.",
                2: "This is the gambit: sacrifice a pawn to speed development and open files/diagonals.",
                4: "Develop with tempo: you immediately attack f4 and prepare quick castling.",
                6: "Hit the pawn chain and open the h-file/lines. Slow play lets Black consolidate.",
                8: "Centralize the knight with threats; you’re aiming at f7 and weak squares.",
            },
        },

        {
            "id": "kg_solid_02_classical_decline",
            "tags": ["solid", "declined", "development"],
            "moves": [
                "e4","e5","f4","Bc5","Nf3","d6","c3",
                "Nf6","d4","exd4"
            ],
            "notes": {
                0: "Standard strong start: grab space and free your pieces.",
                2: "Offer the gambit; if declined, you still get a space/initiative game.",
                4: "Develop and prepare to castle; don’t chase ghosts yet.",
                6: "Build a strong center and prepare d4; structure > tactics here.",
                8: "Take the center; you want active pieces and open lines.",
            },
        },

        {
            "id": "kg_solid_03_falkbeer_basic",
            "tags": ["solid", "countergambit", "center"],
            "moves": [
                "e4","e5","f4","d5","exd5","e4","d3",
                "Nf6","Nc3","Bb4"
            ],
            "notes": {
                0: "Normal central claim; it supports fast piece play later.",
                2: "Still the gambit offer — but now you must respect central counterplay.",
                4: "Accept the pawn when it’s safe; removing Black’s center is often correct.",
                6: "Keep it solid: d3 stabilizes the center and opens your bishop.",
                8: "Develop and fight for control; don’t try to “win instantly” vs the countergambit.",
            },
        },

        {
            "id": "kg_solid_04_schallopp_line",
            "tags": ["solid", "Nf6", "structure"],
            "moves": [
                "e4","e5","f4","Nf6","fxe5","Nxe4","Nf3","d5","d3","Nc5"
            ],
            "notes": {
                0: "Solid: take center space and free your pieces.",
                2: "Gambit offer; you’re aiming for initiative, not hoarding pawns.",
                4: "When Black hits f4 with Nf6, taking e5 is a common practical choice.",
                6: "Develop and challenge the centralized knight; don’t panic.",
                8: "Keep the position stable; d3 supports your center and prepares Bxf4 ideas.",
            },
        },

        {
            "id": "kg_solid_05_bishop_check_defense",
            "tags": ["solid", "check_defense", "accepted"],
            "moves": [
                "e4","e5","f4","exf4","Bc4","Qh4+","Kf1","g5","Nf3","Qh5"
            ],
            "notes": {
                0: "Central control first; you’re building an attack base.",
                2: "Gambit offer for open lines and quick development.",
                4: "Bc4 is the attacking bishop: pressure f7 and speed development.",
                6: "Kf1 is the safe fix: you avoid weakening with g3 and keep your attack alive.",
                8: "Develop with tempo; you want to hit f4 and get pieces out fast.",
            },
        },

        {
            "id": "kg_solid_06_muzio_feel",
            "tags": ["solid", "sacrifice", "attack"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","g5","Bc4","g4","O-O","gxf3"
            ],
            "notes": {
                0: "Normal start; you’ll trade pawn for initiative soon.",
                2: "Gambit: you’re buying speed and open lines.",
                4: "Develop and target the f4 pawn.",
                6: "Bc4 points at f7 and makes castling possible soon.",
                8: "Castling is an attacking move here: rook joins the game and king is safer.",
            },
        },

        {
            "id": "kg_solid_07_modern_accept_d6",
            "tags": ["solid", "accepted", "setup"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","d6","d4","g5","Bc4","Bg7"
            ],
            "notes": {
                0: "Center first; it makes your pieces stronger later.",
                2: "Offer gambit: open lines + initiative.",
                4: "Develop and attack the f4 pawn.",
                6: "Take the center; the gambit works best when you control central squares.",
                8: "Active bishop: pressure f7 and aim at tactics if Black is slow.",
            },
        },

        {
            "id": "kg_solid_08_decline_with_Nc6",
            "tags": ["solid", "declined", "development"],
            "moves": [
                "e4","e5","f4","Nc6","Nf3","Bc5","c3","d6","d4","Bb6"
            ],
            "notes": {
                0: "Normal start.",
                2: "Gambit offer; even if declined you get a strong initiative setup.",
                4: "Develop; don’t overextend the pawn structure too early.",
                6: "c3 supports d4 and builds a strong center.",
                8: "d4 is your main plan: claim space and open lines for your pieces.",
            },
        },

        {
            "id": "kg_punish_01_greedy_second_pawn",
            "tags": ["punish", "accepted", "greedy", "initiative"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","g5","Bc4","g4","O-O","gxf3","Qxf3"
            ],
            "notes": {
                0: "Start normally; you want fast development.",
                2: "Gambit: trade pawn for initiative.",
                4: "Nf3 hits f4 and accelerates development.",
                6: "Bc4 points at f7; you’re building an attack.",
                8: "Castle to activate the rook and keep your king safe.",
                10: "Qxf3: regain material and keep pressure; greedy pawn grabs let you catch up in development.",
            },
        },

        {
            "id": "kg_punish_02_hasty_queen_check",
            "tags": ["punish", "check", "tempo"],
            "moves": [
                "e4","e5","f4","exf4","Bc4","Qh4+","Kf1",
                "Nc6","Nf3","Qh6"
            ],
            "notes": {
                0: "Standard start.",
                2: "Gambit offer; you’re aiming for speed.",
                4: "Bc4: attack f7 and develop with purpose.",
                6: "Kf1: don’t create weaknesses; you’ll punish the queen’s time-waste with development.",
                8: "Nf3: develop and hit the queen/center; queen sorties are punished by tempos.",
            },
        },

        {
            "id": "kg_punish_03_black_ignores_center",
            "tags": ["punish", "center", "initiative"],
            "moves": [
                "e4","e5","f4","Bc5","Nf3","d6","d4",
                "exd4","c3","Bb6"
            ],
            "notes": {
                0: "Central control is your platform.",
                2: "Still the gambit offer — if declined, you take space.",
                4: "Develop; you want to open the center while Black’s king is still in the middle.",
                6: "d4: punish slow play by opening lines and grabbing the center.",
                8: "c3: rebuild the center and open lines; you’re gaining tempo and space.",
            },
        },

        {
            "id": "kg_punish_04_bad_defense_after_h4",
            "tags": ["punish", "accepted", "attack"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","g5","h4",
                "g4","Ne5","d6","Bc4"
            ],
            "notes": {
                0: "Normal start.",
                2: "Gambit offer for initiative.",
                4: "Develop and attack f4.",
                6: "h4: hit the pawn chain; you’re trying to open files and diagonals.",
                8: "Ne5: centralized knight with threats; punishes loosening moves like ...g4.",
                10: "Bc4: bring another piece into the attack; development beats pawn-grabbing.",
            },
        },

        {
            "id": "kg_punish_05_falkbeer_mistake_slow",
            "tags": ["punish", "countergambit", "tempo"],
            "moves": [
                "e4","e5","f4","d5","exd5","e4","Qe2",
                "Nf6","Nc3","Bb4"
            ],
            "notes": {
                0: "Normal start.",
                2: "Gambit offer; expect counterplay.",
                4: "Take on d5 to reduce Black’s central punch.",
                6: "Qe2 supports e4 pressure and keeps you flexible; you’re preventing easy tricks.",
                8: "Nc3: develop and fight for key central squares.",
            },
        },

        {
            "id": "kg_punish_06_early_black_knight_harass",
            "tags": ["punish", "Nf6", "practical"],
            "moves": [
                "e4","e5","f4","Nf6","Nf3","Nxe4","d3",
                "Nf6","Nxe5"
            ],
            "notes": {
                0: "Normal start; keep your pieces ready.",
                2: "Gambit offer; you’re aiming for initiative.",
                4: "Nf3: develop first—don’t chase pawns while Black hits your center.",
                6: "d3: kick the centralized knight and open your bishop; punish overextension.",
                8: "Nxe5: regain material when it’s safe; the point is development + tactical cleanup.",
            },
        },

        {
            "id": "kg_punish_07_bad_black_fianchetto",
            "tags": ["punish", "slow_defense", "initiative"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","g6","d4",
                "Bg7","Bc4","d6"
            ],
            "notes": {
                0: "Standard start.",
                2: "Gambit offer.",
                4: "Develop and attack the extra pawn.",
                6: "d4: punish slow setups by taking the center and opening lines.",
                8: "Bc4: pressure f7 and keep the attack simple and direct.",
            },
        },

        {
            "id": "kg_punish_08_overprotect_pawn_chain",
            "tags": ["punish", "pawn_chain", "initiative"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","g5","Bc4",
                "Bg7","h4","h6"
            ],
            "notes": {
                0: "Normal start.",
                2: "Gambit offer; you’re buying speed.",
                4: "Develop and attack f4.",
                6: "Bc4: build pressure on f7 and speed up castling.",
                8: "h4: hit the pawn chain; don’t let Black lock you out with ...g4 forever.",
            },
        },

        {
            "id": "kg_punish_09_decline_with_weird_defense",
            "tags": ["punish", "declined", "space"],
            "moves": [
                "e4","e5","f4","d6","Nf3","exf4","d4",
                "Nf6","Bc4","Be7"
            ],
            "notes": {
                0: "Standard start.",
                2: "Gambit offer.",
                4: "Develop; don’t overreact to odd move orders.",
                6: "d4: claim the center and open lines—this is how you punish passive defense.",
                8: "Bc4: point at f7 and keep development rolling.",
            },
        },

        {
            "id": "kg_punish_10_bad_black_queen_grab",
            "tags": ["punish", "queen", "tempo"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","Qf6","Nc3",
                "c6","d4","d6"
            ],
            "notes": {
                0: "Standard start.",
                2: "Gambit offer.",
                4: "Develop and attack the pawn.",
                6: "Nc3: develop with tempo ideas; early queen moves invite rapid development.",
                8: "d4: build the big center and open lines while their queen is exposed.",
            },
        },

        {
            "id": "kg_punish_11_too_early_attack_on_f4",
            "tags": ["punish", "initiative", "tempo"],
            "moves": [
                "e4","e5","f4","exf4","Bc4","d5","Bxd5",
                "Qh4+","Kf1"
            ],
            "notes": {
                0: "Normal start.",
                2: "Gambit offer.",
                4: "Bc4: develop aggressively and aim at f7.",
                6: "Bxd5: when possible, win a central pawn and keep initiative (punish ...d5 timing).",
                8: "Kf1: safest response; keep the attack alive and don’t weaken with unnecessary pawn pushes.",
            },
        },

        {
            "id": "kg_punish_12_simple_center_crush",
            "tags": ["punish", "center", "development"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","d5","exd5",
                "Nf6","Bb5+"
            ],
            "notes": {
                0: "Start normally.",
                2: "Gambit offer.",
                4: "Develop and attack f4.",
                6: "exd5: reduce Black’s counterplay; opening lines is your friend.",
                8: "Bb5+: develop with tempo—checks that gain development are ideal in gambits.",
            },
        },

        # --- King's Gambit Knight Sacrifice after f6 lines
        {
            "id": "kg_f6_best_defense_nf6",
            "tags": ["punish", "accepted"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","g5","h4","f6",
                "Nxg5","fxg5","Qh5+","Ke7",
                "Qxg5+","Nf6","e5","d5","exf6+"
            ],
            "notes": {
                0: "Take space and prepare fast development.",
                2: "Open lines and create attacking chances.",
                4: "Develop with tempo and aim at f4.",
                6: "Challenge the pawn chain immediately.",
                8: "Key sacrifice to expose the king.",
                10: "Force the king into the open.",
                12: "Regain material with check.",
                14: "Push e5 to keep the king and pieces tied up.",
                16: "Open more lines and win material with check."
            },
        },

        {
            "id": "kg_f6_mistake_ke8",
            "tags": ["punish", "accepted"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","g5","h4","f6",
                "Nxg5","fxg5","Qh5+","Ke7",
                "Qxg5+","Ke8","Qh5+","Ke7","Qe5+"
            ],
            "notes": {
                0: "Control the center to support the attack.",
                2: "The gambit opens files for active play.",
                4: "Develop toward the kingside.",
                6: "Open the position before Black can stabilize.",
                8: "Sacrifice to force king exposure.",
                10: "Start the forcing sequence.",
                12: "Keep checks coming while winning material.",
                14: "Repeat the check to deny development.",
                16: "Centralize the queen with check."
            },
        },

        {
            "id": "kg_f6_mistake_kf7",
            "tags": ["punish", "accepted"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","g5","h4","f6",
                "Nxg5","fxg5","Qh5+","Ke7",
                "Qxg5+","Kf7","Bc4+","Ke7","Qf5"
            ],
            "notes": {
                0: "Build a strong base for an attack.",
                2: "Open lines and gain initiative.",
                4: "Develop with threats.",
                6: "Prevent Black from locking the kingside.",
                8: "Open the king position.",
                10: "Force the king to move.",
                12: "Convert with a forcing capture.",
                14: "Develop with check to keep momentum.",
                16: "Threaten decisive material loss."
            },
        },

        {
            "id": "kg_f6_mistake_kd6",
            "tags": ["punish", "accepted"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","g5","h4","f6",
                "Nxg5","fxg5","Qh5+","Ke7",
                "Qxg5+","Kd6","Bc4","Qe7","Bxf4"
            ],
            "notes": {
                0: "Central space helps attacking play.",
                2: "Open files favor active pieces.",
                4: "Develop quickly and aim forward.",
                6: "Open the position early.",
                8: "Break open the king’s shelter.",
                10: "Drive the king into danger.",
                12: "Take material with tempo.",
                14: "Develop another attacker.",
                16: "Win more material while the king is exposed."
            },
        },

        {
            "id": "kg_f6_mistake_nc6",
            "tags": ["punish", "accepted"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","g5","h4","f6",
                "Nxg5","fxg5","Qh5+","Ke7",
                "Qxg5+","Nc6","Bc4","d6","Qxf4"
            ],
            "notes": {
                0: "Take central space early.",
                2: "Open attacking lines.",
                4: "Develop toward the king.",
                6: "Open the pawn structure.",
                8: "Sacrifice to force weaknesses.",
                10: "Force the king out.",
                12: "Recover material with check.",
                14: "Develop another attacker.",
                16: "Win material while staying active."
            },
        },

        {
            "id": "kg_f6_mistake_d6",
            "tags": ["punish", "accepted"],
            "moves": [
                "e4","e5","f4","exf4","Nf3","g5","h4","f6",
                "Nxg5","fxg5","Qh5+","Ke7",
                "Qxg5+","d6","Qxf4","Be6","Nc3"
            ],
            "notes": {
                0: "Establish a strong center.",
                2: "Open lines for the pieces.",
                4: "Develop with tempo.",
                6: "Break the pawn chain early.",
                8: "Expose the king with a sacrifice.",
                10: "Force the king into the open.",
                12: "Win back material with check.",
                14: "Pick up another pawn with tempo.",
                16: "Finish development with a clear advantage."
            },
        },
        
    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["danish_gambit"] = {
    "title": OPENING_TITLES["danish_gambit"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3","dxc3","Bc4"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3","dxc3","Nxc3"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "cxb2","Bxb2"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "d5"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "Nf6"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "cxb2","Bxb2","d5"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "cxb2","Bxb2","Nf6"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Nxc3",
                "Nc6"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Nxc3",
                "d6"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3","d5","exd5"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3","d5","cxd4"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","d5","exd5",
                "Qxd5","cxd4","Nc6"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3","Nc6","cxd4"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3","Nc6","Nf3"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3","d6","cxd4"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3","Nf6","cxd4"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3","Be7","cxd4"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3","Qe7","cxd4"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3","c5","cxd4"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e5","d4","exd4","c3","h6","cxd4"],
            "notes": {},
        },

    ],
    "master_addon": [
        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "cxb2","Bxb2","d5","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "cxb2","Bxb2","d5","Bxd5"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "cxb2","Bxb2","Nf6","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "cxb2","Bxb2","Nc6","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "d5","exd5"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "d5","Nxc3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "d5","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Nxc3",
                "Nc6","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Nxc3",
                "Nc6","Bc4"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Nxc3",
                "d6","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Nxc3",
                "Bc5","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Nxc3",
                "Nf6","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "e6","Nxc3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "e6","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","dxc3","Bc4",
                "e6","Nf3","Nf6"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","d5","exd5",
                "Qxd5","cxd4","Nc6","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","d5","cxd4",
                "dxe4"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","d5","cxd4",
                "Nc6","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","Nc6","cxd4",
                "d5","exd5","Qxd5","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","Nc6","cxd4",
                "Nf6","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","Nc6","cxd4",
                "Bc5","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","d6","cxd4",
                "Nf6","Nc3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","d6","cxd4",
                "Nc6","Nf3"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","Nf6","cxd4",
                "Nxe4"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","Be7","cxd4",
                "d5"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","Qe7","cxd4",
                "Qxe4"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","c5","cxd4",
                "cxd4"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","d4","exd4","c3","h6","cxd4",
                "Nf6"
            ],
            "notes": {},
        },

    ],
}

PRACTICE_OPENINGS["smith_morra"] = {
    "title": OPENING_TITLES["smith_morra"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["e4","c5","d4","cxd4","c3"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","c5","d4","cxd4","c3","dxc3","Nxc3"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["london"] = {
    "title": OPENING_TITLES["london"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["d4","d5","Bf4"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["d4","Nf6","Bf4"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["jobava_london"] = {
    "title": OPENING_TITLES["jobava_london"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["d4","d5","Nc3","Nf6","Bf4"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["colle"] = {
    "title": OPENING_TITLES["colle"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["d4","d5","Nf3","Nf6","e3","e6","Bd3"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["trompowsky"] = {
    "title": OPENING_TITLES["trompowsky"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["d4","Nf6","Bg5","e6"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["d4","Nf6","Bg5","Ne4","h4"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["queens_gambit"] = {
    "title": OPENING_TITLES["queens_gambit"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["d4","d5","c4"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["d4","d5","c4","e6","Nc3"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["d4","d5","c4","c6","Nc3"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["ruy_lopez"] = {
    "title": OPENING_TITLES["ruy_lopez"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","Nf3","Nc6","Bb5","a6","Ba4",
                "Nf6"
            ],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["scandinavian"] = {
    "title": OPENING_TITLES["scandinavian"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["e4","d5","exd5","Qxd5","Nc3"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","d5","exd5","Qxd5","Nc3","Qa5"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["caro_kann"] = {
    "title": OPENING_TITLES["caro_kann"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["e4","c6","d4","d5","Nc3"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","c6","d4","d5","e5","Bf5"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["french"] = {
    "title": OPENING_TITLES["french"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["e4","e6","d4","d5","Nc3"],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": ["e4","e6","d4","d5","e5","c5"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["pirc_modern"] = {
    "title": OPENING_TITLES["pirc_modern"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["e4","d6","d4","Nf6","Nc3","g6"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["stafford"] = {
    "title": OPENING_TITLES["stafford"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","Nf3","Nf6","Nxe5","Nc6","Nxc6",
                "dxc6"
            ],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["traxler"] = {
    "title": OPENING_TITLES["traxler"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","Nf3","Nc6","Bc4","Nf6","Ng5",
                "Bc5"
            ],
            "notes": {},
        },

        {
            "id": "",
            "tags": [],
            "moves": [
                "e4","e5","Nf3","Nc6","Bc4","Nf6","Ng5",
                "Bc5","Nxf7"
            ],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["dutch"] = {
    "title": OPENING_TITLES["dutch"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["d4","f5","g3","Nf6","Bg2"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["kings_indian"] = {
    "title": OPENING_TITLES["kings_indian"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["d4","Nf6","c4","g6","Nc3","Bg7"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["benoni"] = {
    "title": OPENING_TITLES["benoni"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["d4","Nf6","c4","c5","d5","e6","Nc3"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["slav"] = {
    "title": OPENING_TITLES["slav"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["d4","d5","c4","c6","Nc3"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}

PRACTICE_OPENINGS["qgd"] = {
    "title": OPENING_TITLES["qgd"],
    "beginner": [
        {
            "id": "",
            "tags": [],
            "moves": ["d4","d5","c4","e6","Nc3","Nf6"],
            "notes": {},
        },

    ],
    "master_addon": [
    ],
}
