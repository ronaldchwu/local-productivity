# Task Tracker

A web-based productivity tool that helps you track your tasks and activities with AI-powered categorization. This tool automatically categorizes your tasks into projects and task types using Ollama's LLM capabilities.

## Features

- **AI-Powered Task Categorization**: Automatically categorizes tasks into projects and task types using Ollama's LLM
- **Real-time Task Logging**: Log tasks as you switch between them
- **Task Stop Tracking**: Mark when you stop working on a task
- **Statistics Dashboard**: View your productivity metrics and task distribution
- **Configurable Categories**: Customize project and task type categories through `config.yaml`
- **CSV Logging**: All tasks are logged to a CSV file for easy analysis

## Prerequisites

- Python 3.x
- Ollama installed and running locally (or accessible via network)
- Required Python packages (install via `pip install -r requirements.txt`):
  - Flask
  - PyYAML
  - requests
  - pandas

## Setup

1. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure Ollama settings in `config.yaml`:
   - Set the `ollama_api_url` if different from default
   - Choose your preferred `ollama_model`
   - Adjust `ollama_request_timeout` if needed

3. Customize your project and task type categories in `config.yaml`:
   - Add your projects under `project_categories`
   - Add your task types under `task_type_categories`
   - Each category should have a name and description

## Usage

1. Start the Flask application:
   ```bash
   python app.py
   ```

2. Open your web browser and navigate to `http://localhost:5000`

3. Use the web interface to:
   - Log new tasks with descriptions
   - Stop current tasks
   - View your task statistics
   - Clear recent task history if needed

## Data Storage

- Tasks are stored in `results/task_log.csv` with the following columns:
  - timestamp: When the task was logged
  - task_description: Your task description
  - project: AI-categorized project
  - task_type: AI-categorized task type

## Configuration

The `config.yaml` file allows you to customize:
- Ollama API settings
- Project categories and their descriptions
- Task type categories and their descriptions

## Contributing

Feel free to submit issues and enhancement requests! 