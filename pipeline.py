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

    def stage(name):
        progress[call_id] = {"stage": name}

    base_call = evaluate_base.spawn(payload["test_rows"])  # runs on its own GPU while this one trains

    stage("preparing")
    model, tokenizer = model_config()
    train_items, eval_items, cal_items = data_config(tokenizer, model, payload["rows"], "labels")

    stage("learning")
    stats = start_training(model, tokenizer, train_items, eval_items, payload["epochs"])

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
