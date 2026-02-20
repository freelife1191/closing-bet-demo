#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate 3-version showcase scenario markdown files."""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


MIN_TTS_RATE = 4.4
MAX_TTS_RATE = 4.8
DEFAULT_TTS_RATE = 4.6


@dataclass(frozen=True)
class SceneSeed:
    """Scene blueprint before timeline allocation."""

    scene: str
    screen: str
    action: str
    narration: str
    subtitle_cue: str


@dataclass(frozen=True)
class SceneRow:
    """Single scene row with computed timeline."""

    scene: str
    time: str
    screen: str
    action: str
    narration: str
    tts_rate: str
    subtitle_cue: str


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Build showcase scenarios")
    parser.add_argument("--out-dir", default="project/video/scenarios")
    parser.add_argument("--short-target-sec", type=int, default=60)
    parser.add_argument("--normal-target-sec", type=int, default=120)
    parser.add_argument("--detail-target-sec", type=int, default=220)
    return parser.parse_args()


def _short_seeds() -> List[SceneSeed]:
    return [
        SceneSeed(
            "S1",
            "/",
            "Hero와 핵심 가치 문장 노출",
            "Smart Money Bot은 VCP와 종가베팅을 통합한 한국 주식 AI 분석 플랫폼입니다.",
            "VCP·종가베팅 통합 AI 분석",
        ),
        SceneSeed(
            "S2",
            "/dashboard/kr",
            "Overview와 KR Market Gate 강조",
            "Overview의 Market Gate가 코스피·코스닥과 환율 위험을 먼저 점검합니다.",
            "Market Gate로 시장 리스크 선점검",
        ),
        SceneSeed(
            "S3",
            "/dashboard/kr/vcp",
            "실시간 VCP 시그널 목록 스크롤",
            "VCP 시그널은 변동성 수축과 기관·외국인 수급을 함께 필터링합니다.",
            "VCP+수급 필터로 후보 압축",
        ),
        SceneSeed(
            "S4",
            "/dashboard/kr/vcp",
            "Gemini/GPT/Perplexity 탭 전환",
            "Gemini·GPT·Perplexity 교차 검증으로 AI 의견 신뢰도를 높입니다.",
            "Multi-Model AI 교차 검증",
        ),
        SceneSeed(
            "S5",
            "/dashboard/kr/closing-bet",
            "점수·등급·재분석 영역 포커스",
            "종가베팅은 점수·등급·재분석 흐름으로 장마감 후보를 빠르게 정렬합니다.",
            "종가베팅 점수·등급·재분석",
        ),
        SceneSeed(
            "S6",
            "/dashboard/kr/cumulative",
            "누적 성과/모의투자 데이터 확인",
            "누적 성과와 모의투자 이력으로 전략 성능을 수치로 검증합니다.",
            "누적 성과·모의투자 검증",
        ),
        SceneSeed(
            "S7",
            "/dashboard/data-status",
            "Data Status와 알림 채널 상태 확인",
            "AI 상담, Data Status, Telegram·Discord·Slack·Email 알림으로 운영을 마무리합니다.",
            "AI 상담+Data Status+멀티채널 알림",
        ),
    ]


