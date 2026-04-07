# MVP 快速验证指南

> **Minimum Viable Product — 货架视觉检测 Azure PoC（自有模型版）**  
> 目标：用最少的资源跑通「上传图片 → AML 自有模型推理 → 结果入库」完整链路

---

## 1. MVP 范围

### 保留（核心链路）

```
本地/手动上传图片
        ↓
   Azure Blob Storage [shelfmvpstore001] / [raw-images]
        ↓
   Azure Functions [shelf-mvp-fn-b1]（Blob Trigger）
        ↓
    AML Online Endpoint [shelf-detection-endpoint]（默认 Mock，可切换真实模型适配器）
        ↓
   Azure Cosmos DB [shelf-mvp-cosmos] / [ShelfVisionDB] / [DetectionResults]（Serverless）
        ↓
   Python 脚本查询结果
```

### 移除（降低复杂度）

| 完整方案组件 | MVP 替代方案 | 原因 |
|------------|------------|------|
| Azure IoT Hub | 手动/脚本上传图片到 Blob | 无需真实设备 |
| Azure Event Grid | Blob Trigger 直连 | PoC 延迟可接受 |
| Azure OpenAI | 不使用，直接调 AML 端点 | 验证自有模型接入流程 |
| GPU 实例 | CPU 实例（Standard_DS2_v2） | MVP 阶段 score.py 无需 GPU |
| Azure API Management | 直接查询 Cosmos DB | 无需对外暴露接口 |
| Power BI | Python 脚本打印结果 | 无需可视化配置 |

### 预计成本

> 轻度测试（每天约 100 张图片）。AML Endpoint 按运行时长计费，**测试结束后及时删除 Deployment 可大幅降低成本**。

| 服务 | 规格 | 月估算 |
|------|------|--------|
| Blob Storage | 热层 1 GB | < $0.1 |
| Azure Functions | 消费计划，免费额度内 | $0 |
| Azure Machine Learning | Standard_DS2_v2 CPU × 1（常开） | ~$100 |
| Cosmos DB | Serverless，低 RU | < $1 |
| **合计** | | **~$100/月（按需开关端点可降至 <$10）** |

---

## 2. 前置准备

- Azure 订阅（免费试用账户即可）
- Python 3.10+（本地运行上传/查询脚本）
- Azure CLI（可选，用于命令行创建资源）
- Azure Functions Core Tools（本地调试 Function 用，可选）

安装依赖：

```bash
# 本地运行上传/查询脚本 + AML 部署脚本
pip install azure-storage-blob azure-cosmos azure-ai-ml azure-identity
```

---

## 3. 创建 Azure 资源（约 15 分钟）

### 3.1 创建资源组

