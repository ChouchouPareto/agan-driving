from app.services import AIService, QUESTION_BANK


def main() -> None:
    service = AIService()
    if not service.settings.dashscope_api_key:
        raise SystemExit("SKIP: DASHSCOPE_API_KEY is not configured")
    match = QUESTION_BANK["驾驶机动车通过没有交通信号的交叉路口怎样行驶"]
    result = service.answer("驾驶机动车通过没有交通信号的交叉路口怎样行驶？", match)
    if service.is_mock:
        raise SystemExit(f"FAIL: real model was not used ({service.error_type or 'unknown'})")
    if result.direct_answer != match["answer"]:
        raise SystemExit("FAIL: locked answer changed")
    print({"status": "PASS", "model": service.model_id, "tokens": service.token_usage, "detail_length": len(result.detail)})


if __name__ == "__main__":
    main()
