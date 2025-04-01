document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const taskInput = document.getElementById('taskInput');
    const logButton = document.getElementById('logButton');
    const stopTaskButton = document.getElementById('stopTaskButton');
    const statusBar = document.getElementById('statusBar');
    const currentTaskDiv = document.getElementById('currentTask');
    const rangeButtons = document.querySelectorAll('.time-range-selector button');
    const clearMinutesInput = document.getElementById('clearMinutesInput');
    const clearRecentButton = document.getElementById('clearRecentButton');
    const projectChartCanvas = document.getElementById('projectChart');
    const typeChartCanvas = document.getElementById('typeChart');
    const taskList = document.getElementById('taskList');
    const editModal = document.getElementById('editModal');
    const closeModal = document.querySelector('.close');
    const saveEditButton = document.getElementById('saveEdit');
    const editProject = document.getElementById('editProject');
    const editTaskType = document.getElementById('editTaskType');
    const editTaskInfo = document.getElementById('editTaskInfo');
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    // --- State Variables ---
    let projectChart = null;
    let typeChart = null;
    let currentRange = 'today'; // Default range
    let currentEditTask = null;
    let categories = null;

    // --- Utility to disable/enable all action buttons ---
    const setButtonsDisabled = (disabled) => {
        logButton.disabled = disabled;
        stopTaskButton.disabled = disabled;
        clearRecentButton.disabled = disabled;
        // Optionally disable range buttons during operations?
        // rangeButtons.forEach(button => button.disabled = disabled);
    };

    // --- Chart Initialization ---
    function initChart(canvas, chartType = 'bar') {
        if (!canvas) {
            console.error("Canvas element not found for chart");
            return null;
        }
        const ctx = canvas.getContext('2d');
        return new Chart(ctx, {
            type: chartType,
            data: {
                labels: [],
                datasets: [{
                    label: 'Minutes Spent',
                    data: [],
                    backgroundColor: 'rgba(54, 162, 235, 0.6)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y', // Horizontal bar chart
                scales: {
                    x: { 
                        beginAtZero: true, 
                        title: { display: true, text: 'Minutes' },
                        ticks: {
                            maxRotation: 0,
                            autoSkip: true
                        }
                    },
                    y: { 
                        ticks: { 
                            autoSkip: false,
                            maxRotation: 0
                        }
                    }
                },
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }, // Hide legend for single dataset
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.parsed.x.toFixed(1)} minutes`;
                            }
                        }
                    }
                }
            }
        });
    }

    // --- Update Chart Data ---
    function updateChart(chart, newData) {
        if (!chart || !newData) return;
        chart.data.labels = Object.keys(newData);
        chart.data.datasets[0].data = Object.values(newData);
        chart.update();
    }

     // --- Update Current Task Display ---
     function updateCurrentTask(taskInfo) {
        if (taskInfo && taskInfo.project !== '--STOPPED--') { // Check if it's valid task info
            try {
                // Attempt to parse the ISO string date
                const startTime = new Date(taskInfo.start_time);
                // Check if the date is valid before using toLocaleTimeString
                if (!isNaN(startTime.getTime())) {
                     currentTaskDiv.textContent = `Currently working on: "${taskInfo.description}" (Project: ${taskInfo.project}, Type: ${taskInfo.type}) since ${startTime.toLocaleTimeString()}`;
                } else {
                     console.error("Invalid start_time format received:", taskInfo.start_time);
                     currentTaskDiv.textContent = `Currently working on: "${taskInfo.description}" (Project: ${taskInfo.project}, Type: ${taskInfo.type}) - Invalid start time.`;
                }
            } catch(e) {
                console.error("Error processing start_time:", e);
                 currentTaskDiv.textContent = `Currently working on: "${taskInfo.description}" (Project: ${taskInfo.project}, Type: ${taskInfo.type}) - Error displaying start time.`;
            }
        } else {
            currentTaskDiv.textContent = 'No task active.'; // Covers null or STOPPED task
        }
    }

    // --- Tab Functions ---
    function showTab(tabId) {
        tabContents.forEach(content => {
            content.style.display = content.id === tabId ? 'block' : 'none';
        });
        tabButtons.forEach(button => {
            button.classList.toggle('active', button.getAttribute('data-tab') === tabId);
        });
    }

    // --- Category Loading ---
    async function loadCategories() {
        try {
            const response = await fetch('/get_categories');
            if (!response.ok) throw new Error('Failed to fetch categories');
            
            categories = await response.json();
            
            // Populate project dropdown
            editProject.innerHTML = categories.project_categories
                .map(cat => `<option value="${cat.name}">${cat.name}</option>`)
                .join('');
            
            // Populate task type dropdown
            editTaskType.innerHTML = categories.task_type_categories
                .map(cat => `<option value="${cat.name}">${cat.name}</option>`)
                .join('');
        } catch (error) {
            console.error('Error loading categories:', error);
            statusBar.textContent = `Error loading categories: ${error.message}`;
        }
    }

    // --- Modal Functions ---
    function showModal() {
        editModal.style.display = 'block';
    }

    function hideModal() {
        editModal.style.display = 'none';
        currentEditTask = null;
    }

    // --- Task List Functions ---
    function formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString();
    }

    function createTaskEntry(task) {
        const entry = document.createElement('div');
        entry.className = 'task-entry';
        entry.innerHTML = `
            <div>
                <strong>${task.task_description}</strong><br>
                <small>${formatDate(task.timestamp)}</small><br>
                <small>Project: ${task.project} | Type: ${task.task_type}</small>
            </div>
            <button class="edit-button">Edit</button>
        `;

        entry.querySelector('.edit-button').addEventListener('click', () => {
            currentEditTask = task;
            editTaskInfo.innerHTML = `
                <p><strong>Task:</strong> ${task.task_description}</p>
                <p><strong>Time:</strong> ${formatDate(task.timestamp)}</p>
            `;
            
            // Populate dropdowns with current values
            editProject.value = task.project;
            editTaskType.value = task.task_type;
            
            showModal();
        });

        return entry;
    }

    async function updateTaskList() {
        try {
            const response = await fetch(`/get_stats?range=${currentRange}`);
            if (!response.ok) throw new Error('Failed to fetch task list');
            
            const stats = await response.json();
            if (stats.error) {
                taskList.innerHTML = `<p>Error: ${stats.error}</p>`;
                return;
            }

            // Clear existing entries
            taskList.innerHTML = '';
            
            // Add entries for each task
            if (stats.tasks) {
                stats.tasks.forEach(task => {
                    if (task.project !== '--STOPPED--') {
                        taskList.appendChild(createTaskEntry(task));
                    }
                });
            }
        } catch (error) {
            console.error('Error updating task list:', error);
            taskList.innerHTML = `<p>Error loading tasks: ${error.message}</p>`;
        }
    }

    // --- Edit Task Categories ---
    async function saveTaskCategories() {
        if (!currentEditTask) return;

        const newProject = editProject.value;
        const newTaskType = editTaskType.value;

        try {
            const response = await fetch('/update_task_categories', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    timestamp: currentEditTask.timestamp,
                    project: newProject,
                    task_type: newTaskType
                })
            });

            const result = await response.json();
            
            if (response.ok && result.status === 'success') {
                statusBar.textContent = 'Categories updated successfully';
                hideModal();
                fetchAndUpdateStats(currentRange);
                updateTaskList();
            } else {
                throw new Error(result.message || 'Failed to update categories');
            }
        } catch (error) {
            console.error('Error updating categories:', error);
            statusBar.textContent = `Error updating categories: ${error.message}`;
        }
    }

    // --- Fetch Stats from Backend ---
    async function fetchAndUpdateStats(range = 'today') {
        statusBar.textContent = `Fetching stats for ${range}...`;
        setButtonsDisabled(true);
        currentRange = range;

        rangeButtons.forEach(button => {
            button.style.fontWeight = button.getAttribute('data-range') === range ? 'bold' : 'normal';
        });

        try {
            const response = await fetch(`/get_stats?range=${range}`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
                throw new Error(`HTTP error ${response.status}: ${errorData.message || 'Failed to fetch stats'}`);
            }
            const stats = await response.json();

            if (stats.error) {
                statusBar.textContent = `Error fetching stats: ${stats.error}`;
                updateChart(projectChart, {});
                updateChart(typeChart, {});
                updateCurrentTask(null);
            } else {
                updateChart(projectChart, stats.projects || {});
                updateChart(typeChart, stats.types || {});
                updateCurrentTask(stats.current_task);
                statusBar.textContent = stats.message || `Stats updated for ${range}.`;
                updateTaskList();
            }

        } catch (error) {
            console.error('Error fetching stats:', error);
            statusBar.textContent = `Error fetching stats: ${error.message}`;
            updateChart(projectChart, {});
            updateChart(typeChart, {});
            updateCurrentTask(null);
        } finally {
            setButtonsDisabled(false);
        }
    }

    // --- Log New Task ---
    async function logTask() {
        const description = taskInput.value.trim();
        if (!description) {
            statusBar.textContent = 'Please enter a task description.';
            return;
        }

        setButtonsDisabled(true);
        statusBar.textContent = 'Logging task and categorizing (this may take a moment)...';

        try {
            const response = await fetch('/log_task', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ description: description }),
            });

            const result = await response.json();

            if (response.ok && result.status === 'success') {
                statusBar.textContent = 'Task logged successfully!';
                taskInput.value = ''; // Clear input
                fetchAndUpdateStats(currentRange); // Refresh stats for the current view
            } else {
                throw new Error(result.message || 'Failed to log task');
            }
        } catch (error) {
            console.error('Error logging task:', error);
            statusBar.textContent = `Error logging task: ${error.message}. Is the backend server running?`;
        } finally {
            setButtonsDisabled(false);
        }
    }

     // --- Stop Current Task ---
     async function stopTask() {
        if (!confirm("Are you sure you want to stop timing the current task?")) {
            return;
        }
        setButtonsDisabled(true);
        statusBar.textContent = 'Stopping current task...';

        try {
            const response = await fetch('/stop_task', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();

            if (response.ok && result.status === 'success') {
                statusBar.textContent = result.message || 'Task stopped.';
                currentTaskDiv.textContent = 'No task active.'; // Explicitly update UI
                fetchAndUpdateStats(currentRange);
            } else {
                 throw new Error(result.message || 'Failed to stop task');
            }
        } catch (error) {
            console.error('Error stopping task:', error);
            statusBar.textContent = `Error stopping task: ${error.message}.`;
        } finally {
            setButtonsDisabled(false);
        }
    }

     // --- Clear Recent Logs ---
     async function clearRecentLogs() {
        const minutes = parseInt(clearMinutesInput.value, 10);
        if (isNaN(minutes) || minutes <= 0) {
            statusBar.textContent = 'Please enter a valid number of minutes (greater than 0).';
            return;
        }
        if (!confirm(`Are you sure you want to delete all log entries from the last ${minutes} minute(s)? This cannot be undone.`)) {
            return;
        }
        setButtonsDisabled(true);
        statusBar.textContent = `Clearing entries from the last ${minutes} minutes...`;

        try {
            const response = await fetch('/clear_recent', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ minutes: minutes }),
            });
            const result = await response.json();

            if (response.ok && result.status === 'success') {
                statusBar.textContent = `Successfully cleared ${result.cleared_count} entries.`;
                clearMinutesInput.value = '';
                fetchAndUpdateStats(currentRange);
            } else {
                 throw new Error(result.message || 'Failed to clear logs');
            }
        } catch (error) {
            console.error('Error clearing logs:', error);
            statusBar.textContent = `Error clearing logs: ${error.message}.`;
        } finally {
            setButtonsDisabled(false);
        }
    }

    // --- Event Listeners ---
    logButton.addEventListener('click', logTask);
    stopTaskButton.addEventListener('click', stopTask);
    clearRecentButton.addEventListener('click', clearRecentLogs);

    taskInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            logTask();
        }
    });

    rangeButtons.forEach(button => {
        button.addEventListener('click', () => {
            fetchAndUpdateStats(button.getAttribute('data-range'));
        });
    });

    closeModal.addEventListener('click', hideModal);
    saveEditButton.addEventListener('click', saveTaskCategories);
    window.addEventListener('click', (event) => {
        if (event.target === editModal) {
            hideModal();
        }
    });

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            showTab(button.getAttribute('data-tab'));
        });
    });

    // --- Initial Load ---
    projectChart = initChart(projectChartCanvas);
    typeChart = initChart(typeChartCanvas);

    if (projectChart && typeChart) {
        loadCategories().then(() => {
            fetchAndUpdateStats(currentRange);
            showTab('overview'); // Show overview tab by default
        });
    } else {
        statusBar.textContent = "Error initializing charts. Please check the console.";
        console.error("Failed to initialize one or both charts.");
    }
});