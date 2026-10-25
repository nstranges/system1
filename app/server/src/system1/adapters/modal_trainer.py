import json
from typing import Any, Protocol

from system1.contracts.training import EvalAnswer, TrainingJob

STAGES = ("preparing", "learning", "checking", "testing")


class ModalRunner(Protocol):
    """The slice of Modal the trainer needs, so tests don't need Modal."""

    def spawn(self, payload: dict) -> str: ...

    def poll(self, call_id: str) -> tuple[str, Any]:
        """("running", None), ("done", result dict) or ("failed", message)."""
        ...

    def stage(self, call_id: str) -> str | None: ...


class SdkModalRunner:
    """Calls the function deployed by `make modal-deploy`. Needs the `modal` extra and Modal's own auth."""

    def __init__(self, app_name: str, function_name: str, progress_name: str):
        self._app_name, self._function_name, self._progress_name = app_name, function_name, progress_name

    def spawn(self, payload: dict) -> str:
        import modal

        function = modal.Function.from_name(self._app_name, self._function_name)
        return function.spawn(payload).object_id

    def poll(self, call_id: str) -> tuple[str, Any]:
        import modal
        from modal.exception import FunctionTimeoutError
        from modal.exception import TimeoutError as NotReady

        try:
            return "done", modal.FunctionCall.from_id(call_id).get(timeout=0)
        except FunctionTimeoutError:  # the function hit its own time limit
            return "failed", "Training ran past its time limit."
        except (NotReady, TimeoutError):  # no output yet; get(timeout=0) raises the built-in one
            return "running", None
        except modal.exception.Error as exc:
            return "failed", str(exc) or type(exc).__name__
        except Exception as exc:  # noqa: BLE001 - an exception raised inside the remote function is re-raised here as its own type
            return "failed", str(exc) or type(exc).__name__

    def stage(self, call_id: str) -> str | None:
        import modal

        progress = modal.Dict.from_name(self._progress_name, create_if_missing=True)
        return (progress.get(call_id) or {}).get("stage")


class ModalTrainer:
    """Trains a LoRA on Modal (pipeline.py), and scores it and the untrained base on the test examples there."""

    needs_examples = True

    def __init__(self, runner: ModalRunner, epochs: int = 1):
        self._runner = runner
        self._epochs = epochs

    def start(self, dataset_ref: str, config: dict) -> TrainingJob:
        key = next(iter(config["questions"]))
        questions = json.dumps(config["questions"])

        def row(e: dict) -> dict:
            state = e["input"] if isinstance(e["input"], str) else json.dumps(e["input"])
            return {
                "id": e["id"],
                "split": e["split"],
                "state": state,
                "gold": json.dumps({key: {"type": "choice", "label": e["label"]}}),
            }

        examples = config["examples"]
        payload = {
            "project_id": config["project_id"],
            "epochs": self._epochs,
            # train.py picks its question set by column name; the test rows are only scored, never trained on.
            "rows": [{**row(e), "questions_labels": questions} for e in examples if e["split"] != "test"],
            "test_rows": [{**row(e), "questions": questions} for e in examples if e["split"] == "test"],
        }
        return TrainingJob(id=self._runner.spawn(payload), status="queued", message="Queued.")

    def status(self, job_id: str) -> TrainingJob:
        state, value = self._runner.poll(job_id)
        if state == "running":
            stage = self._runner.stage(job_id)
            return TrainingJob(
                id=job_id, status="running", message="Training.", metrics={"stage": stage} if stage in STAGES else {}
            )
        if state == "failed":
            return TrainingJob(id=job_id, status="failed", message=f"Training didn't finish: {value}")
        return TrainingJob(
            id=job_id,
            status="succeeded",
            message="Done.",
            adapter_ref=value.get("adapter_ref"),
            metrics=value.get("metrics", {}),
            evaluations={
                lane: [EvalAnswer(**a) for a in answers] for lane, answers in value.get("evaluations", {}).items()
            },
        )
