1. Current State Recap
Graph = single chain. apps/backend/app/agent/system_design/graph.py wires a fixed intent → clarifier → planner → kb_search → web_search → designer → critic → finaliser path. There’s no higher-level controller to decide which capabilities to invoke or to revisit earlier stages intelligently.
LangGraph runtime. apps/backend/start.sh still launches langgraph dev. That mode is intended for local experiments and tears down runs/checkpoints on every restart; production should use langgraph serve (or LangGraph Cloud) so run state persists through deployments.
Memory gated on metadata. In nodes.py, hybrid memory only engages when metadata["user_id"] exists; right now, we never populate that metadata when a run starts, so semantic/episodic recall silently short-circuits. Even with PG configured, the store is effectively “off”.
State/trace storage. app/storage/memory.py stores run metadata in in-memory dicts. Any restart wipes traces/token stats, making debugging impossible and forcing the front-end to rely solely on LangGraph Cloud.

2. Architectural Upgrades Needed
A. Core Orchestrator Layer
Build a supervising agent (or controller node) that:
Examines the user goal + context (memory, clarifier answer, metadata).
Chooses which specialist agents to run (planner, KB research, web search, critic, reasoning loops, etc.) and in what order.
Supports re-entrant resumes: when a clarifier answer arrives, the orchestrator rehydrates state and decides the next best action rather than blindly jumping to planner.
Implementation sketch:
Replace the linear graph with a “router” node that outputs the next node name + config (LangGraph supports conditional routing + Command). This router should use metadata like user_id, historical outcomes, and signals (e.g., KB hit count) to decide dynamically.
Introduce agent-specific subgraphs (e.g., ResearchAgent, DesignAgent, CriticAgent) that can be called iteratively. Use Command.resume or shared channels so the orchestrator can loop until success criteria are met.
Store an “orchestration plan” in state (JSON doc with steps, statuses). Each node updates its portion, enabling restarts/resumes.
B. Metadata & Context Propagation
When creating runs, include a metadata object carrying user_id, thread_id, plan_id, etc. (LangGraph Cloud accepts {"config": {"configurable": {...}}} or metadata in the POST body.)
Update ensureSession/createThread/startRunStream to fetch the Supabase user ID and pass it through. Once metadata["user_id"] exists, your hybrid memory logic in nodes.py will actually read/write user-specific history instead of anonymous.
C. Replace langgraph dev with a production runtime
In apps/backend/start.sh, swap langgraph dev for langgraph serve --host 0.0.0.0 --port $PORT --config langgraph.json.
Confirm langgraph.json points to the compiled graph and app/auth.py for auth.
Verify LANGGRAPH_PG_URL, SUPABASE_*, and model keys are present in the deployment environment. Since you already have PG configured, this change stops the abrupt run loss on redeploys.

D. Persistent Run/Trace Store
Options:
Reuse LangGraph checkpointer + store for run metadata: extend langgraph_store to write per-run summaries (status, timestamps, errors) into Postgres. Provide APIs (/runs/{id}) wired to that data.
Add Redis/Postgres tables specifically for run statuses and traces (beyond the checkpointer). Each node already logs events via add_event; persist those events to Postgres to survive restarts.
Use LangSmith or LangGraph Cloud tracing: if you already stream events there, the frontend could query LangSmith APIs for traces instead of the local /runs/{id}/trace.
Pick whichever aligns with your observability stack, but the key is removing the in-memory dict reliance.
3. Memory + Context after Orchestrator
With a real orchestrator:
At run start, hydrate state with:
Latest short-term context (last N messages) from Supabase or checkpointer.
Long-term memory via load_long_term_messages (now keyed per user).
Any domain-specific memories (e.g., previous designs) retrieved by the orchestrator before calling downstream agents.
After each agent completes, log the interaction back into long-term memory using record_long_term_memory.
Because the orchestrator now controls flow, it can decide to refresh memory mid-run (e.g., if critic says “missing compliance requirements”, fetch relevant memories before re-invoking planner).
This solves the gating issue indirectly: once metadata is populated and the orchestrator always requests memory, context management won’t silently drop out.
4. Path to a Multi-Agent System
A concrete roadmap:
Stabilize runtime (short-term):
Switch to langgraph serve.
Ensure LANGGRAPH_PG_URL + other envs exist in LangSmith/Vercel builds.
Persist /runs data in Postgres so traces survive redeploys.
Introduce metadata flow:
Fetch Supabase user.id in ChatClient or actions.ts.
Pass { metadata: { user_id, thread_id } } when invoking runs/resumes.
Update nodes to read/write additional metadata (session goals, plan IDs).
Design orchestrator:
Add a new node, e.g., coordinator, that inspects state and returns the next node or completes with final output.
Break the big chain into modular subgraphs. Example: planner and designer operate within a design_agent subgraph that can be looped by the coordinator.
Use LangGraph’s Structured Messages or RunnableBranch to implement routing logic with guardrails.
Agent specialization:
Create dedicated agents with their own prompts/tools: KBResearchAgent, MarketDataAgent, ArchitectureAgent, CriticAgent.
Expose toolkits (Polymarket API, Perplexity Finance, etc.) per agent and let the orchestrator compose them as needed.
Memory + knowledge integration:
After metadata fix, expand langgraph_store usage: semantic search for past designs, user preferences, prior clarifier answers.
Optionally add external vector DB (Supabase pgvector) for domain documents and integrate via the orchestrator.
Observability & retries:
Add health checks before runs (call /health/checkpointer).
Implement retry logic if resume returns 404 due to redeploy—e.g., auto-restart the run when the orchestrator sees missing checkpoints.
Leverage LangSmith tracing to monitor agent-level timings and failures.
Once those layers are in place, you’ll have:
A resilient backend that keeps run state across deployments.
True multi-agent coordination instead of a fixed chain.
Functional long-/short-term memory keyed per user.
Persistent traces/metrics for debugging.
