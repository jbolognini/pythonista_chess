# lichess_engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Literal
import json
import time
import urllib.parse
import urllib.request
import urllib.error
import socket


CloudStatus = Literal[
    "ok",           # pvs present
    "missing",      # 404 / not cached
    "rate_limited", # 429 or backoff window active
    "offline",      # DNS / no route
    "timeout",      # socket timeout
    "bad_json",     # response not JSON
    "http_error",   # other HTTP codes
    "error",        # anything else
]


@dataclass(frozen=True)
class PV:
    best_uci: str
    cp: Optional[int] = None
    mate: Optional[int] = None
    moves_uci: str = ""


@dataclass(frozen=True)
class CloudEval:
    status: CloudStatus
    pvs: List[PV]
    http_code: Optional[int] = None
    retry_after_s: Optional[int] = None


class LichessCloudEngine:
    def __init__(self, timeout_s: float = 15.0):
        self.timeout_s = timeout_s
        self._backoff_until = 0.0

    def eval(self, fen: str, *, multipv: int = 3) -> CloudEval:
        now = time.time()
        if now < self._backoff_until:
            return CloudEval(
                status="rate_limited",
                pvs=[],
                retry_after_s=int(self._backoff_until - now),
            )

        params = urllib.parse.urlencode({"fen": fen, "multiPv": str(multipv)})
        url = f"https://lichess.org/api/cloud-eval?{params}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                status = getattr(resp, "status", 200)
                body = resp.read().decode("utf-8", "replace")

            # Some environments don't raise for non-200, so handle explicitly:
            if status == 404:
                return CloudEval(status="missing", pvs=[], http_code=404)
            if status == 429:
                self._backoff_until = time.time() + 60.0
                return CloudEval(status="rate_limited", pvs=[], http_code=429, retry_after_s=60)
            if status >= 400:
                return CloudEval(status="http_error", pvs=[], http_code=status)

            js = json.loads(body)

            raw = js.get("pvs") or []
            if not raw:
                return CloudEval(status="missing", pvs=[])

            out: List[PV] = []
            want = max(1, int(multipv))
            for pv in raw[:want]:
                moves = (pv.get("moves") or "").strip()
                if not moves:
                    continue
                out.append(
                    PV(
                        best_uci=moves.split()[0],
                        cp=pv.get("cp"),
                        mate=pv.get("mate"),
                        moves_uci=moves,
                    )
                )

            if not out:
                return CloudEval(status="missing", pvs=[])

            return CloudEval(status="ok", pvs=out)

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return CloudEval(status="missing", pvs=[], http_code=404)
            if e.code == 429:
                self._backoff_until = time.time() + 60.0
                return CloudEval(status="rate_limited", pvs=[], http_code=429, retry_after_s=60)
            return CloudEval(status="http_error", pvs=[], http_code=e.code)

        except urllib.error.URLError:
            return CloudEval(status="offline", pvs=[])

        except socket.timeout:
            return CloudEval(status="timeout", pvs=[])

        except json.JSONDecodeError:
            return CloudEval(status="bad_json", pvs=[])

        except Exception:
            return CloudEval(status="error", pvs=[])

