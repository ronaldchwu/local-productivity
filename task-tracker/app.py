import csv
import datetime
import json
import os
import yaml # requires PyYAML
import requests # requires requests
import pandas as pd # requires pandas
from flask import Flask, jsonify, render_template, request # requires Flask

# --- Configuration ---
CONFIG_FILE = 'config.yaml'
CSV_FILE = 'results/task_log.csv'
STOP_MARKER_PROJECT = "--STOPPED--"
STOP_MARKER_TYPE = "--STOPPED--"

# --- Configuration Loading ---
def load_config():
    """Loads configuration from the YAML file."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = yaml.safe_load(f)
            if not config_data: # Handle empty config file
                print(f"WARN: Configuration file '{CONFIG_FILE}' is empty.")
                return {} # Return empty dict, defaults will be used later
            return config_data
    except FileNotFoundError:
        print(f"ERROR: Configuration file '{CONFIG_FILE}' not found. Using defaults.")
        return {} # Return empty dict, defaults will be used later
    except yaml.YAMLError as e:
        print(f"ERROR: Could not parse configuration file '{CONFIG_FILE}': {e}")
        return None # Indicate critical error

config = load_config()
if config is None:
    exit("Exiting due to fatal configuration error.")

# Use get with defaults for crucial Ollama settings
OLLAMA_API_URL = config.get('ollama_api_url', 'http://localhost:11434/api/generate')
OLLAMA_MODEL = config.get('ollama_model', 'llama3:latest')
OLLAMA_TIMEOUT = config.get('ollama_request_timeout', 60)
PROJECT_CATEGORIES = config.get('project_categories', [{'name': 'Default Project', 'description': 'Default'}])
TASK_TYPE_CATEGORIES = config.get('task_type_categories', [{'name': 'Default Task', 'description': 'Default'}])


app = Flask(__name__, template_folder='templates', static_folder='static')

# --- Ollama Categorization (Using Descriptions) ---
def categorize_task_with_ollama(description):
    """Uses Ollama to categorize the task description using category descriptions."""
    if not OLLAMA_API_URL:
        print("WARN: Ollama API URL not configured. Skipping categorization.")
        return "Un-categorized", "Un-categorized"

    project_details_list = []
    valid_project_names = set()
    for cat in PROJECT_CATEGORIES:
        if isinstance(cat, dict) and 'name' in cat and 'description' in cat:
            project_details_list.append(f"* Name: {cat['name']}\n  Description: {cat['description']}")
            valid_project_names.add(cat['name'])
        else:
             print(f"WARN: Invalid format for project category item: {cat}. Skipping.")

    type_details_list = []
    valid_type_names = set()
    for cat in TASK_TYPE_CATEGORIES:
        if isinstance(cat, dict) and 'name' in cat and 'description' in cat:
            type_details_list.append(f"* Name: {cat['name']}\n  Description: {cat['description']}")
            valid_type_names.add(cat['name'])
        else:
            print(f"WARN: Invalid format for task type category item: {cat}. Skipping.")

    valid_project_names.add("Un-categorized")
    valid_type_names.add("Un-categorized")

    project_prompt_list = "\n".join(project_details_list)
    type_prompt_list = "\n".join(type_details_list)

    prompt = f"""
Analyze the following task description entered by a user:
'{description}'

Your goal is to classify this task into the single most appropriate project category and the single most appropriate task type category based *only* on the definitions provided below.
Carefully consider the meaning and keywords in the user's description and match them against the category names AND their detailed descriptions to find the best fit.

Available Project Categories:
{project_prompt_list}

Available Task Type Categories:
{type_prompt_list}

