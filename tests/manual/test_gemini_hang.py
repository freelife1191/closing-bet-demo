import asyncio
import os
import time
from dotenv import load_dotenv

try:
    from google import genai
except ImportError:
    genai = None

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

async def test_sync_to_thread_hang():
    print("--- [테스트 1] 동기 클라이언트, 타임아웃 11초 (Sec) ---")
    
    # 10s is minimum deadline. Let's try 11 seconds.
    timeout_sec = 11.0
    client = genai.Client(
        api_key=API_KEY, 
        http_options={'timeout': timeout_sec}
    )
    
    def _call_gemini():
        print(f"[{time.strftime('%H:%M:%S')}] _call_gemini 스레드 작업 시작")
        try:
            # We don't have a reliable way to force 11s hang on Gemini server side natively via prompt easily,
            # but let's just make a valid call to see if config is accepted.
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents='매우 긴 대답을 해줘. 그리고 시간이 오래 걸려야해. ' * 50
            )
            print(f"[{time.strftime('%H:%M:%S')}] _call_gemini 정상 완료!")
            return response.text
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] _call_gemini 스레드 내부 예외 발생: {type(e).__name__} - {e}")
            raise e
            
    try:
        print(f"[{time.strftime('%H:%M:%S')}] wait_for (15초) 설정하여 to_thread 호출")
        resp = await asyncio.wait_for(
            asyncio.to_thread(_call_gemini),
            timeout=15.0
        )
        print("결과:", resp[:100])
    except asyncio.TimeoutError:
        print(f"[{time.strftime('%H:%M:%S')}] 주요 코루틴에서 TimeoutError 잡힘!")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 메인 에러: {e}")

    print("--- 테스트 1 완료 ---\n")

async def test_async_client():
    print("--- [테스트 2] 비동기 클라이언트, timeout=11.0초 ---")
    timeout_sec = 11.0
    client = genai.Client(
        api_key=API_KEY, 
        http_options={'timeout': timeout_sec}
    )
    
    try:
        print(f"[{time.strftime('%H:%M:%S')}] wait_for (15초) 설정하여 비동기 호출")
        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents='매우 긴 대답을 해줘. ' * 50
            ),
            timeout=15.0
        )
        print("결과:", resp.text[:100])
    except asyncio.TimeoutError:
        print(f"[{time.strftime('%H:%M:%S')}] 비동기 호출 타임아웃!")
    except Exception as e:
        print(f"비동기 예외: {type(e).__name__} - {e}")
        
    print("--- 테스트 2 완료 ---\n")

async def main():
    await test_sync_to_thread_hang()
    await test_async_client()
    
if __name__ == "__main__":
    asyncio.run(main())
