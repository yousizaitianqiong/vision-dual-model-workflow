from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflow" / "dify-vision-dual-model-demo.yml"


def test_dify_workflow_shape_and_sanitized_endpoint():
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    graph = document["workflow"]["graph"]

    assert document["version"] == "0.7.0"
    assert len(graph["nodes"]) == 6
    assert len(graph["edges"]) == 5
    assert "http://media-preprocess:8002/v1/media/prepare" in WORKFLOW.read_text(encoding="utf-8")
    assert "remote_url" not in WORKFLOW.read_text(encoding="utf-8")
    assert document["workflow"]["environment_variables"][0]["name"] == "qwen_vision_model"
    assert document["workflow"]["environment_variables"][1]["name"] == "sensenova_vision_model"
