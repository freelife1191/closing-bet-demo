import { useCallback, useLayoutEffect, useRef } from 'react';

export type IsAccountActionCurrent = () => boolean;
export type CaptureAccountAction = () => IsAccountActionCurrent;

/** 계정 전환 또는 언마운트 뒤 늦게 도착한 요청 응답의 UI 부수효과를 막는다. */
export function useAccountActionGuard(accountKey: string | null): CaptureAccountAction {
  const generationRef = useRef(0);

  useLayoutEffect(() => {
    generationRef.current += 1;
    return () => {
      generationRef.current += 1;
    };
  }, [accountKey]);

  return useCallback(() => {
    const generation = generationRef.current;
    return () => generationRef.current === generation;
  }, []);
}
