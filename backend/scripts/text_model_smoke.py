import time

from app.services import AIService, QUESTION_BANK


def main() -> None:
    service = AIService()
    if not service.settings.dashscope_api_key:
        raise SystemExit("SKIP: DASHSCOPE_API_KEY is not configured")
    match = QUESTION_BANK["驾驶机动车通过没有交通信号的交叉路口怎样行驶"]
    started = time.monotonic()
    result = service.answer("驾驶机动车通过没有交通信号的交叉路口怎样行驶？", match)
    if service.is_mock:
        raise SystemExit(f"FAIL: real model was not used ({service.error_type or 'unknown'})")
    if result.direct_answer != match["answer"]:
        raise SystemExit("FAIL: locked answer changed")
    first = {"model": service.model_id, "tokens": service.token_usage, "latency_ms": int((time.monotonic() - started) * 1000), "detail_length": len(result.detail)}
    follow_up = AIService()
    started = time.monotonic()
    second = follow_up.answer("为什么要让右方来车先行？", match, explain_again=True)
    if follow_up.is_mock or second.direct_answer != match["answer"]:
        raise SystemExit(f"FAIL: follow-up model was not safely used ({follow_up.error_type or 'unknown'})")
    print({"status": "PASS", "first": first, "follow_up": {"model": follow_up.model_id, "tokens": follow_up.token_usage, "latency_ms": int((time.monotonic() - started) * 1000), "detail_length": len(second.detail)}})


if __name__ == "__main__":
    main()
