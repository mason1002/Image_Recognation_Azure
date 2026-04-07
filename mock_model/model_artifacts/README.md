Put real model files in this directory when you are ready to replace the mock flow.

Supported by the current deployment script:

- If this folder contains a real model file such as .onnx, .pt, .pth, .pb, .joblib, or .pkl,
  deploy_to_aml.py will register the whole folder as the AML model asset.
- If no such file exists, the deployment falls back to mock_model/model_stub.txt.

Typical next step:

1. Add model.onnx or model.pt here.
2. Implement mock_model/real_model_adapter.py.
3. Add any extra runtime dependencies to mock_model/conda.yml.
4. Redeploy the AML online deployment.