Instructions:
1. Choose exactly one project category name from the available project names listed above.
2. Choose exactly one task type category name from the available task type names listed above.
3. If the user's description does not clearly fit any of the specific categories defined (considering both name and description), choose "Un-categorized" for that specific category (project or task type or both).
4. Respond *only* with a valid JSON object containing the chosen project name and task type name. Do not add any explanation or introductory text. The JSON object should look exactly like this:
{{"project": "Chosen Project Name", "task_type": "Chosen Task Type Name"}}
"""

    headers = {'Content-Type': 'application/json'}
    data = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }

    try:
        response = requests.post(
            OLLAMA_API_URL,
            headers=headers,
            json=data,
            timeout=OLLAMA_TIMEOUT
        )
        response.raise_for_status()

        response_data = response.json()
        json_response_str = response_data.get('response', '{}')

        try:
            parsed_categories = json.loads(json_response_str)
            project = parsed_categories.get("project", "Un-categorized")
            task_type = parsed_categories.get("task_type", "Un-categorized")

            if project not in valid_project_names:
                print(f"WARN: Ollama returned unknown project '{project}'. Defaulting to Un-categorized.")
                project = "Un-categorized"
            if task_type not in valid_type_names:
                print(f"WARN: Ollama returned unknown task type '{task_type}'. Defaulting to Un-categorized.")
                task_type = "Un-categorized"

            return project, task_type

        except json.JSONDecodeError:
            print(f"ERROR: Could not parse JSON response string from Ollama: {json_response_str}")
            return "Un-categorized", "Un-categorized"

    except requests.exceptions.Timeout:
         print(f"ERROR: Timeout connecting to Ollama API at {OLLAMA_API_URL}")
         return "Un-categorized", "Un-categorized"
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not connect to Ollama API at {OLLAMA_API_URL}: {e}")
        return "Un-categorized", "Un-categorized"
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during Ollama interaction: {e}")
        return "Un-categorized", "Un-categorized"


# --- CSV Handling ---
def ensure_csv_exists():
    """Creates the CSV with header if it doesn't exist."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'task_description', 'project', 'task_type'])

def append_to_csv(data_row):
    """Appends a row to the CSV file."""
    ensure_csv_exists()
    # Use utf-8 encoding for broader compatibility
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(data_row)

# --- Flask Routes ---
@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/log_task', methods=['POST'])
def log_task():
    """Logs a new task switch event."""
    try:
        data = request.get_json()
        description = data.get('description')
        if not description:
            return jsonify({"status": "error", "message": "No description provided"}), 400

        timestamp = datetime.datetime.now().isoformat()

        print(f"Categorizing '{description}' using Ollama...")
        project, task_type = categorize_task_with_ollama(description)
        print(f"Categorized as: Project='{project}', Type='{task_type}'")

        append_to_csv([timestamp, description, project, task_type])

        return jsonify({"status": "success", "message": "Task logged"})
    except Exception as e:
        print(f"ERROR in /log_task: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Internal server error"}), 500

