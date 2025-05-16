import csv
import os
import json

# --- 設定項目 ---
CSV_FILE_PATH = os.path.join('vars', 'monitors.csv')
OUTPUT_PROJECT_BASE_DIR = os.path.join('projects', 'synthetic-monitor') # ここに <monitor_id> ディレクトリが作られる
TEMPLATE_FILE_NAME = 'monitor.json' # 各モニター設定ディレクトリ内に作られるJSONファイル名
PROJECT_FILE_NAME = 'project.yaml' # 各モニター設定ディレクトリ内に作られるYAMLファイル名
# --- 設定項目ここまで ---

def create_monitor_json_content(row_data):
    """CSVの1行データから monitor.json の内容を生成する"""
    
    # locations の処理 (セミコロン区切りの文字列をリストに)
    locations_list = []
    if row_data.get('locations'): # CSVのヘッダー名 'locations' に注意 (現状は location_id)
        locations_list = [loc.strip() for loc in row_data['locations'].split(';') if loc.strip()]
    elif row_data.get('location_id'): # 'location_id' 列もフォールバックとしてチェック
        locations_list = [loc.strip() for loc in row_data['location_id'].split(';') if loc.strip()]
    else:
        locations_list = ["GEOLOCATION-7F39AED31559436D"] # デフォルト

    # tags の処理
    tags_list = []
    # 1. 必須タグ列からタグを生成
    required_tags_map = {
        "Purpose": row_data.get("tag_purpose"),
        "Industry": row_data.get("tag_industry"),
        "Owner": row_data.get("tag_owner"),
        "ExpiryDate": row_data.get("tag_expiry_date")
    }
    for key, value in required_tags_map.items():
        if value and value.strip(): # 値が存在する場合のみタグを追加
            tags_list.append({"context": "CONTEXTLESS", "key": key, "value": value.strip()})

    # 2. 汎用タグ列 (tag_custom) からタグを生成
    custom_tags_str = row_data.get("tag_custom")
    if custom_tags_str and custom_tags_str.strip():
        custom_tag_pairs = [tag.strip() for tag in custom_tags_str.split(';') if tag.strip()]
        for pair_str in custom_tag_pairs:
            if ':' in pair_str:
                key, value = pair_str.split(':', 1)
                tags_list.append({"context": "CONTEXTLESS", "key": key.strip(), "value": value.strip()})
            else:
                tags_list.append({"context": "CONTEXTLESS", "key": pair_str.strip()})

    # 3. デフォルトタグ (上記のタグが一つも設定されなかった場合)
    if not tags_list:
        tags_list.append({"context": "CONTEXTLESS", "key": "MonacoCsvGenerated"})

    # enabled の処理 (文字列をブール値に)
    is_enabled = row_data.get('enabled', 'true').lower() == 'true'

    # frequencyMin の処理 (文字列を整数に、デフォルト60)
    frequency_min = 60
    if row_data.get('frequencyMin'):
        try:
            frequency_min = int(row_data['frequencyMin'])
        except ValueError:
            print(f"Warning: Invalid frequencyMin '{row_data['frequencyMin']}' for {row_data.get('monitor_id')}. Using default 60.")
            frequency_min = 60
            
    monitor_name = row_data.get('monitor_name', 'Unnamed Monitor')
    monitor_url = row_data.get('target_url', 'https://www.dynatrace.com')
    script_type = row_data.get('script_type', 'availability')
    event_description = row_data.get('description', f"Navigate to {monitor_url}")


    content = {
      "anomalyDetection": {
        "loadingTimeThresholds": {"enabled": False, "thresholds": []},
        "outageHandling": {
          "globalOutage": True,
          "globalOutagePolicy": {"consecutiveRuns": 1},
          "localOutage": False,
          "localOutagePolicy": {"affectedLocations": None, "consecutiveRuns": None},
          "retryOnError": True
        }
      },
      "automaticallyAssignedApps": [],
      "enabled": is_enabled,
      "events": [], # 通常のブラウザモニターではここは空で、script.events を使う
      "frequencyMin": frequency_min,
      "keyPerformanceMetrics": {
        "loadActionKpm": "VISUALLY_COMPLETE",
        "xhrActionKpm": "VISUALLY_COMPLETE"
      },
      "locations": locations_list,
      "managementZones": [],
      "manuallyAssignedApps": [],
      "name": monitor_name, # Dynatrace上での表示名 (project.yamlのconfig.nameとは別に、APIペイロードにもnameが必要)
      "script": {
        "configuration": {
          "bandwidth": {"networkType": "WiFi"},
          "chromiumStartupFlags": {"disable-web-security": False},
          "device": {"deviceName": "Desktop", "orientation": "landscape"}
        },
        "events": [
          {
            "description": event_description,
            "type": "navigate", # 'navigate' 固定 (より複雑なスクリプトは別途対応が必要)
            "url": monitor_url,
            "wait": {"waitFor": "page_complete"}
          }
        ],
        "type": script_type, # 'clickpath' or 'availability'
        "version": "1.0"
      },
      "tags": tags_list,
      "type": "BROWSER"
    }
    return content

