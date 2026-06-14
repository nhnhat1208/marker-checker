# GreenNode AgentBase Skills

This is a router. The canonical skill definitions live in `.claude/skills/`. When you need to perform any AgentBase task, follow these steps:

1. **Identify the needed skill** based on the user's request:
   - General questions / platform overview / credentials → `.claude/skills/agentbase/`
   - Build or scaffold a new agent → `.claude/skills/agentbase-wizard/`
   - Deploy, runtime management, container registry → `.claude/skills/agentbase-deploy/`
   - Agent identity and outbound auth (API keys, OAuth2) → `.claude/skills/agentbase-identity/`
   - Memory (conversation history, long-term) → `.claude/skills/agentbase-memory/`
   - Logs, metrics, status dashboard → `.claude/skills/agentbase-monitor/`
   - Policy and authorization → `.claude/skills/agentbase-policy/`
   - Resource Gateway (MCP proxy) → `.claude/skills/agentbase-gateway/`
   - LLM model access and platform API keys → `.claude/skills/agentbase-llm/`
   - Tear down all resources → `.claude/skills/agentbase-teardown/`

2. **Read the SKILL.md** at the identified path (e.g., `.claude/skills/agentbase-deploy/SKILL.md`).

3. **Read any referenced sub-documents** listed in that SKILL.md (e.g., `references/`, `scripts/`) as needed to complete the task.

4. **Follow the instructions** in the loaded SKILL.md exactly.

All scripts are located under `.claude/skills/agentbase/scripts/` and are invoked as `bash .claude/skills/agentbase/scripts/<script>.sh`.
