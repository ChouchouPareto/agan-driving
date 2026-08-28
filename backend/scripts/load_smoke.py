"""Small staging load-smoke runner for the agent entry path.

Example:
  .venv/bin/python scripts/load_smoke.py --base-url https://staging.example.com/api/v1 --requests 200 --concurrency 20
"""

import argparse
import asyncio
import statistics
import time

import httpx


async def run_one(client: httpx.AsyncClient, base_url: str, token: str, index: int) -> tuple[float, bool, str]:
    started = time.perf_counter()
    try:
        response = await client.post(
            f"{base_url}/agent/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "text": "我最近练车有点紧张，应该怎么调整？",
                "license_type": "C1",
                "subject": "subject-1",
                "conversation_id": None,
            },
        )
        response.raise_for_status()
        return (time.perf_counter() - started) * 1000, True, ""
    except (httpx.HTTPError, KeyError) as exc:
        return (time.perf_counter() - started) * 1000, False, f"{type(exc).__name__}:{index}"


async def main() -> int:
    parser = argparse.ArgumentParser(description="阿甘学车测试环境轻量压力冒烟")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--invite", default="INVITE_CODE_REMOVED")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1 or args.concurrency > 200:
        parser.error("requests 必须大于 0，concurrency 必须在 1 到 200 之间")

    semaphore = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(timeout=args.timeout) as client:
        auth = await client.post(f"{args.base_url.rstrip('/')}/auth/invitations/verify", json={"code": args.invite})
        auth.raise_for_status()
        token = auth.json()["access_token"]

        async def limited(index: int):
            async with semaphore:
                return await run_one(client, args.base_url.rstrip("/"), token, index)

        wall_started = time.perf_counter()
        results = await asyncio.gather(*(limited(index) for index in range(args.requests)))
        wall_seconds = time.perf_counter() - wall_started

    latencies = sorted(item[0] for item in results)
    successes = sum(1 for _, ok, _ in results if ok)
    percentile = lambda ratio: latencies[min(len(latencies) - 1, int((len(latencies) - 1) * ratio))]
    print(f"requests={args.requests} concurrency={args.concurrency} success={successes} errors={args.requests - successes}")
    print(f"throughput={args.requests / wall_seconds:.2f} req/s mean={statistics.mean(latencies):.1f}ms p50={percentile(.50):.1f}ms p95={percentile(.95):.1f}ms p99={percentile(.99):.1f}ms")
    return 0 if successes == args.requests else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
