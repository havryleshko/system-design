# System Design Agent

![Architecture](docs/architecture.png)

## Overview
Backend LangGraph system-design agent that runs in LangGraph Studio. Agents execute sequentially—planner → research → design → critic → evals → final_judgement—and produce a final architecture summary plus JSON (`architecture_json`, `design_brief`) and markdown `output`.

## Quickstart (Studio)
1) Set required env vars (see Environment).  
2) Launch LangGraph Studio pointing at the compiled graph.  
3) In Studio, set run metadata (`user_id`, `thread_id`, `run_id`). Memory and store depend on these.  
4) Run the graph. The final message and `output` contain the architecture summary; `architecture_json`/`design_brief` are in state.

## Environment (full list used)
- `OPENAI_API_KEY`  
- `LANGGRAPH_PG_URL` (Postgres for LangGraph store/checkpointer; memory uses this)  
- `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (frontend/Supabase, if applicable)  
- `GITHUB_TOKEN` (optional GitHub enrichment)  
- `TAVILY_API_KEY` (optional web search)  
- Other app vars already present in the repo as needed

## Memory
- Episodic + semantic memory via LangGraph Postgres store.  
- Gated by `metadata.user_id` (and `thread_id`/`run_id`); ensure these are set in run metadata (Studio run config).  
- Checkpointer/store use `LANGGRAPH_PG_URL`.

## Agent Flow
- Planner: scope → steps  
- Research: knowledge_base → github_api → web_search  
- Design: architecture_generator → diagram_generator → output_formatter
- Critic: review → hallucination_check → risk  
- Evals: telemetry → scores → final_judgement  
- Final_judgement: emits user-facing markdown in `messages` and `output`, plus `architecture_json` and `design_brief`.

## Commands (example)
- Install deps: `pip install -r apps/backend/requirements.txt` (and frontend deps if needed).  
- Run Studio (adjust to your command): `langgraph dev` or `langgraph serve` pointing to `apps/backend/app/agent/system_design/graph.py`.  
- Set run metadata in Studio before executing.

## Contributing
PRs welcome. Please keep lint/tests green.

## License
MIT

## Support
Use GitHub Issues.

