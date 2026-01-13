import unittest

from app.services.threads import _build_initial_run_state


class TestRunStateReset(unittest.TestCase):
    def test_build_initial_run_state_resets_run_scoped_fields(self) -> None:
        # Regression guard:
        # - LangGraph checkpointer is keyed by `thread_id`, so state persists across runs.
        # - If a previous run ends with run_phase="done", a new run must NOT inherit it,
        #   otherwise orchestrator routes to END immediately and returns stale output.
        meta = {"user_id": "u", "thread_id": "t", "run_id": "r"}
        state = _build_initial_run_state(prompt="new prompt", metadata=meta)

        self.assertEqual(state["run_phase"], "planner")
        self.assertEqual(state["output"], "")
        self.assertEqual(state["plan_scope"], {})
        self.assertEqual(state["plan_state"], {})
        self.assertEqual(state["research_state"], {})
        self.assertEqual(state["design_state"], {})
        self.assertEqual(state["critic_state"], {})
        self.assertEqual(state["eval_state"], {})
        self.assertEqual(state["orchestrator"], {})
        self.assertEqual(state["selected_patterns"], [])