@app.route('/stop_task', methods=['POST'])
def stop_task():
    """Logs a special marker to indicate the end of the last task."""
    try:
        last_line = None
        if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0: # Check size > 0
            try:
                 with open(CSV_FILE, 'rb') as f:
                    # Find the last newline character (handle edge cases)
                    f.seek(0, os.SEEK_END)
                    if f.tell() <= 1: # Empty or single character file
                        pass # Cannot read last line
                    else:
                        f.seek(-2, os.SEEK_END) # Go before potential trailing newline
                        while f.read(1) != b'\n' and f.tell() > 1:
                            f.seek(-2, os.SEEK_CUR)
                        if f.tell() == 1: # Reached beginning without finding newline
                            f.seek(0)
                        last_line_bytes = f.readline() # Read the actual last line

                 try:
                    last_line = last_line_bytes.decode('utf-8').strip()
                 except UnicodeDecodeError:
                     print("WARN: Could not decode last line of CSV.")
                     last_line = None

                 if last_line:
                    # Use csv reader for robust parsing of the line
                    try:
                        last_entry = next(csv.reader([last_line]))
                        if len(last_entry) > 2 and last_entry[2] == STOP_MARKER_PROJECT:
                            return jsonify({"status": "success", "message": "Task already stopped."})
                    except csv.Error as csv_e:
                        print(f"WARN: Could not parse last CSV line '{last_line}': {csv_e}")


            except FileNotFoundError:
                 pass # Should not happen if os.path.exists passed
            except Exception as e:
                print(f"WARN: Could not read last line to check if stopped: {e}")

        timestamp = datetime.datetime.now().isoformat()
        description = "Task Stopped"
        append_to_csv([timestamp, description, STOP_MARKER_PROJECT, STOP_MARKER_TYPE])

        return jsonify({"status": "success", "message": "Stop marker logged."})

    except Exception as e:
        print(f"ERROR in /stop_task endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@app.route('/clear_recent', methods=['POST'])
def clear_recent():
    """Deletes log entries within the specified number of past minutes."""
    try:
        data = request.get_json()
        minutes_to_clear = data.get('minutes')

        if not isinstance(minutes_to_clear, int) or minutes_to_clear <= 0:
            return jsonify({"status": "error", "message": "Invalid number of minutes."}), 400

        if not os.path.exists(CSV_FILE):
            return jsonify({"status": "success", "message": "Log file doesn't exist.", "cleared_count": 0})

        try:
            # Read CSV, ensuring correct header detection even if empty after header
            df = pd.read_csv(CSV_FILE)
            if df.empty:
                 return jsonify({"status": "success", "message": "Log file is empty.", "cleared_count": 0})

            try:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            except Exception as e:
                 print(f"Error converting timestamp column: {e}")
                 return jsonify({"status": "error", "message": "Error processing timestamp data."}), 500

            # Use timezone-naive comparison unless timestamps have timezone info
            cutoff_time = pd.Timestamp.now() - pd.Timedelta(minutes=minutes_to_clear)
            if df['timestamp'].dt.tz is not None:
                 cutoff_time = pd.Timestamp.now(tz=df['timestamp'].dt.tz) - pd.Timedelta(minutes=minutes_to_clear)

            original_count = len(df)
            df_filtered = df[df['timestamp'] < cutoff_time].copy()
            cleared_count = original_count - len(df_filtered)

            # Overwrite using utf-8 encoding
            df_filtered.to_csv(CSV_FILE, index=False, encoding='utf-8')

            return jsonify({"status": "success", "message": f"Cleared entries from the last {minutes_to_clear} minutes.", "cleared_count": cleared_count})

        except pd.errors.EmptyDataError:
            return jsonify({"status": "success", "message": "Log file is effectively empty.", "cleared_count": 0})
        except Exception as e:
            print(f"ERROR during clear operation: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": f"Failed to process or write log file: {e}"}), 500

    except Exception as e:
        print(f"ERROR in /clear_recent endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@app.route('/get_stats')
def get_stats():
    """Calculates and returns time tracking statistics."""
    time_range = request.args.get('range', 'today')

    try:
        if not os.path.exists(CSV_FILE):
             return jsonify({"projects": {}, "types": {}, "current_task": None, "tasks": [], "error": "No data yet."})

        try:
            df = pd.read_csv(CSV_FILE)
            if df.empty:
                return jsonify({"projects": {}, "types": {}, "current_task": None, "tasks": [], "error": "No data yet."})
        except pd.errors.EmptyDataError:
             return jsonify({"projects": {}, "types": {}, "current_task": None, "tasks": [], "error": "Log file is empty or header-only."})

        try:
             df['timestamp'] = pd.to_datetime(df['timestamp'])
             df = df.sort_values(by='timestamp').reset_index(drop=True)
        except Exception as e:
            print(f"Error processing timestamp column in get_stats: {e}")
            return jsonify({"projects": {}, "types": {}, "current_task": None, "tasks": [], "error": "Error processing timestamp data."}), 500

        df['end_time'] = df['timestamp'].shift(-1)
        tz_info = df['timestamp'].dt.tz
        now = pd.Timestamp.now(tz=tz_info) if tz_info else pd.Timestamp.now()
        df['end_time'].fillna(now, inplace=True)
        df['duration_seconds'] = (df['end_time'] - df['timestamp']).dt.total_seconds()
        df['duration_seconds'] = df['duration_seconds'].clip(lower=0)

        current_task_info = None
        if not df.empty:
            last_entry_overall = df.iloc[-1]
            if last_entry_overall['project'] != STOP_MARKER_PROJECT:
                current_task_info = {
                    "description": last_entry_overall['task_description'],
                    "project": last_entry_overall['project'],
                    "type": last_entry_overall['task_type'],
                    "start_time": last_entry_overall['timestamp'].isoformat(),
                }

        today_local = datetime.date.today()
        df['date'] = df['timestamp'].dt.date

        if time_range == 'today':
            df_range_filtered = df[df['date'] == today_local].copy()
        elif time_range == 'week':
            start_of_week = today_local - datetime.timedelta(days=today_local.weekday())
            df_range_filtered = df[df['date'] >= start_of_week].copy()
        else: # 'all'
            df_range_filtered = df.copy()

        # Filter out STOP markers before aggregation
        df_agg_filtered = df_range_filtered[df_range_filtered['project'] != STOP_MARKER_PROJECT].copy()

        # Determine final current task based on range
        final_current_task = None
        if current_task_info:
            task_start_date = pd.to_datetime(current_task_info['start_time']).date()
            if time_range == 'all':
                final_current_task = current_task_info
            elif time_range == 'week':
                 start_of_week = today_local - datetime.timedelta(days=today_local.weekday())
                 if task_start_date >= start_of_week:
                     final_current_task = current_task_info
            elif time_range == 'today':
                if task_start_date == today_local:
                    final_current_task = current_task_info

        if df_agg_filtered.empty:
            return jsonify({
                "projects": {},
                "types": {},
                "current_task": final_current_task,
                "tasks": [],
                "message": f"No completed task data to aggregate for range '{time_range}'."
            })

        project_stats = df_agg_filtered.groupby('project')['duration_seconds'].sum() / 60
        type_stats = df_agg_filtered.groupby('task_type')['duration_seconds'].sum() / 60

        # Convert task entries to list of dictionaries
        tasks = df_agg_filtered.to_dict('records')
        for task in tasks:
            task['timestamp'] = task['timestamp'].isoformat()

        return jsonify({
            "projects": project_stats.round(2).to_dict(),
            "types": type_stats.round(2).to_dict(),
            "current_task": final_current_task,
            "tasks": tasks
        })

    except FileNotFoundError:
         return jsonify({"projects": {}, "types": {}, "current_task": None, "tasks": [], "error": "CSV file not found."})
    except Exception as e:
        print(f"ERROR in /get_stats: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Internal server error calculating stats: {e}"}), 500

