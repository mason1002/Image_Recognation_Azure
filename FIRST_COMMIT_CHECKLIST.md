# First Commit Checklist

## Repo Scope

This repository should contain only the files required to explain and run the MVP.

Included in the initial commit:

- `README.md`
- `MVP.md`
- `assets/architecture-overview.svg`
- `deploy_to_aml.py`
- `mock_model/conda.yml`
- `mock_model/score.py`
- `mock_model/real_model_adapter.py`
- `mock_model/model_stub.txt`
- `mock_model/model_artifacts/README.md`
- `shelf_func/function_app.py`
- `shelf_func/host.json`
- `shelf_func/requirements.txt`
- `.gitignore`

Excluded from the initial commit:

- `generate_ppt.py`
- `generate_drawio.py`
- `*.pptx`
- `*.pdf`
- `*.drawio`
- `enable_storage_test_access.cmd`
- `disable_storage_test_access.cmd`
- `testImage/`
- `*.zip`
- `.venv/`
- `local.settings.json`
- `shelf_func/.python_packages/`

## Security Checks

- Confirm no real `AML_API_KEY`, storage connection string, SAS token, or account key is present in any tracked file.
- Confirm no real Azure access tokens, CLI output dumps, or deployment logs are present in the repo.
- Confirm no customer data, shelf photos, or test images are included.
- Confirm `deploy_to_aml.py` uses environment variables for subscription, resource group, and workspace.
- Confirm `shelf_func/function_app.py` does not hardcode private blob account URLs or temporary debug upload routes.

## Functional Checks

- Confirm `README.md` and `MVP.md` describe the MVP flow accurately.
- Confirm `README.md` image renders correctly from `assets/architecture-overview.svg`.
- Confirm `shelf_func/requirements.txt` matches imports used by `shelf_func/function_app.py`.
- Confirm `mock_model/score.py` still supports mock mode by default.
- Confirm `mock_model/model_artifacts/README.md` is only guidance text and contains no real model file.

## Before First Commit

- Run `git status` and verify only intended MVP files appear.
- Run a final secret scan if you add any new files.
- Add a repository description similar to: `Azure MVP for shelf image recognition with Functions, AML endpoint, and Cosmos DB`.
- If you create the remote repository later, use the name `Image_Recognation_Azure`.

## Suggested First Commands

```powershell
git status
git add .
git status
git commit -m "Initial MVP commit"
```