"""
Simulate exactly what the inbound worker does for message id=12 (text='Hi').
This runs locally with the production DB to reproduce the exact error.
"""
import asyncio
import os
import sys

# Point at production DB
os.environ["DATABASE_URL"] = "postgres://postgres:qsLdbwueuhAJKIsVvhn06~77IvUMNbAz@turntable.proxy.rlwy.net:23554/railway"

async def main():
    from sqlmodel import Session
    from src.infra.database import engine
    from src.adapters.api.dependencies import llm_router
    from src.adapters.db.tenant_models import SystemSetting

    with Session(engine) as session:
        # Step 1: Load keys from DB (simulate startup)
        print("=== LOADING KEYS FROM DB ===")
        zai_setting = session.get(SystemSetting, "zai_api_key")
        uni_setting = session.get(SystemSetting, "uniapi_key")
        print(f"  zai_api_key in DB: {bool(zai_setting and zai_setting.value)}")
        print(f"  uniapi_key in DB:  {bool(uni_setting and uni_setting.value)}")

        if zai_setting and zai_setting.value:
            os.environ["ZAI_API_KEY"] = zai_setting.value
            zai_prov = llm_router.providers.get("zai")
            if zai_prov:
                zai_prov.api_key = zai_setting.value
                zai_prov._init_client()
                print("  ZaiProvider reinitialised.")

        print()
        print("=== PROVIDER HEALTH ===")
        for name, prov in llm_router.providers.items():
            print(f"  {name}: healthy={prov.is_healthy()}")

        print()
        print("=== SIMULATING run_turn for lead=3, workspace=1, agent=1 ===")
        from src.app.runtime.agent_runtime import ConversationAgentRuntime
        runtime = ConversationAgentRuntime(session, llm_router)
        try:
            result = await runtime.run_turn(
                lead_id=3,
                workspace_id=1,
                user_message="Hi",
                agent_id_override=1,
                bypass_safety=True,
                history_override=[],
            )
            print(f"  SUCCESS: {result}")
        except Exception as e:
            import traceback
            print(f"  FAILED: {type(e).__name__}: {e}")
            traceback.print_exc()

asyncio.run(main())