@app.route('/update_task_categories', methods=['POST'])
def update_task_categories():
    """Updates the project and task type categories for a specific task entry."""
    try:
        data = request.get_json()
        timestamp = data.get('timestamp')
        project = data.get('project')
        task_type = data.get('task_type')

        if not all([timestamp, project, task_type]):
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        if not os.path.exists(CSV_FILE):
            return jsonify({"status": "error", "message": "No task log found"}), 404

        # Read the CSV file
        df = pd.read_csv(CSV_FILE)
        
        # Find the row with matching timestamp
        mask = df['timestamp'] == timestamp
        if not mask.any():
            return jsonify({"status": "error", "message": "Task entry not found"}), 404

        # Update the categories
        df.loc[mask, 'project'] = project
        df.loc[mask, 'task_type'] = task_type

        # Save back to CSV
        df.to_csv(CSV_FILE, index=False)

        return jsonify({"status": "success", "message": "Categories updated successfully"})

    except Exception as e:
        print(f"ERROR in /update_task_categories: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Internal server error"}), 500

@app.route('/get_categories')
def get_categories():
    """Returns the available project and task type categories."""
    try:
        return jsonify({
            "project_categories": PROJECT_CATEGORIES,
            "task_type_categories": TASK_TYPE_CATEGORIES
        })
    except Exception as e:
        print(f"ERROR in /get_categories: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Internal server error"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    ensure_csv_exists()
    # Set debug=False for production/stable use
    # Use host='0.0.0.0' to access from other devices on your network
    app.run(debug=True, port=5001, host='127.0.0.1')