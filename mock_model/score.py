import json
import os
import random
from typing import Any


_ADAPTER = None
_RUNTIME_MODE = "mock"


def _mock_result() -> dict[str, Any]:
    return {
        "description": "货架图像分析完成（模拟结果）",
        "compliance_score": round(random.uniform(0.65, 0.97), 2),
        "issues": random.sample(
            ["第二层中间缺货", "价签遮挡商品", "商品摆放错位"],
            k=random.randint(0, 2),
        ),
        "out_of_stock_positions": ["第二层第3–4格"] if random.random() > 0.6 else [],
        "objects": [
            {"name": "Coca-Cola 330ml", "position": "第一层左侧", "status": "in_stock"},
            {"name": "百事可乐 330ml", "position": "第一层右侧", "status": "in_stock"},
            {"name": "农夫山泉 550ml", "position": "第二层左侧", "status": "in_stock"},
        ],
    }


def _parse_request(raw_data: Any) -> dict[str, Any]:
    if isinstance(raw_data, (bytes, bytearray)):
        raw_data = raw_data.decode("utf-8")

    if isinstance(raw_data, str):
        payload = json.loads(raw_data)
    elif isinstance(raw_data, dict):
        payload = raw_data
    else:
        raise TypeError(f"Unsupported request type: {type(raw_data)!r}")

    return payload.get("input_data", payload)


def init():
    global _ADAPTER, _RUNTIME_MODE

    requested_mode = os.getenv("MODEL_RUNTIME_MODE", "auto").lower()

    if requested_mode == "mock":
        _RUNTIME_MODE = "mock"
        print("模型初始化完成（Mock）")
        return

    try:
        import real_model_adapter as adapter

        adapter.init_model()
        _ADAPTER = adapter
        _RUNTIME_MODE = "real"
        print("模型初始化完成（Real Adapter）")
    except Exception as exc:
        _ADAPTER = None
        _RUNTIME_MODE = "mock"
        print(f"真实模型适配器未启用，回退到 Mock 模式: {exc}")


def run(raw_data):
    input_data = _parse_request(raw_data)

    if _RUNTIME_MODE == "real" and _ADAPTER is not None:
        result = _ADAPTER.predict(input_data)
    else:
        result = _mock_result()

    return json.dumps(result, ensure_ascii=False)
