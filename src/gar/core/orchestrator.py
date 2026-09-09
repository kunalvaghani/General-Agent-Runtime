"""Single bounded runtime shared by CLI and API."""

from gar.core.executor import Executor
from gar.core.planner import Planner, PlanningService
from gar.core.state import Plan, TaskStatus
from gar.core.verifier import Verifier


class Orchestrator:
    def __init__(self, repo, adapter, tools, memory=None):
        self.repo, self.adapter, self.tools = repo, adapter, tools
        self.memory = memory

    async def run(self, task_id, approval_id=None, retry=False):
        task = self.repo.get(task_id)
        if self.repo.get_plan(task_id) is None:
            context = ""
            if self.memory:
                context = "\n".join(
                    i.content for i in self.memory.search(source=task_id, category="working")
                )[:20000]
            await PlanningService(self.repo, Planner(self.adapter)).plan_task(task_id, context)
        if retry:
            self.repo.prepare_retry(task_id)
        task = self.repo.get(task_id)
        if task.status != TaskStatus.VERIFYING:
            task = await Executor(self.repo, self.adapter, self.tools).run(task_id, approval_id)
        if task.status == TaskStatus.VERIFYING:
            await Verifier().verify(self.repo, task_id, self.tools)
        result = self.repo.get(task_id)
        if result.is_terminal and self.memory:
            from gar.learning.reflection import reflect

            reflect(result, self.memory)
        return result

    async def replan(self, task_id):
        task = self.repo.get(task_id)
        if task.status != TaskStatus.BLOCKED:
            raise ValueError("Only blocked tasks can replan")
        count = task.metadata.get("replans", 0)
        if count >= 2:
            raise ValueError("Replan limit reached")
        previous = self.repo.get_plan(task_id)
        task = self.repo.transition(task_id, TaskStatus.PLANNING, task.version)
        proposal = await Planner(self.adapter).create_plan(task, str(task.metadata)[-20000:])
        proposal = Plan.model_validate(
            {**proposal.model_dump(), "revision": previous.revision + 1 if previous else 1}
        )
        from gar.core.events import EventType

        task = self.repo.checkpoint(
            task_id,
            {"metadata": {**task.metadata, "replans": count + 1}},
            task.version,
            EventType.MODEL_RESPONDED,
            {"role": "replanner"},
        )
        self.repo.save_plan(proposal, task.version)
        return self.repo.get(task_id)
