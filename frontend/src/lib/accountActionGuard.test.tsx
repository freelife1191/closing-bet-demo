import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { useAccountActionGuard } from './accountActionGuard';

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function GuardProbe({ accountKey, operation }: { accountKey: string; operation: () => Promise<string> }) {
  const captureAction = useAccountActionGuard(accountKey);
  const [result, setResult] = useState<string | null>(null);
  const run = async () => {
    const isCurrent = captureAction();
    const result = await operation();
    if (isCurrent()) {
      setResult(result);
    }
  };
  return <><button onClick={run}>실행</button>{result && <p>{result}</p>}</>;
}

describe('useAccountActionGuard', () => {
  it('계정이 바뀐 뒤 이전 요청의 늦은 UI 부수효과를 버린다', async () => {
    const aliceRequest = deferred<string>();
    const view = render(<GuardProbe accountKey="alice@example.test" operation={() => aliceRequest.promise} />);

    fireEvent.click(screen.getByText('실행'));
    view.rerender(<GuardProbe accountKey="bob@example.test" operation={async () => 'Bob 성공'} />);
    aliceRequest.resolve('Alice 실패');
    await aliceRequest.promise;

    expect(screen.queryByText('Alice 실패')).toBeNull();
  });
});
