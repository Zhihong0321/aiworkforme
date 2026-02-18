"""
Diagnostic: test the actual LLM router call exactly as the inbound worker does.
Run this on the production server to see the real error.
"""
import asyncio
import os
import sys

async def main():
    print("=== ENV VARS CHECK ===")
    zai_key = os.getenv("ZAI_API_KEY", "")
    uniapi_key = os.getenv("UNIAPI_API_KEY", "")
    print(f"ZAI_API_KEY set: {bool(zai_key)} (len={len(zai_key)})")
    print(f"UNIAPI_API_KEY set: {bool(uniapi_key)} (len={len(uniapi_key)})")

    print()
    print("=== LLM ROUTER HEALTH ===")
    from src.adapters.api.dependencies import llm_router
    from src.infra.llm.schemas import LLMTask
    for name, provider in llm_router.providers.items():
        print(f"  provider '{name}': healthy={provider.is_healthy()}")
    print(f"  routing: CONVERSATION -> {llm_router.routing_config.get(LLMTask.CONVERSATION)}")

    print()
    print("=== TEST LLM CALL (CONVERSATION) ===")
    try:
        response = await llm_router.execute(
            task=LLMTask.CONVERSATION,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello in one word."}
            ]
        )
        print(f"SUCCESS: {response.content!r}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

asyncio.run(main())
