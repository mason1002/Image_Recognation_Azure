"""Register model assets and deploy the AML online endpoint.

Behavior:
- If real model files exist under mock_model/model_artifacts/, register that folder.
- Otherwise register model_placeholder.txt and keep the endpoint in mock mode.
"""
import os

from azure.ai.ml import MLClient
from azure.ai.ml.entities import (
    Model, Environment,
    ManagedOnlineEndpoint, ManagedOnlineDeployment, CodeConfiguration
)
from azure.identity import DefaultAzureCredential
from pathlib import Path

def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


SUBSCRIPTION_ID = _require_env("AZURE_SUBSCRIPTION_ID")
RESOURCE_GROUP  = _require_env("AZURE_RESOURCE_GROUP")
WORKSPACE_NAME  = _require_env("AZURE_ML_WORKSPACE")
ENDPOINT_NAME   = os.getenv("AZURE_ML_ENDPOINT_NAME", "shelf-detection-endpoint")
MODEL_NAME      = os.getenv("AZURE_ML_MODEL_NAME", "shelf-detection-model")
ENV_NAME        = os.getenv("AZURE_ML_ENV_NAME", "shelf-inference-env")
MODEL_ARTIFACTS_DIR = Path("./mock_model/model_artifacts")
MODEL_PLACEHOLDER_PATH = Path("./mock_model/model_placeholder.txt")


def resolve_model_path() -> Path:
    real_model_extensions = {".onnx", ".pt", ".pth", ".pb", ".joblib", ".pkl"}

    if MODEL_ARTIFACTS_DIR.exists():
        for path in MODEL_ARTIFACTS_DIR.rglob("*"):
            if path.is_file() and path.suffix.lower() in real_model_extensions:
                return MODEL_ARTIFACTS_DIR

    return MODEL_PLACEHOLDER_PATH

ml_client = MLClient(
    DefaultAzureCredential(),
    subscription_id=SUBSCRIPTION_ID,
    resource_group_name=RESOURCE_GROUP,
    workspace_name=WORKSPACE_NAME
)

# 1. 注册模型
print(">>> 注册模型...")
model_path = resolve_model_path()
is_real_model = model_path == MODEL_ARTIFACTS_DIR
model = ml_client.models.create_or_update(
    Model(
        path=str(model_path),
        name=MODEL_NAME,
        version="1",
        description=(
            "货架检测模型（真实模型目录）"
            if is_real_model
            else "货架检测模型（MVP Mock 版本）"
        )
    )
)
print(f"    模型已注册：{model.name}:{model.version}")
print(f"    模型路径：{model_path}")

# 2. 注册推理环境
print(">>> 注册推理环境...")
env = ml_client.environments.create_or_update(
    Environment(
        name=ENV_NAME,
        conda_file="./mock_model/conda.yml",
        image="mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04",
    )
)
print(f"    环境已注册：{env.name}")

# 3. 创建 Online Endpoint
print(">>> 创建 Endpoint...")
endpoint = ml_client.online_endpoints.begin_create_or_update(
    ManagedOnlineEndpoint(name=ENDPOINT_NAME, auth_mode="key")
).result()
print(f"    Endpoint 已就绪：{endpoint.name}")

# 4. 创建 Deployment（CPU 实例）
print(">>> 部署模型（CPU，Standard_DS2_v2）...")
deployment = ml_client.online_deployments.begin_create_or_update(
    ManagedOnlineDeployment(
        name="blue",
        endpoint_name=ENDPOINT_NAME,
        model=model,
        environment=env,
        code_configuration=CodeConfiguration(
            code="./mock_model",
            scoring_script="score.py"
        ),
        instance_type="Standard_DS2_v2",
        instance_count=1
    )
).result()
print(f"    Deployment 已就绪：{deployment.name}")

# 5. 将 100% 流量切到 blue
endpoint.traffic = {"blue": 100}
ml_client.online_endpoints.begin_create_or_update(endpoint).result()

# 获取调用信息
endpoint = ml_client.online_endpoints.get(ENDPOINT_NAME)
keys = ml_client.online_endpoints.get_keys(ENDPOINT_NAME)

print("\n========================================")
print(f"端点 URL : {endpoint.scoring_uri}")
print(f"API Key  : {keys.primary_key}")
print("========================================\n")
print("请将以上两个值设置到 Function App 的环境变量中：")
print("  AML_ENDPOINT_URL = <端点 URL>")
print("  AML_API_KEY      = <API Key>")
print("\n部署前请先设置：AZURE_SUBSCRIPTION_ID / AZURE_RESOURCE_GROUP / AZURE_ML_WORKSPACE")
print("\n可选：在 AML 部署环境变量中设置 MODEL_RUNTIME_MODE=mock|auto 控制是否启用真实模型适配器。")
