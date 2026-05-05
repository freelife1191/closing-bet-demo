#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전체 데이터 업데이트 파이프라인을 직접 실행하여 step별 결과를 출력한다."""
import logging
import os
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# Quiet some noisy libraries
for noisy in (
    "urllib3",
    "google.auth",
    "google_auth_httplib2",
    "google.api_core",
    "matplotlib",
    "matplotlib.font_manager",
    "asyncio",
    "engine.data_sources_provider_strategies",
    "engine.data_sources_fallback_manager",
):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger("update_test")

from services.common_update_service import run_background_update_pipeline


_RESULTS: dict[str, str] = {}


def _update_item_status(name: str, status: str) -> None:
    _RESULTS[name] = status
    logger.info("[STATUS] %s -> %s", name, status)


def _finish_update() -> None:
    logger.info("[FINISH] update finished")


def main() -> int:
    items = sys.argv[1:] if len(sys.argv) > 1 else None
    target_date = None
    force = False

    shared_state = SimpleNamespace(STOP_REQUESTED=False)
    t0 = time.perf_counter()
    run_background_update_pipeline(
        target_date=target_date,
        selected_items=items,
        force=force,
        update_item_status=_update_item_status,
        finish_update=_finish_update,
        shared_state=shared_state,
        logger=logger,
    )
    elapsed = time.perf_counter() - t0
    print()
    print("=" * 60)
    print(f"Pipeline elapsed: {elapsed:.1f}s")
    print(f"items requested : {items or 'ALL'}")
    print()
    for k, v in _RESULTS.items():
        marker = "OK " if v == "done" else "ERR" if v == "error" else "..."
        print(f"  {marker} {k:25s} -> {v}")
    failures = [k for k, v in _RESULTS.items() if v != "done"]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
