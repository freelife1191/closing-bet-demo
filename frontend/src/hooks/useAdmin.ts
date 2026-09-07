'use client';

import { useSession } from 'next-auth/react';
import { useState, useEffect } from 'react';

interface UseAdminResult {
  isAdmin: boolean;
  isLoading: boolean;
  userEmail: string | null;
}

/**
 * ADMIN 권한 확인을 위한 커스텀 훅
 * - 로그인된 사용자의 이메일이 ADMIN_EMAILS에 포함되어 있는지 확인
 * - 서버에서 ADMIN 이메일 목록을 확인하여 보안 강화
 */
export function useAdmin(): UseAdminResult {
  const { data: session, status } = useSession();
  const [isAdmin, setIsAdmin] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAdmin = async () => {
      if (status === 'loading') {
        return; // 세션 로딩 중이면 대기
      }

      if (!session?.user?.email) {
        setIsAdmin(false);
        setIsLoading(false);
        return;
      }

      try {
        // 이메일을 붙이지 않는다. 서버는 서명된 신원으로만 판정하므로 무시되고, 실어
        // 보내면 접근 로그와 브라우저 이력에만 남는다.
        const res = await fetch('/api/admin/check', { cache: 'no-store' });
        if (res.ok) {
          const data = await res.json();
          setIsAdmin(data.isAdmin === true);
        } else {
          setIsAdmin(false);
        }
      } catch (error) {
        console.error('Failed to check admin status:', error);
        setIsAdmin(false);
      } finally {
        setIsLoading(false);
      }
    };

    checkAdmin();
  }, [session, status]);

  return {
    isAdmin,
    isLoading: status === 'loading' || isLoading,
    userEmail: session?.user?.email || null,
  };
}

export default useAdmin;