def _normal_seeds() -> List[SceneSeed]:
    return [
        SceneSeed(
            "S1",
            "/",
            "핵심 가치 슬라이드 노출",
            "Smart Money Bot은 Rule-based Screening과 AI Reasoning을 결합해 한국 주식 매매 신호 품질을 끌어올립니다.",
            "Rule-based Screening + AI Reasoning",
        ),
        SceneSeed(
            "S2",
            "README.md",
            "데이터 레이어 다이어그램 포커스",
            "데이터 레이어는 Toss Securities API 우선, pykrx·yfinance 폴백, 뉴스 크롤링으로 입력 품질을 유지합니다.",
            "Toss 우선, pykrx/yfinance 폴백",
        ),
        SceneSeed(
            "S3",
            "engine/phases.py",
            "Phase1~4 파이프라인 코드 하이라이트",
            "엔진은 Phase1~4 구조로 사전 필터링, 뉴스 수집, LLM 배치 분석, 시그널 생성을 역할로 분리해 처리합니다.",
            "Phase1~4 파이프라인 분리 처리",
        ),
        SceneSeed(
            "S4",
            "/dashboard/kr",
            "Overview KPI와 KR Market Gate 강조",
            "Overview의 KR Market Gate는 시장 점수와 상위 섹터를 보여주고 interval 설정으로 자동 갱신 주기를 제어합니다.",
            "Overview + KR Market Gate + interval",
        ),
        SceneSeed(
            "S5",
            "/dashboard/kr/vcp",
            "실시간 시그널과 VCP 기준표 모달 표시",
            "VCP 페이지는 실시간 시그널, VCP 기준표, 차트 범위 표시, AI 탭 비교로 패턴 완성도를 다면으로 검토합니다.",
            "VCP 기준표/차트범위/AI 탭 비교",
        ),
        SceneSeed(
            "S6",
            "/dashboard/kr/closing-bet",
            "Jongga V2 결과와 재분석 버튼 강조",
            "종가베팅은 점수 구성, S/A/B 등급, Jongga V2 재분석과 메시지 전송 흐름으로 의사결정을 가속합니다.",
            "종가베팅 + Jongga V2 재분석",
        ),
        SceneSeed(
            "S7",
            "/dashboard/kr/cumulative",
            "성과 테이블과 백테스트 요약 확인",
            "누적 성과 화면은 페이지네이션 히스토리와 백테스트 요약을 제공해 전략의 장기 기대값을 지속적으로 추적합니다.",
            "누적 성과 + 백테스트 요약",
        ),
        SceneSeed(
            "S8",
            "/dashboard/kr/vcp",
            "매수/매도 모달과 포트폴리오 연계 강조",
            "매수·매도 모달로 연결되는 모의투자 기능은 포트폴리오, 자산 곡선, 거래 로그를 함께 기록해 실행력을 점검합니다.",
            "모의투자 포트폴리오/거래로그",
        ),
        SceneSeed(
            "S9",
            "/chatbot",
            "세션 목록과 모델 선택 영역 포커스",
            "AI 상담은 세션 관리, 모델 조회, 제안 프롬프트, 프로필·쿼터 API를 결합해 일관된 투자 대화 흐름을 제공합니다.",
            "AI 상담 세션/모델/쿼터 관리",
        ),
        SceneSeed(
            "S10",
            "/dashboard/data-status",
            "업데이트 진행, 알림 채널, 운영 스크립트 강조",
            "Data Status, 스케줄러, Telegram·Discord·Slack·Email 알림, restart_all.sh로 루프를 완성합니다.",
            "Data Status + 스케줄러 + 멀티채널 알림",
        ),
    ]


