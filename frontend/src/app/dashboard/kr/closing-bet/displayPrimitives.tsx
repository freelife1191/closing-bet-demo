'use client';

import Tooltip from '@/app/components/Tooltip';
import { isPositivePrice } from './displayHelpers';

// [JONGGA-006] 종가베팅 화면의 표시용 프리미티브. 화면 고유 로직을 담지 않으므로
// 페이지 본체에서 떼어냈다. 다만 components/ 가 아니라 이 자리에 두는 이유가 있다.
//
// 이 파일에 담는 기준은 「이 라우트에서만 쓰는 표시용 컴포넌트」다. 둘 다 종가베팅
// 페이지에서만 불리고 다른 라우트는 참조하지 않는다. 여기에 더해 PriceRangeBar 는
// 같은 디렉터리의 displayHelpers 를 쓰므로 공용 디렉터리로 올릴 수도 없다. 올리면
// 공용 컴포넌트가 특정 라우트의 모듈을 가로질러 가져오게 되어 의존 방향이 뒤집힌다.
// StatBox 는 그 제약이 없지만 기준이 같으므로 함께 둔다.
//
// 근거: AUDIT-JONGGA §4.1

// Price Range Progress Bar Component
//
// 시세를 못 받은 종목은 백엔드가 값을 비우는 대신 0 으로 채운 응답을 돌려준다. 세 갈래가
// 모두 그렇게 한다(services/kr_market_stock_detail_service.py 의 기본값 payload 와
// engine/collectors/naver_extractors_mixin.py 의 빈 결과 딕셔너리). 그 0 을 그대로 그리면
// 「₩0」과 「L: ₩0 / H: ₩0」이 정상 시세처럼 보이고 손잡이가 범위 한가운데에 놓인다.
// 주가에 0 원은 없으므로 값을 구하지 못한 것으로 보고 그 사실을 적는다.
//
// 키가 아예 빠진 응답도 같은 자리에서 걸러야 한다. 캐시를 읽는 쪽이 code 가 문자열인지만
// 검사하고 통과시키므로(kr_market_stock_detail_service.py 의 _normalize_stock_detail_payload)
// 시세 키가 빠진 채로 화면까지 닿을 수 있고, 그러면 toLocaleString 이 터져 모달이 통째로
// 그려지지 않는다. 값을 받는 이 함수에서 한 번 막으면 호출하는 두 자리가 함께 고쳐진다.
export function PriceRangeBar({ low, high, current, label }: {
  low?: number | null;
  high?: number | null;
  current?: number | null;
  label: string;
}) {
  if (!isPositivePrice(low) || !isPositivePrice(high) || !isPositivePrice(current)) {
    return (
      <div className="mb-5">
        <div className="flex justify-between items-end mb-2">
          <span className="text-xs text-gray-400 font-medium">{label}</span>
          <span className="text-xs text-gray-500">시세를 불러오지 못했습니다</span>
        </div>
      </div>
    );
  }

  const range = high - low;
  const position = range > 0 ? ((current - low) / range) * 100 : 50;
  const positionClamped = Math.max(0, Math.min(100, position));

  return (
    <div className="mb-5">
      <div className="flex justify-between items-end mb-2">
        <span className="text-xs text-gray-400 font-medium">{label}</span>
        <div className="text-right">
          <span className="text-[10px] text-gray-500 mr-2">실시간</span>
          <span className="text-sm font-bold text-white">₩{current.toLocaleString()}</span>
        </div>
      </div>

      <div className="relative h-2.5 bg-[#131722] rounded-full ring-1 ring-white/10">
        {/* Background Range Gradient (Low -> High indication) */}
        <div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-500/20 via-gray-500/10 to-rose-500/20" />

        {/* Active Range Fill (Optional: Low to Current) */}
        <div
          className="absolute top-0 left-0 h-full rounded-l-full bg-white/5"
          style={{ width: `${positionClamped}%` }}
        />

        {/* Indicator Knob */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full border-2 border-indigo-500 shadow-lg z-10 transition-all duration-500 group cursor-help"
          style={{ left: `${positionClamped}%`, transform: 'translate(-50%, -50%)' }}
        >
          <div className="absolute -top-6 left-1/2 -translate-x-1/2 bg-indigo-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
            {positionClamped.toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="flex justify-between text-[10px] text-gray-500 mt-1.5 font-mono">
        <span className="text-blue-400">L: ₩{low.toLocaleString()}</span>
        <span className="text-rose-400">H: ₩{high.toLocaleString()}</span>
      </div>
    </div>
  );
}

export function StatBox({ label, value, highlight = false, customValue, tooltip }: { label: string, value: number, highlight?: boolean, customValue?: string, tooltip?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1 flex items-center gap-1">
        {label}
        {tooltip && (
          <Tooltip content={tooltip}>
            <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
          </Tooltip>
        )}
      </span>
      <span className={`text-2xl font-mono font-bold ${highlight ? 'text-indigo-400' : 'text-white'}`}>
        {customValue || value}
      </span>
    </div>
  )
}