在 [portal.azure.com](https://portal.azure.com) 中：

```
+ 创建资源 → 资源组
    名称：[rg-aml-test]
    区域：[westus2]（或离你最近的区域）
```

### 3.2 创建 Storage Account

```
+ 创建资源 → 存储账户
    资源组：[rg-aml-test]
    名称：[shelfmvpstore001]（全局唯一）
  冗余：LRS（本地冗余，成本最低）
```

创建完成后，进入存储账户 → **容器** → 新建：
- *[raw-images]*（存放待检测图片）
- *[results]*（可选）

### 3.3 创建 AML 工作区并部署模拟推理端点

#### 步骤一：在 Portal 创建 AML Workspace

```
+ 创建资源 → 搜索"Azure Machine Learning"
    资源组：[rg-aml-test]
    工作区名称：[amltestworkspace]
    区域：[westus2]（与其他资源同区域）
```

创建完成后记录：
- **订阅 ID**（概述页面）
- **资源组名称**：*[rg-aml-test]*
- **工作区名称**：*[amltestworkspace]*

#### 步骤二：准备模型目录（默认 Mock，可扩展到真实模型）

在本地创建目录 `mock_model/`，建议包含以下文件：

**`mock_model/model_stub.txt`**（默认占位文件；没有真实模型文件时走 Mock）

```
shelf-detection-model-v1-stub
```

**`mock_model/score.py`**（统一推理入口）

- 默认行为：回退到 Mock 结果，确保 MVP 一定可跑通
- 可选行为：如果 `real_model_adapter.py` 已实现并能成功加载，就切到真实模型逻辑

**`mock_model/real_model_adapter.py`**（真实模型适配器模板）

- 在这里加载 `.pt`、`.onnx` 或其他模型文件
- 输入保持和当前 Function 一致：`blob_name`、`image_b64`
- 输出保持和当前 Mock 结果一致：`description`、`compliance_score`、`issues`、`out_of_stock_positions`、`objects`

**`mock_model/model_artifacts/`**（可选）

- 放置真实模型文件，例如 `model.onnx`、`model.pt`
- `deploy_to_aml.py` 会优先注册这个目录；若目录里没有真实模型文件，则自动回退到 `model_stub.txt`

`score.py` 示例：

```python
import json
import os

_adapter = None
_mode = "mock"

def init():
    global _adapter, _mode

    if os.getenv("MODEL_RUNTIME_MODE", "auto").lower() == "mock":
        print("模型初始化完成（Mock）")
        return

    try:
        import real_model_adapter as adapter
        adapter.init_model()
        _adapter = adapter
        _mode = "real"
        print("模型初始化完成（Real Adapter）")
    except Exception as exc:
        print(f"真实模型未启用，回退到 Mock: {exc}")

def run(raw_data):
    payload = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    input_data = payload.get("input_data", payload)

    if _mode == "real" and _adapter is not None:
        result = _adapter.predict(input_data)
    else:
        result = {
            "description": "货架图像分析完成（模拟结果）",
            "compliance_score": 0.82,
            "issues": [],
            "out_of_stock_positions": [],
            "objects": []
        }

    return json.dumps(result)
```

**`mock_model/conda.yml`**（推理环境依赖）

```yaml
channels:
  - conda-forge
dependencies:
  - python=3.10
  - pip:
    - azureml-inference-server-http   # AML 推理服务器（必须）
        - numpy
        - pillow
```

如果真实模型需要额外依赖，例如 `torch`、`onnxruntime-gpu`、`opencv-python-headless`，再按模型框架补充进去。

#### 步骤三：注册模型并部署端点

在本地运行 `deploy_to_aml.py`：

```python
# deploy_to_aml.py
from azure.ai.ml import MLClient
from azure.ai.ml.entities import (
    Model, Environment,
    ManagedOnlineEndpoint, ManagedOnlineDeployment, CodeConfiguration
)
from azure.identity import DefaultAzureCredential

ml_client = MLClient(
    DefaultAzureCredential(),
    subscription_id="<YOUR_SUBSCRIPTION_ID>",
    resource_group_name="[rg-aml-test]",
    workspace_name="[amltestworkspace]"
)

# 1. 注册模型
#    - mock_model/model_artifacts/ 下有真实模型文件时，注册整个目录
#    - 否则回退到 model_stub.txt
model = ml_client.models.create_or_update(
    Model(
        path="<自动选择 model_artifacts/ 或 model_stub.txt>",
        name="[shelf-detection-model]",
        version="1",
        description="货架检测模型（Mock/Real 双模式）"
    )
)

# 2. 注册推理环境
env = ml_client.environments.create_or_update(
    Environment(
        name="[shelf-detection-env]",
        conda_file="./mock_model/conda.yml",
        image="mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04",
    )
)

# 3. 创建 Online Endpoint
endpoint = ml_client.online_endpoints.begin_create_or_update(
    ManagedOnlineEndpoint(
        name="[shelf-detection-endpoint]",
        auth_mode="key"
    )
).result()
print(f"Endpoint 已创建：{endpoint.name}")

# 4. 创建 Deployment（CPU 实例，默认先跑 Mock；接好真实模型后无需改调用链）
deployment = ml_client.online_deployments.begin_create_or_update(
    ManagedOnlineDeployment(
        name="[blue]",
        endpoint_name="[shelf-detection-endpoint]",
        model=model,
        environment=env,
        code_configuration=CodeConfiguration(
            code="./mock_model",
            scoring_script="score.py"
        ),
        instance_type="Standard_DS2_v2",   # CPU 实例，成本最低
        instance_count=1
    )
).result()

# 5. 将 100% 流量切到 [blue]
endpoint.traffic = {"[blue]": 100}
ml_client.online_endpoints.begin_create_or_update(endpoint).result()

# 获取调用信息
endpoint = ml_client.online_endpoints.get("[shelf-detection-endpoint]")
keys = ml_client.online_endpoints.get_keys("[shelf-detection-endpoint]")
print(f"\n端点 URL：{endpoint.scoring_uri}")
print(f"API Key：{keys.primary_key}")
```

```bash
python deploy_to_aml.py
```

记录输出的：
- **端点 URL**：*[https://[shelf-detection-endpoint].[westus2].inference.ml.azure.com/score]*
- **API Key**：primary_key 的值

> **保留 Mock 的同时接真实模型**：
> 1. 将真实模型文件放入 `mock_model/model_artifacts/`
> 2. 在 `mock_model/real_model_adapter.py` 中实现 `init_model()` 和 `predict()`
> 3. 按需在 `conda.yml` 中补充框架依赖
> 4. 重新部署 AML deployment
>
> 如果适配器未完成或加载失败，`score.py` 会自动回退到 Mock 模式，不影响 MVP 联调。

### 3.4 创建 Cosmos DB

```
+ 创建资源 → Azure Cosmos DB → NoSQL API
    资源组：[rg-aml-test]
    账户名：[shelf-mvp-cosmos]
  容量模式：Serverless（按量计费，最省钱）
```

创建完成后：
1. 进入数据资源管理器 → 新建数据库：*[ShelfVisionDB]*
2. 新建容器：
    - 容器 ID：*[DetectionResults]*
   - 分区键：`/storeId`

记录：
- **URI**：在「概述」页面获取
- **主密钥**：在「密钥」页面获取

### 3.5 创建 Function App

```
+ 创建资源 → 函数应用
    资源组：[rg-aml-test]
    名称：[shelf-mvp-fn-b1]（全局唯一）
  运行时堆栈：Python 3.11
  托管计划：消费量（Serverless）
    存储账户：选择 [shelfmvpstore001]
```

---

## 4. 部署 Azure Function

### 4.1 Function 代码

在本地新建文件夹 `shelf_func/`，创建以下文件：

**`function_app.py`**

```python
import azure.functions as func
import logging
import json
import os
import base64
import requests
from datetime import datetime, timezone
from azure.cosmos import CosmosClient

app = func.FunctionApp()

# 从环境变量读取配置（在 Function App → 配置 中设置）
AML_ENDPOINT_URL = os.environ["AML_ENDPOINT_URL"]   # AML 推理端点 URL
AML_API_KEY      = os.environ["AML_API_KEY"]         # AML 端点 Primary Key
COSMOS_URI       = os.environ["COSMOS_URI"]
COSMOS_KEY       = os.environ["COSMOS_KEY"]


@app.blob_trigger(
    arg_name="blob",
    path="[raw-images]/{name}",
    connection="AzureWebJobsStorage"
)
def analyze_shelf_image(blob: func.InputStream):
    blob_name = blob.name.split("/")[-1]
    logging.info(f"[MVP] 检测到新图片：{blob_name}")

    # ── 1. 读取图片并编码为 Base64 ──────────────────────────────
    image_bytes = blob.read()
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    # ── 2. 调用 AML Online Endpoint 推理 ────────────────────────
    headers = {
        "Authorization": f"Bearer {AML_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = json.dumps({"image": b64_image})

    response = requests.post(AML_ENDPOINT_URL, data=payload, headers=headers, timeout=30)
    response.raise_for_status()
    analysis = response.json()

    # ── 3. 整理结果写入 Cosmos DB ──────────────────────────────
    result_doc = {
        "id": blob_name.replace(".", "_"),
        "storeId": "store-mvp-001",        # MVP 阶段固定门店 ID
        "imageName": blob_name,
        "analyzedAt": datetime.now(timezone.utc).isoformat(),
        "model": "[shelf-detection-model]:1",
        "description": analysis.get("description", ""),
        "complianceScore": analysis.get("compliance_score", 0),
        "issues": analysis.get("issues", []),
        "outOfStockPositions": analysis.get("out_of_stock_positions", []),
        "objects": analysis.get("objects", []),
        "objectCount": len(analysis.get("objects", []))
    }

    logging.info(f"[MVP] 合规评分：{result_doc['complianceScore']}，问题数：{len(result_doc['issues'])}")

    # ── 4. 写入 Cosmos DB ────────────────────────────────────────
    cosmos_client = CosmosClient(COSMOS_URI, COSMOS_KEY)
    container = (cosmos_client
                 .get_database_client("[ShelfVisionDB]")
                 .get_container_client("[DetectionResults]"))
    container.upsert_item(result_doc)

    logging.info(f"[MVP] 结果已写入 Cosmos DB：{result_doc['id']}")
```

**`requirements.txt`**

```
azure-functions
requests
azure-cosmos
```

### 4.2 设置 Function App 环境变量

在 Azure Portal → 你的 Function App → **配置** → 应用程序设置，添加：

| 名称 | 值 |
|------|-----|
| `AML_ENDPOINT_URL` | `https://[shelf-detection-endpoint].[westus2].inference.ml.azure.com/score` |
| `AML_API_KEY` | deploy_to_aml.py 输出的 primary_key |
| `COSMOS_URI` | Cosmos DB 的 URI |
| `COSMOS_KEY` | Cosmos DB 的主密钥 |

> `AzureWebJobsStorage` 在创建 Function App 时已自动绑定到 *[shelfmvpstore001]*，无需手动添加。

### 4.3 部署到 Azure

使用 Azure Functions Core Tools：

```bash
cd shelf_func
func azure functionapp publish [shelf-mvp-fn-b1] --python
```

或在 VS Code 中安装 **Azure Functions 扩展**，右键 → Deploy to Function App。

---

## 5. 测试端到端流程

### 5.0 测试流程总览

```mermaid
flowchart TD
    A[上传测试图片<br/>Azure Portal 或 upload_test.py] --> B[Blob Storage<br/><i>[raw-images]</i> 容器]
    B --> C[Azure Functions<br/>Blob Trigger 被触发]
    C --> D[AML Online Endpoint<br/>执行 Mock 或真实模型推理]
    D --> E[Azure Cosmos DB<br/>写入 <i>[DetectionResults]</i>]
    E --> F[结果验证<br/>Portal / query_results.py]

    C --> C1[查看 Function 日志<br/>确认是否触发成功]
    D --> D1[确认无 HTTP 错误<br/>推理返回 JSON]
    E --> E1[确认新增结果文档<br/>字段完整]
```

可以把这张图理解为两条线：

- 主链路：上传图片 → Function 触发 → AML 推理 → Cosmos 入库
- 验证链路：看 Function 日志 → 看 AML 是否返回成功 → 看 Cosmos 是否出现结果文档

### 5.1 上传测试图片

测试图片必须上传到以下 Blob 容器，Function 才会被触发：

- 存储账户：*[shelfmvpstore001]*
- Blob 容器：*[raw-images]*
- 示例 Blob 路径：*[raw-images]/test_shelf.jpg*

**方式 A：Azure Portal（最简单）**

```
存储账户 [shelfmvpstore001] → 容器 [raw-images] → 上传 → 选择本地图片
```

**方式 B：Python 脚本上传**

```python
# upload_test.py
from azure.storage.blob import BlobServiceClient

CONN_STR = "<[shelfmvpstore001] 的连接字符串>"  # 存储账户 → 访问密钥 → 连接字符串

client = BlobServiceClient.from_connection_string(CONN_STR)
container = client.get_container_client("[raw-images]")

# 上传本地图片
with open("test_shelf.jpg", "rb") as f:
    container.upload_blob("test_shelf.jpg", f, overwrite=True)

print("图片上传完成，等待 Function 触发...")
```

```bash
python upload_test.py
```

### 5.2 查看 Function 执行日志

```
Azure Portal → Function App [shelf-mvp-fn-b1]
  → Functions → analyze_shelf_image
  → 监视 → 调用
```

日志示例：

```
[MVP] 检测到新图片：test_shelf.jpg
[MVP] 合规评分：0.75，问题数：2
[MVP] 结果已写入 Cosmos DB：test_shelf_jpg
```

### 5.3 查询 Cosmos DB 结果

**方式 A：Azure Portal 数据资源管理器**

```
Cosmos DB → 数据资源管理器
    → [ShelfVisionDB] → [DetectionResults] → Items
```

**方式 B：Python 查询脚本**

```python
# query_results.py
from azure.cosmos import CosmosClient
import json

COSMOS_URI = "<你的 Cosmos URI>"
COSMOS_KEY = "<你的主密钥>"

client = CosmosClient(COSMOS_URI, COSMOS_KEY)
container = (client
             .get_database_client("[ShelfVisionDB]")
             .get_container_client("[DetectionResults]"))

# 查询最近 10 条记录
items = list(container.query_items(
    query="SELECT TOP 10 * FROM c ORDER BY c._ts DESC",
    enable_cross_partition_query=True
))

for item in items:
    print(f"\n📸 图片：{item['imageName']}")
    print(f"   时间：{item['analyzedAt']}")
    print(f"   描述：{item.get('description', '')}")
    print(f"   合规评分：{item.get('complianceScore', 'N/A')}")
    print(f"   发现问题：{item.get('issues', [])}")
    print(f"   疑似缺货：{item.get('outOfStockPositions', [])}")
    for obj in item.get('objects', []):
        print(f"     - {obj['name']} @ {obj['position']} [{obj['status']}]")
```

```bash
python query_results.py
```

输出示例：

```
📸 图片：test_shelf.jpg
   时间：2026-04-06T10:30:00+00:00
   描述：a shelf with various products
   检测物体数：5
     - bottle (置信度: 0.923)
     - can (置信度: 0.887)
     - box (置信度: 0.841)
     - shelf (置信度: 0.956)
     - product (置信度: 0.812)
```

### 5.4 测试通过标准

完成一次端到端测试后，满足以下条件即可认为 MVP 主链路验证通过：

| 检查项 | 通过标准 |
|------|------|
| Blob 上传 | *[raw-images]* 容器中可以看到刚上传的测试图片 |
| Function 触发 | Function Monitor 中出现对应调用记录，且无未处理异常 |
| Function 日志 | 至少出现以下关键日志：`[MVP] 检测到新图片`、`[MVP] 合规评分`、`[MVP] 结果已写入 Cosmos DB` |
| AML 推理 | Function 未在调用 AML 时抛出 HTTP 错误，说明端点可正常返回 JSON |
| Cosmos DB 入库 | *[DetectionResults]* 容器中新增 1 条与测试图片同名的记录 |
| 结果字段完整性 | 新记录至少包含 `id`、`storeId`、`imageName`、`analyzedAt`、`description`、`complianceScore` |
| 数据可读性 | `issues`、`outOfStockPositions`、`objects` 字段可被正常查询和打印，即使为空数组也算通过 |

建议使用下面的最小验收结论：

```text
上传 1 张测试图片后，若 5 分钟内：
1. Function 成功触发并完成执行
2. Cosmos DB 中出现对应结果文档
3. 文档中的关键字段可正常读取

则判定本次 MVP 端到端测试通过。
```

---

## 6. MVP → 生产的升级路径

当 MVP 验证完核心链路后，按需逐步升级：

```
MVP 现状                        升级方向
─────────────────────────────────────────────────────────
手动上传图片             →  IoT Hub + 边缘设备自动上传
Blob Trigger             →  Event Grid（消除 10 分钟延迟）
Mock score.py （模拟返回）  →  替换为加载真实 .pt 模型文件
CPU 实例 推理            →  GPU 实例（Standard_NC4as_T4_v3）
Python 脚本查询          →  API Management REST 接口
手动看结果               →  Power BI Dashboard
单门店测试               →  多门店 storeId 分区扩展
```

升级无需重写架构——只需把 `mock_model/score.py` 中的 `init()` 改为 `torch.load(".pt")`, `run()` 改为真实推理即可，Function 和 Cosmos DB 代码不变。

---

## 7. 资源清理

测试完成后删除资源组，避免持续计费：

```bash
az group delete --name [rg-aml-test] --yes --no-wait
```

或在 Portal → 资源组 [rg-aml-test] → 删除资源组。

---

*MVP 文档 | Microsoft Azure | April 2026*