def _detail_seeds() -> List[SceneSeed]:
    # 기본 3분대 설계(190초). 불필요하게 길이를 늘리기보다 기능 커버리지를 우선한다.
    return [
        SceneSeed(
            "S1",
            "/",
            "랜딩 Hero와 가치 제안 노출",
            "Smart Money Bot은 한국 주식의 Market-First 운용 원칙 위에서 VCP와 종가베팅 전략을 AI로 연결해 실행하는 통합 시스템입니다.",
            "Market-First + VCP + 종가베팅 통합",
        ),
        SceneSeed(
            "S2",
            "terminal:./restart_all.sh",
            "Quick Start 명령과 서비스 포트 확인",
            "운영 시작은 restart_all.sh 하나로 백엔드 5501과 프론트엔드 3500을 동시에 띄우고 stop_all.sh로 안전하게 종료하는 구조입니다.",
            "restart_all.sh / stop_all.sh 운영",
        ),
        SceneSeed(
            "S3",
            "README.md#architecture",
            "아키텍처 다이어그램과 Data Layer 강조",
            "Data Layer는 Toss Securities API 우선, pykrx·yfinance 폴백, 뉴스 수집을 결합해 시세·수급·재료 데이터의 신뢰성과 연속성을 확보합니다.",
            "Toss 우선 + pykrx/yfinance 폴백",
        ),
        SceneSeed(
            "S4",
            "/dashboard/kr",
            "KR Market Gate 점수와 상태 배지 확대",
            "Market Gate는 코스피·코스닥, 환율, 섹터 강도를 종합해 OPEN 또는 CLOSED를 판정하고 무리한 종목 진입을 상단에서 차단합니다.",
            "Market Gate OPEN/CLOSED 판정",
        ),
        SceneSeed(
            "S5",
            "engine/phases.py",
            "Phase1~4 파이프라인 코드 스냅샷",
            "엔진은 Phase1 사전 필터링, Phase2 뉴스 수집, Phase3 LLM 배치 분석, Phase4 최종 시그널 확정으로 책임을 분리해 유지보수성을 높입니다.",
            "Phase1~4 책임 분리 아키텍처",
        ),
        SceneSeed(
            "S6",
            "engine/scorer.py",
            "점수/등급 계산 로직과 임계값 강조",
            "Scorer와 Grade 체계는 거래대금, 수급, 패턴 완성도, 리스크 항목을 수치화해 S/A/B 등급으로 의사결정 우선순위를 명확히 만듭니다.",
            "점수화 + S/A/B 등급화",
        ),
        SceneSeed(
            "S7",
            "/dashboard/kr/vcp",
            "실시간 VCP 테이블과 VCP 기준표 모달 확인",
            "VCP 페이지는 Score 60+ 필터, VCP 범위 시각화, 차트 패턴 검증을 결합해 변동성 수축 후보를 기술적으로 빠르게 추려냅니다.",
            "VCP Score60+ + 범위 시각화",
        ),
        SceneSeed(
            "S8",
            "/dashboard/kr/vcp",
            "Gemini/GPT/Perplexity AI 탭 순차 전환",
            "Gemini·GPT·Perplexity의 교차 검증 결과를 한 화면에서 비교해 단일 모델 편향을 줄이고 매수·보유·회피 판단의 신뢰도를 올립니다.",
            "Multi-Model AI 교차 검증",
        ),
        SceneSeed(
            "S9",
            "/dashboard/kr/closing-bet",
            "Jongga V2 최신 결과와 상태 영역 스크롤",
            "종가베팅은 점수 구성, 등급 기준, 최신 결과 조회와 상태 추적을 제공하고 run·analyze·reanalyze 흐름으로 장마감 전략을 즉시 갱신합니다.",
            "Jongga V2 run/analyze/reanalyze",
        ),
        SceneSeed(
            "S10",
            "/dashboard/kr/closing-bet",
            "재분석 버튼과 메시지 전송 기능 포커스",
            "reanalysis와 message API는 후보군 해석을 재계산한 뒤 팀 채널로 바로 공유해 분석과 실행 사이의 지연을 줄여줍니다.",
            "재분석 후 즉시 메시지 공유",
        ),
        SceneSeed(
            "S11",
            "/dashboard/kr/cumulative",
            "누적 성과 표와 백테스트 카드 확대",
            "누적 성과 화면은 페이지네이션 히스토리, 승률, 평균수익, 백테스트 요약을 제공해 전략 품질을 감이 아닌 데이터로 관리하게 합니다.",
            "누적 성과 + 백테스트 데이터 관리",
        ),
        SceneSeed(
            "S12",
            "/dashboard/kr/vcp",
            "매수·매도 모달과 포트폴리오 히스토리 연계",
            "모의투자 서비스는 포트폴리오, 입출금, 매매 이력, 자산 곡선을 SQLite로 기록해 실제 운용 전에 실행 규율을 검증하도록 돕습니다.",
            "모의투자 실행 규율 사전 검증",
        ),
        SceneSeed(
            "S13",
            "/chatbot",
            "세션 목록/모델 선택/추천 질문 흐름 시연",
            "AI 상담은 세션·히스토리·프로필·모델·제안 프롬프트·쿼터 API를 통합해 시장 질문, 종목 질문, 리스크 질문을 연속적으로 처리합니다.",
            "AI 상담 세션·히스토리·쿼터 통합",
        ),
        SceneSeed(
            "S14",
            "services/scheduler.py",
            "스케줄러 체인과 lock 처리 로직 하이라이트",
            "스케줄러는 lock 파일로 중복 실행을 막고 장중/장마감 체인에서 Market Gate 갱신, VCP 분석, AI 종가베팅, 알림 발송을 자동화합니다.",
            "lock 기반 스케줄링 자동 체인",
        ),
        SceneSeed(
            "S15",
            "project/project-showcase-kit/scripts/pipeline/run_all.sh",
            "showcase-scenario stage와 검증 리포트 확인",
            "project-showcase-kit은 preflight부터 validate까지 파이프라인을 오케스트레이션하고 시나리오·TTS·자막·용어 감사 결과로 산출물 품질을 보증합니다.",
            "파이프라인+용어감사+싱크검증",
        ),
    ]