def create_project_yaml_content(monitor_id, monitor_name_from_csv):
    """project.yaml の内容を生成する"""
    content = f"""configs:
  - id: "{monitor_id}"
    config:
      name: "{monitor_name_from_csv}" # Dynatrace上での設定名にもなる
      template: "{TEMPLATE_FILE_NAME}"
      # parameters は使用しない
    type:
      api: "synthetic-monitor"
"""
    return content

def main():
    if not os.path.exists(CSV_FILE_PATH):
        print(f"Error: CSV file not found at {CSV_FILE_PATH}")
        return

    # ベース出力ディレクトリがなければ作成
    if not os.path.exists(OUTPUT_PROJECT_BASE_DIR):
        os.makedirs(OUTPUT_PROJECT_BASE_DIR)
        print(f"Created base directory: {OUTPUT_PROJECT_BASE_DIR}")

    try:
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8-sig') as csv_file: # encodingをutf-8-sigに変更 (BOM付き対応)
            csv_reader = csv.DictReader(csv_file)
            
            if not csv_reader.fieldnames:
                print(f"Error: CSV file {CSV_FILE_PATH} is empty or has no header row.")
                return

            generated_project_dirs = []

            for row in csv_reader:
                monitor_id = row.get('monitor_id')
                monitor_name_from_csv = row.get('monitor_name', 'Unnamed Monitor')

                if not monitor_id:
                    print(f"Warning: Skipping row due to missing 'monitor_id': {row}")
                    continue

                # 各モニターごとの出力ディレクトリを作成
                current_monitor_dir = os.path.join(OUTPUT_PROJECT_BASE_DIR, monitor_id)
                if not os.path.exists(current_monitor_dir):
                    os.makedirs(current_monitor_dir)
                
                generated_project_dirs.append(current_monitor_dir)

                # --- monitor.json の作成 ---
                monitor_json_data = create_monitor_json_content(row)
                monitor_json_path = os.path.join(current_monitor_dir, TEMPLATE_FILE_NAME)
                with open(monitor_json_path, mode='w', encoding='utf-8') as mj_file:
                    json.dump(monitor_json_data, mj_file, indent=2)
                print(f"  Created {monitor_json_path}")

                # --- project.yaml の作成 ---
                project_yaml_data = create_project_yaml_content(monitor_id, monitor_name_from_csv)
                project_yaml_path = os.path.join(current_monitor_dir, PROJECT_FILE_NAME)
                with open(project_yaml_path, mode='w', encoding='utf-8') as py_file:
                    py_file.write(project_yaml_data)
                print(f"  Created {project_yaml_path}")
            
            if generated_project_dirs:
                print(f"\nSuccessfully generated Monaco configurations for {len(generated_project_dirs)} monitor(s).")
                print("Generated project directories:")
                for proj_dir in generated_project_dirs:
                    print(f"  - {proj_dir}")
                print(f"\nNext steps:")
                print(f"1. Review the generated files in the '{OUTPUT_PROJECT_BASE_DIR}' directory.")
                print(f"2. Ensure your 'manifest.yaml' points to the '{OUTPUT_PROJECT_BASE_DIR}' directory as a project path, or lists each sub-directory.")
                print(f"   Example for 'manifest.yaml' (if pointing to base directory):")
                print(f"     projects:")
                print(f"       - name: synthetic-monitors # Can be any name")
                print(f"         path: {OUTPUT_PROJECT_BASE_DIR}")
                print(f"3. Run 'monaco deploy manifest.yaml --environment <your_env_name>'")

            else:
                print("No monitor configurations were generated. Check CSV content and format.")


    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    main() 