# Terminal Pomodoro Timer with Task Tracker

An interactive terminal-based pomodoro timer with integrated task management, priorities, and daily statistics.

## Features

- **Interactive Timer**: Live countdown display with visual progress bar
- **Meditation Bell Sounds**: Gentle chime when starting, soothing bell when completing
- **Task Management**: Add, edit, complete, and delete tasks
- **Priority System**: High, Medium, and Low priority levels
- **Estimated Pomodoros**: Track estimated vs completed pomodoros per task
- **Daily Statistics**: View today's productivity stats
- **Persistent Storage**: Tasks and stats saved to JSON files
- **Keyboard Shortcuts**: Quick navigation and control
- **Auto Sessions**: Automatic transitions between work and break periods
  - 25 min work sessions
  - 5 min short breaks
  - 15 min long breaks (every 4 pomodoros)

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Make the script executable (optional):
```bash
chmod +x pomodoro.py
```

## Usage

Run the application:
```bash
python pomodoro.py
```

Or if made executable:
```bash
./pomodoro.py
```

## Keyboard Shortcuts

### Timer Controls
- `s` - Start/pause the timer
- `k` - Skip to next session

### Task Management
- `a` - Add a new task
- `e` - Edit a task (prompts for ID)
- `c` - Complete a task (prompts for ID)
- `d` - Delete a task (prompts for ID)
- `1-9` - Set task 1-9 as active

### Other
- `?` - Toggle help screen
- `q` - Quit the application

## Workflow

1. **Add tasks**: Press `a` to add a task with title, priority, and estimated pomodoros
2. **Select active task**: Press `1-9` to set the corresponding task as active
3. **Start timer**: Press `s` to start a 25-minute work session
4. **Work**: Focus on your active task until the timer completes
5. **Break**: Timer automatically switches to break mode (5 or 15 minutes)
6. **Repeat**: Continue the cycle, tracking completed pomodoros per task

## Data Storage

All data is stored in `~/.pomodoro/`:
- `tasks.json` - Your tasks and active task state
- `stats.json` - Daily pomodoro statistics

## Sound System

The app plays **Glass.aiff meditation bell** sounds for all audio feedback:

- 🔔 **Start** (1 bell): When you start a new session
- 🔔🔔 **Pause/Resume** (2 bells): When you pause or resume
- 🔔🔔🔔 **Completion** (3 bells): When a session completes

All sounds use the same calming meditation bell (Glass.aiff) - only the number of bells changes!

### Platform Support:
- **macOS**: Uses Glass.aiff meditation bell (built-in)
- **Linux**: Uses system bell sounds if available
- **Windows/Fallback**: Uses terminal beep

Sounds play in the background and won't interrupt your flow. If system sounds aren't available, the app gracefully falls back to terminal beeps.

### Testing Sounds:
```bash
python3 test_all_sounds.py
```

This will play all three sound patterns so you can hear them.

## Requirements

- Python 3.7+
- rich library (for terminal UI)
- No additional audio libraries needed (uses system audio)

## Tips

- Complete pomodoros are automatically tracked for your active task
- Tasks show progress as completed/estimated pomodoros
- Daily stats reset each day
- Use priorities to organize your task list
- The timer will beep when a session completes