def _clean_chars(text: str) -> int:
    cleaned = re.sub(r"\s+", "", text)
    return len(cleaned)


def _rate_hint(narration: str, duration_sec: int) -> float:
    chars = _clean_chars(narration)
    if chars <= 0 or duration_sec <= 0:
        return DEFAULT_TTS_RATE
    raw = chars / float(duration_sec)
    return min(MAX_TTS_RATE, max(MIN_TTS_RATE, raw))


def _distribute_with_limits(values: List[float], limits: List[float], delta: float, expand: bool) -> List[float]:
    adjusted = values[:]
    remaining = abs(delta)
    for _ in range(16):
        if remaining <= 1e-6:
            break
        if expand:
            capacity = [max(0.0, limit - current) for current, limit in zip(adjusted, limits)]
        else:
            capacity = [max(0.0, current - limit) for current, limit in zip(adjusted, limits)]
        total_capacity = sum(capacity)
        if total_capacity <= 1e-6:
            break
        for idx, room in enumerate(capacity):
            if room <= 0:
                continue
            share = remaining * (room / total_capacity)
            amount = min(room, share)
            adjusted[idx] = adjusted[idx] + amount if expand else adjusted[idx] - amount
        used = abs(sum(adjusted) - sum(values))
        remaining = max(0.0, abs(delta) - used)
    return adjusted


def _allocate_seconds(seeds: List[SceneSeed], target_sec: int) -> List[int]:
    if not seeds:
        return []
    if target_sec <= 0:
        return [1 for _ in seeds]

    chars = [_clean_chars(seed.narration) for seed in seeds]
    preferred = [max(1.0, count / DEFAULT_TTS_RATE) for count in chars]
    lower = [max(1.0, count / MAX_TTS_RATE) for count in chars]
    upper = [max(1.0, count / MIN_TTS_RATE) for count in chars]

    durations = preferred[:]
    preferred_sum = sum(durations)
    target = float(target_sec)

    if preferred_sum < target:
        durations = _distribute_with_limits(durations, upper, target - preferred_sum, expand=True)
    elif preferred_sum > target:
        durations = _distribute_with_limits(durations, lower, preferred_sum - target, expand=False)

    floor_values = [max(1, int(math.floor(value))) for value in durations]
    remainders = [value - math.floor(value) for value in durations]
    diff = target_sec - sum(floor_values)

    if diff > 0:
        order = sorted(range(len(floor_values)), key=lambda idx: remainders[idx], reverse=True)
        for idx in order:
            if diff <= 0:
                break
            floor_values[idx] += 1
            diff -= 1
    elif diff < 0:
        order = sorted(range(len(floor_values)), key=lambda idx: remainders[idx])
        for idx in order:
            if diff >= 0:
                break
            if floor_values[idx] > 1:
                floor_values[idx] -= 1
                diff += 1

    floor_values[-1] = max(1, floor_values[-1] + (target_sec - sum(floor_values)))
    return floor_values


