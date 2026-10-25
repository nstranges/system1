"""Modal entry point the product server calls (ModalTrainer): train a project's LoRA, then score it and the
untrained base on the project's frozen test examples. Deploy with `make modal-deploy`.

Reuses train.py's steps unchanged. Not exercised without a GPU: smoke-test with a small project first.
"""
import json
import time

import modal

from train import app, calibrate_model, data_config, image, model_config, save_adapter, start_training, vol

PROGRESS_DICT = "system1-progress"
pipeline_image = image.add_local_python_source("train")

with pipeline_image.imports():
    from tqdm.auto import tqdm
    from transformers import TrainerCallback
    from unsloth import FastDecisionModel

def predict_rows(model, tokenizer, test_rows):
    """Answer every test row; returns [{id, pred, p_gold, latency_ms}] (the server scores against its own gold)."""
    out = []
    for row in tqdm(test_rows, desc = "Predicting", unit = "row"):
        questions = json.loads(row["questions"])
        name = next(iter(questions))
        gold = json.loads(row["gold"])[name]["label"].lower()
        started = time.perf_counter()
        result = FastDecisionModel.predict(model, tokenizer, row["state"], questions)[name]
        probs = {str(k).lower(): float(v) for k, v in result["probabilities"].items()}
        out.append({
            "id": row["id"],
            "pred": str(result["answer"]),
            "p_gold": probs.get(gold, 0.0),
            "latency_ms": (time.perf_counter() - started) * 1000,
        })
    return out

class LiveProgress(TrainerCallback if "TrainerCallback" in globals() else object):
    """Reports step, epoch and loss to the progress Dict, at most every few seconds, for the product's details view."""

    def __init__(self, push, every = 3.0):
        self.push, self.every, self.last = push, every, 0.0
        self.loss, self.eval_loss = [], []

    def _send(self, state, force = False):
        if not force and time.monotonic() - self.last < self.every:
            return
        self.last = time.monotonic()
        stride = max(1, len(self.loss) // 200)  # keep the payload small on long runs
        self.push({
            "step": state.global_step,
            "total_steps": state.max_steps,
            "epoch": round(state.epoch or 0, 2),
            "history": self.loss[::stride],
            "eval_history": self.eval_loss,
        })

    def on_log(self, args, state, control, logs = None, **kwargs):
        if logs and "loss" in logs:
            self.loss.append([state.global_step, round(float(logs["loss"]), 4)])
        self._send(state)

    def on_evaluate(self, args, state, control, metrics = None, **kwargs):
        if metrics and "eval_loss" in metrics:
            self.eval_loss.append([round(state.epoch or 0, 2), round(float(metrics["eval_loss"]), 4)])
        self._send(state, force = True)

@app.function(image = pipeline_image, gpu = "L4", timeout = 60 * 60 * 2)
def evaluate_base(test_rows):
    """Untrained Laya on the test rows (same load as eval_laya.py)."""
    model, tokenizer = FastDecisionModel.from_pretrained(
        model_name = "convaiinnovations/laya", max_seq_length = 512, load_in_4bit = False
    )
    FastDecisionModel.for_inference(model)
    return predict_rows(model, tokenizer, test_rows)

@app.function(image = pipeline_image, gpu = "L4", timeout = 60 * 60 * 4, volumes = {"/outputs": vol})
def run_project(payload):
    """payload: {project_id, epochs, rows (train + cal), test_rows}. Stages match the server's progress names."""
    call_id = modal.current_function_call_id()
    progress = modal.Dict.from_name(PROGRESS_DICT, create_if_missing = True)

    def stage(name, **detail):
        progress[call_id] = {"stage": name, **detail}

    base_call = evaluate_base.spawn(payload["test_rows"])  # runs on its own GPU while this one trains

    stage("preparing")
    model, tokenizer = model_config()
    train_items, eval_items, cal_items = data_config(tokenizer, model, payload["rows"], "labels")

    stage("learning")
    live = LiveProgress(lambda detail: stage("learning", **detail))
    stats = start_training(model, tokenizer, train_items, eval_items, payload["epochs"], [live])

    stage("checking")
    calibration = calibrate_model(model, tokenizer, cal_items)
    folder = f"/outputs/projects/{payload['project_id']}/{call_id}"
    save_adapter(model, tokenizer, folder)
    vol.commit()

    stage("testing")
    FastDecisionModel.for_inference(model)
    sys1 = predict_rows(model, tokenizer, payload["test_rows"])
    base = base_call.get()
    return {
        "adapter_ref": f"laya-outputs:{folder.removeprefix('/outputs/')}",
        "metrics": json.loads(json.dumps({"train": getattr(stats, "metrics", {}), "calibration": calibration}, default = str)),
        "evaluations": {"sys1": sys1, "base": base},
    }
