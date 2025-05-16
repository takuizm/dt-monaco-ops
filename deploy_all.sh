#!/bin/bash

# --- 設定 ---
PYTHON_SCRIPT="csv_to_individual_configs.py"
MANIFEST_FILE="manifest.yaml"
ENVIRONMENT_NAME="prod" # environments.yaml から特定

# --- 処理開始 ---

# 1. .envファイルが存在すれば読み込む
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | sed -e 's/\r$//' | xargs) # Windowsの改行コード(CRLF)も考慮
else
    echo "Warning: .env file not found. Please ensure API token and Environment URL environment variables are set."
    echo "e.g., DT_API_TOKEN, DT_ENV_URL or MONACO_TOKEN_PROD, MONACO_ENVIRONMENT_URL_PROD"
fi

echo ""

# 2. Pythonスクリプトを実行してMonaco設定ファイルを生成
echo "[Step 1/2] Generating Monaco configurations from CSV using '$PYTHON_SCRIPT'..."
python3 "$PYTHON_SCRIPT"
if [ $? -ne 0 ]; then
    echo "Error: Python script '$PYTHON_SCRIPT' failed."
    exit 1
fi
echo "Configuration generation complete."
echo ""

# 3. Monacoでデプロイ
echo "[Step 2/2] Deploying configurations with Monaco (Manifest: '$MANIFEST_FILE', Environment: '$ENVIRONMENT_NAME')..."
monaco deploy "$MANIFEST_FILE" --environment "$ENVIRONMENT_NAME"
if [ $? -ne 0 ]; then
    echo "Error: Monaco deploy failed."
    exit 1
fi
echo "Deployment complete!"

exit 0