def _format_hms(total_sec: int) -> str:
    minute = max(0, total_sec) // 60
    second = max(0, total_sec) % 60
    return f"{minute:02d}:{second:02d}"


def _parse_hms(raw: str) -> int:
    parts = raw.strip().split(":")
    if len(parts) != 2:
        return 0
    return (int(parts[0]) * 60) + int(parts[1])


def _parse_time_range(raw: str) -> tuple[int, int]:
    if "-" not in raw:
        return 0, 0
    start_raw, end_raw = [item.strip() for item in raw.split("-", 1)]
    start_sec = _parse_hms(start_raw)
    end_sec = _parse_hms(end_raw)
    if end_sec < start_sec:
        end_sec = start_sec
    return start_sec, end_sec


def _build_rows(seeds: List[SceneSeed], target_sec: int) -> List[SceneRow]:
    durations = _allocate_seconds(seeds, target_sec)
    rows: List[SceneRow] = []
    cursor = 0
    for idx, seed in enumerate(seeds):
        scene_duration = durations[idx] if idx < len(durations) else 1
        start = cursor
        end = start + scene_duration
        tts_rate = _rate_hint(seed.narration, scene_duration)
        rows.append(
            SceneRow(
                scene=seed.scene,
                time=f"{_format_hms(start)}-{_format_hms(end)}",
                screen=seed.screen,
                action=seed.action,
                narration=seed.narration,
                tts_rate=f"{tts_rate:.1f}",
                subtitle_cue=seed.subtitle_cue,
            )
        )
        cursor = end
    return rows


def _render(version_name: str, target_sec: int, rows: List[SceneRow]) -> str:
    lines: List[str] = [
        f"# {version_name} 시나리오",
        "",
        "- project: Smart Money Bot",
        f"- targetDurationSec: {target_sec}",
        "- ttsPolicy: seminar(4.4~4.8 syll/sec, default 4.6)",
        "- syncPolicy: speed -> compression -> scene_extend(no-cut)",
        "- scriptPolicy: dual-script(ko,en-separated)",
        "",
        "| Scene | Time | Screen | Action | Narration | TTSRate | SubtitleCue |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row.scene} | {row.time} | `{row.screen}` | {row.action} | {row.narration} | {row.tts_rate} | {row.subtitle_cue} |"
        )
    return "\n".join(lines).strip() + "\n"


def _build_scene_plan_payload(version: str, target_sec: int, rows: List[SceneRow]) -> Dict:
    scene_rows: List[Dict[str, object]] = []
    for row in rows:
        start_sec, end_sec = _parse_time_range(row.time)
        scene_rows.append(
            {
                "scene_id": row.scene,
                "time_range": row.time,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "target_sec": max(0, end_sec - start_sec),
                "screen": row.screen,
                "action": row.action,
                "narration_ko": row.narration,
                "tts_rate": float(row.tts_rate),
                "subtitle_cue": row.subtitle_cue,
            }
        )
    return {
        "version": version,
        "targetDurationSec": target_sec,
        "scenes": scene_rows,
    }


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    version_specs = [
        ("short", "간소화(1분 이내)", args.short_target_sec, _short_seeds()),
        ("normal", "보통(2분)", args.normal_target_sec, _normal_seeds()),
        ("detail", "디테일(3분 이상)", args.detail_target_sec, _detail_seeds()),
    ]

    for version, label, target_sec, seeds in version_specs:
        rows = _build_rows(seeds, target_sec)
        scenario_path = out_dir / f"scenario_{version}.md"
        scenario_path.write_text(_render(label, target_sec, rows), encoding="utf-8")
        print(f"scenario generated: {scenario_path}")

        scene_plan = _build_scene_plan_payload(version=version, target_sec=target_sec, rows=rows)
        scene_plan_path = out_dir / f"scene_plan_{version}.json"
        scene_plan_path.write_text(json.dumps(scene_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"scene plan generated: {scene_plan_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
