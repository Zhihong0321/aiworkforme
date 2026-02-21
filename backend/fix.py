import os

path = r"e:\AIworkforMe\backend\src\app\runtime\context_builder.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace(
    "strategy_prompt = self._compile_strategy_prompt(strategy) if strategy else \"Role: Professional Assistant.\"",
    """strategy_prompt = self._compile_strategy_prompt(strategy) if strategy else \"Role: Professional Assistant.\"

        # 1.5 Fetch global context & goal from AgentKnowledgeFile
        global_context_prompt = ""
        agent_goal_prompt = ""
        agent_system_prompt = ""
        
        if agent_id:
            Agent = importlib.import_module("src.adapters.db.agent_models").Agent
            agent = self.session.get(Agent, agent_id)
            if agent and agent.system_prompt:
                agent_system_prompt = agent.system_prompt
                
            AgentKnowledgeFile = importlib.import_module("src.adapters.db.agent_models").AgentKnowledgeFile
            statement = select(AgentKnowledgeFile).where(AgentKnowledgeFile.agent_id == agent_id)
            all_files = self.session.exec(statement).all()
            for f in all_files:
                tags = f.tags or "[]"
                if '"fundamental_context"' in tags:
                    global_context_prompt += f"{f.content}\\n"
                if '"agent_goal"' in tags:
                    agent_goal_prompt += f"{f.content}\\n\""""
)

text = text.replace(
    """        else:
            final_system_instruction = f"{strategy_prompt}\\n{memory_context}\\n{knowledge_context}"
            generation_config = {\"max_tokens\": 2048, \"temperature\": 0.7}
            tools_enabled = True""",
    """        else:
            final_system_instruction = (
                f"{strategy_prompt}\\n"
                f"{'--- AGENT SYSTEM PROMPT ---\\n' + agent_system_prompt + '\\n' if agent_system_prompt else ''}"
                f"{'--- FUNDAMENTAL CONTEXT ---\\n' + global_context_prompt + '\\n' if global_context_prompt else ''}"
                f"{'--- AGENT GOAL ---\\n' + agent_goal_prompt + '\\n' if agent_goal_prompt else ''}"
                f"{memory_context}\\n"
                f"{knowledge_context}"
            )
            generation_config = {"max_tokens": 2048, "temperature": 0.7}
            tools_enabled = True"""
)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
