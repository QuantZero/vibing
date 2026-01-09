#!/usr/bin/env python3
"""
Terminal Pomodoro Timer with Task Tracker
Features: Interactive timer, task management, priorities, daily stats
"""

import json
import os
import sys
import time
import math
import subprocess
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# Data file paths
DATA_DIR = Path.home() / ".pomodoro"
TASKS_FILE = DATA_DIR / "tasks.json"
STATS_FILE = DATA_DIR / "stats.json"

# Pomodoro settings
WORK_MINUTES = 25
SHORT_BREAK_MINUTES = 5
LONG_BREAK_MINUTES = 15
POMODOROS_UNTIL_LONG_BREAK = 4


class SoundPlayer:
    """Plays meditation bell sounds using system audio"""

    @staticmethod
    def play_bell(bell_type="completion"):
        """Play meditation bell sound in background thread"""
        def _play():
            try:
                if sys.platform == "darwin":  # macOS
                    # All sounds use Glass.aiff meditation bell
                    bell_sound = "/System/Library/Sounds/Glass.aiff"

                    if bell_type == "start":
                        # Single bell for start
                        subprocess.run(["afplay", bell_sound],
                                     check=False, timeout=2)
                    elif bell_type == "pause":
                        # Two bells for pause/resume
                        subprocess.run(["afplay", bell_sound],
                                     check=False, timeout=2)
                        time.sleep(0.2)
                        subprocess.run(["afplay", bell_sound],
                                     check=False, timeout=2)
                    elif bell_type == "completion":
                        # Three bells for completion
                        for i in range(3):
                            subprocess.run(["afplay", bell_sound],
                                         check=False, timeout=2)
                            if i < 2:  # Don't sleep after last bell
                                time.sleep(0.3)

                elif sys.platform.startswith("linux"):
                    # Use paplay on Linux
                    bell_sound = "/usr/share/sounds/freedesktop/stereo/bell.oga"
                    bell_count = {"start": 1, "pause": 2, "completion": 3}
                    count = bell_count.get(bell_type, 3)

                    for i in range(count):
                        subprocess.run(["paplay", bell_sound],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL,
                                     check=False, timeout=2)
                        if i < count - 1:
                            time.sleep(0.3)
                else:
                    # Windows or unknown - use terminal bell
                    bell_count = {"start": 1, "pause": 2, "completion": 3}
                    count = bell_count.get(bell_type, 3)
                    for i in range(count):
                        print('\a', flush=True)
                        if i < count - 1:
                            time.sleep(0.3)
            except Exception as e:
                # Fallback to terminal bell
                bell_count = {"start": 1, "pause": 2, "completion": 3}
                count = bell_count.get(bell_type, 3)
                for i in range(count):
                    print('\a', flush=True)
                    if i < count - 1:
                        time.sleep(0.2)

        # Play sound in background thread so it doesn't block the UI
        thread = threading.Thread(target=_play, daemon=True)
        thread.start()

    @staticmethod
    def play_start_sound():
        """Play single bell when starting a session"""
        SoundPlayer.play_bell("start")

    @staticmethod
    def play_pause_sound():
        """Play two bells when pausing/resuming"""
        SoundPlayer.play_bell("pause")

    @staticmethod
    def play_completion_sound():
        """Play three bells when completing a session"""
        SoundPlayer.play_bell("completion")


class Priority(Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class TimerState(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


class SessionType(Enum):
    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


@dataclass
class Task:
    id: int
    title: str
    priority: str
    estimated_pomodoros: int
    completed_pomodoros: int = 0
    completed: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class PomodoroTimer:
    """Core timer logic"""

    def __init__(self):
        self.state = TimerState.STOPPED
        self.session_type = SessionType.WORK
        self.remaining_seconds = WORK_MINUTES * 60
        self.total_seconds = WORK_MINUTES * 60
        self.pomodoros_completed = 0
        self.start_time = None
        self.paused_time = 0

    def start(self):
        if self.state == TimerState.STOPPED:
            self.start_time = time.time()
            # Play start sound when beginning a new session (1 bell)
            SoundPlayer.play_start_sound()
        elif self.state == TimerState.PAUSED:
            # Resume from pause - play pause sound (2 bells)
            pause_duration = time.time() - self.paused_time
            self.start_time += pause_duration
            SoundPlayer.play_pause_sound()
        self.state = TimerState.RUNNING

    def pause(self):
        if self.state == TimerState.RUNNING:
            self.state = TimerState.PAUSED
            self.paused_time = time.time()
            # Play pause sound (2 bells)
            SoundPlayer.play_pause_sound()

    def stop(self):
        self.state = TimerState.STOPPED
        self.remaining_seconds = self.total_seconds

    def skip(self):
        """Skip to next session"""
        if self.state == TimerState.RUNNING:
            # Force completion by setting elapsed time to total
            self.start_time = time.time() - self.total_seconds
            self.remaining_seconds = 0
        else:
            # If not running, just complete the session
            self.complete_session()

    def update(self):
        """Update timer state, returns True if session completed"""
        if self.state != TimerState.RUNNING:
            return False

        elapsed = time.time() - self.start_time
        self.remaining_seconds = max(0, self.total_seconds - int(elapsed))

        if self.remaining_seconds == 0:
            self.complete_session()
            return True
        return False

    def complete_session(self):
        """Handle session completion and transition to next session"""
        if self.session_type == SessionType.WORK:
            self.pomodoros_completed += 1
            # Determine next break type
            if self.pomodoros_completed % POMODOROS_UNTIL_LONG_BREAK == 0:
                self.start_break(SessionType.LONG_BREAK)
            else:
                self.start_break(SessionType.SHORT_BREAK)
        else:
            # Break finished, start work session
            self.start_work()

    def start_work(self):
        """Start a work session"""
        self.session_type = SessionType.WORK
        self.total_seconds = WORK_MINUTES * 60
        self.remaining_seconds = self.total_seconds
        self.state = TimerState.STOPPED

    def start_break(self, break_type: SessionType):
        """Start a break session"""
        self.session_type = break_type
        if break_type == SessionType.LONG_BREAK:
            self.total_seconds = LONG_BREAK_MINUTES * 60
        else:
            self.total_seconds = SHORT_BREAK_MINUTES * 60
        self.remaining_seconds = self.total_seconds
        self.state = TimerState.STOPPED

    def get_time_display(self) -> str:
        """Format remaining time as MM:SS"""
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def get_progress(self) -> float:
        """Get progress as percentage (0-1)"""
        if self.total_seconds == 0:
            return 1.0
        return 1 - (self.remaining_seconds / self.total_seconds)


class TaskManager:
    """Manages tasks with persistence"""

    def __init__(self):
        self.tasks: List[Task] = []
        self.next_id = 1
        self.active_task_id: Optional[int] = None
        self.load_tasks()

    def add_task(self, title: str, priority: str, estimated_pomodoros: int) -> Task:
        task = Task(
            id=self.next_id,
            title=title,
            priority=priority,
            estimated_pomodoros=estimated_pomodoros
        )
        self.tasks.append(task)
        self.next_id += 1
        self.save_tasks()
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def get_active_task(self) -> Optional[Task]:
        if self.active_task_id:
            return self.get_task(self.active_task_id)
        return None

    def set_active_task(self, task_id: Optional[int]):
        self.active_task_id = task_id
        self.save_tasks()

    def complete_task(self, task_id: int):
        task = self.get_task(task_id)
        if task:
            task.completed = True
            self.save_tasks()

    def delete_task(self, task_id: int):
        self.tasks = [t for t in self.tasks if t.id != task_id]
        if self.active_task_id == task_id:
            self.active_task_id = None
        self.save_tasks()

    def edit_task(self, task_id: int, title: Optional[str] = None,
                  priority: Optional[str] = None, estimated: Optional[int] = None):
        task = self.get_task(task_id)
        if task:
            if title is not None:
                task.title = title
            if priority is not None:
                task.priority = priority
            if estimated is not None:
                task.estimated_pomodoros = estimated
            self.save_tasks()

    def increment_task_pomodoro(self, task_id: int):
        task = self.get_task(task_id)
        if task:
            task.completed_pomodoros += 1
            self.save_tasks()

    def get_incomplete_tasks(self, sort_by_priority: bool = False) -> List[Task]:
        tasks = [t for t in self.tasks if not t.completed]
        if sort_by_priority:
            priority_order = {"High": 0, "Medium": 1, "Low": 2}
            tasks.sort(key=lambda t: priority_order.get(t.priority, 3))
        return tasks

    def save_tasks(self):
        DATA_DIR.mkdir(exist_ok=True)
        data = {
            "next_id": self.next_id,
            "active_task_id": self.active_task_id,
            "tasks": [asdict(task) for task in self.tasks]
        }
        with open(TASKS_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def load_tasks(self):
        if not TASKS_FILE.exists():
            return
        try:
            with open(TASKS_FILE, 'r') as f:
                data = json.load(f)
            self.next_id = data.get("next_id", 1)
            self.active_task_id = data.get("active_task_id")
            self.tasks = [Task(**task_data) for task_data in data.get("tasks", [])]
        except Exception as e:
            print(f"Error loading tasks: {e}")


class Statistics:
    """Tracks daily pomodoro statistics"""

    def __init__(self):
        self.stats: Dict[str, Dict] = {}
        self.load_stats()

    def record_pomodoro(self, task_title: str):
        today = date.today().isoformat()
        if today not in self.stats:
            self.stats[today] = {
                "total_pomodoros": 0,
                "tasks": {}
            }

        self.stats[today]["total_pomodoros"] += 1

        if task_title not in self.stats[today]["tasks"]:
            self.stats[today]["tasks"][task_title] = 0
        self.stats[today]["tasks"][task_title] += 1

        self.save_stats()

    def get_today_stats(self) -> Dict:
        today = date.today().isoformat()
        return self.stats.get(today, {"total_pomodoros": 0, "tasks": {}})

    def save_stats(self):
        DATA_DIR.mkdir(exist_ok=True)
        with open(STATS_FILE, 'w') as f:
            json.dump(self.stats, f, indent=2)

    def load_stats(self):
        if not STATS_FILE.exists():
            return
        try:
            with open(STATS_FILE, 'r') as f:
                self.stats = json.load(f)
        except Exception as e:
            print(f"Error loading stats: {e}")


class PomodoroApp:
    """Main application with interactive UI"""

    def __init__(self):
        self.console = Console()
        self.timer = PomodoroTimer()
        self.task_manager = TaskManager()
        self.stats = Statistics()
        self.running = True
        self.show_help = False
        self.terminal_settings = None
        self.live_display = None

    def create_layout(self) -> Layout:
        """Create the terminal layout"""
        layout = Layout()
        layout.split_column(
            Layout(name="timer", size=8),
            Layout(name="tasks", size=15),
            Layout(name="stats", size=8),
            Layout(name="controls", size=3)
        )
        return layout

    def render_timer(self) -> Panel:
        """Render the timer panel"""
        # Session type display
        session_emoji = {
            SessionType.WORK: "🍅",
            SessionType.SHORT_BREAK: "☕",
            SessionType.LONG_BREAK: "🌴"
        }
        session_name = self.timer.session_type.value.replace('_', ' ').title()

        # State indicator
        state_text = {
            TimerState.STOPPED: "[yellow]Ready[/yellow]",
            TimerState.RUNNING: "[green]Running[/green]",
            TimerState.PAUSED: "[blue]Paused[/blue]"
        }

        # Time display
        time_text = Text(self.timer.get_time_display(), style="bold", justify="center")
        time_text.stylize("red" if self.timer.session_type == SessionType.WORK else "cyan", 0, len(time_text))

        # Progress bar
        progress = self.timer.get_progress()
        bar_width = 40
        filled = int(progress * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Active task
        active_task = self.task_manager.get_active_task()
        task_info = f"\nActive Task: {active_task.title}" if active_task else "\nNo active task"

        content = f"{session_emoji.get(self.timer.session_type, '')} {session_name} - {state_text[self.timer.state]}\n"
        content += f"\n{time_text}\n"
        content += f"{bar}\n"
        content += f"Pomodoros completed today: {self.timer.pomodoros_completed}"
        content += task_info

        return Panel(content, title="Pomodoro Timer", border_style="bold")

    def render_tasks(self) -> Panel:
        """Render the tasks panel"""
        table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
        table.add_column("ID", style="dim", width=4)
        table.add_column("Task", min_width=30)
        table.add_column("Priority", width=8)
        table.add_column("Progress", width=10)

        tasks = self.task_manager.get_incomplete_tasks(sort_by_priority=True)
        if not tasks:
            return Panel("No tasks yet. Press 'a' to add a task.", title="Tasks")

        for idx, task in enumerate(tasks[:10], 1):  # Show first 10 tasks
            # Mark active task and show selection number
            active_marker = '>' if task.id == self.task_manager.active_task_id else ' '
            task_id = f"{active_marker}[{idx}]"

            # Priority color
            priority_style = {
                "High": "red",
                "Medium": "yellow",
                "Low": "green"
            }
            priority = f"[{priority_style.get(task.priority, 'white')}]{task.priority}[/{priority_style.get(task.priority, 'white')}]"

            # Progress
            progress = f"{task.completed_pomodoros}/{task.estimated_pomodoros}"

            table.add_row(task_id, task.title, priority, progress)

        return Panel(table, title=f"Tasks ({len(tasks)} total)")

    def render_stats(self) -> Panel:
        """Render daily statistics"""
        today_stats = self.stats.get_today_stats()
        total = today_stats["total_pomodoros"]

        content = f"Total pomodoros today: {total}\n"

        if today_stats["tasks"]:
            content += "\nBreakdown by task:\n"
            for task_title, count in list(today_stats["tasks"].items())[:5]:
                content += f"  • {task_title}: {count}\n"
        else:
            content += "\nNo pomodoros completed yet today."

        return Panel(content, title="Today's Statistics", border_style="blue")

    def render_controls(self) -> Panel:
        """Render keyboard controls"""
        controls = (
            "[bold cyan]Controls:[/bold cyan] "
            "\\[1-9]select  \\[s]tart/pause  \\[k]ip  \\[a]dd  \\[e]dit  \\[c]omplete  \\[d]elete  \\[?]help  \\[q]uit"
        )
        return Panel(controls, border_style="dim")

    def render_help(self) -> Panel:
        """Render help panel"""
        help_text = """
[bold cyan]Keyboard Shortcuts:[/bold cyan]

[yellow]Timer Controls:[/yellow]
  s - Start/pause the timer
  k - Skip to next session

[yellow]Task Management:[/yellow]
  a - Add a new task
  e - Edit a task (prompts for ID)
  c - Complete a task (prompts for ID)
  d - Delete a task (prompts for ID)
  1-9 - Set task 1-9 as active

[yellow]Other:[/yellow]
  ? - Toggle this help
  q - Quit the application

[bold]How it works:[/bold]
1. Add tasks with 'a'
2. Select an active task (1-9)
3. Start the timer with 's'
4. Work for 25 minutes
5. Take breaks (5 min short, 15 min long every 4 pomodoros)

Press any key to close help...
"""
        return Panel(help_text, title="Help", border_style="green")

    def render(self) -> Layout:
        """Render the complete UI"""
        if self.show_help:
            layout = Layout()
            layout.update(self.render_help())
            return layout

        layout = self.create_layout()
        layout["timer"].update(self.render_timer())
        layout["tasks"].update(self.render_tasks())
        layout["stats"].update(self.render_stats())
        layout["controls"].update(self.render_controls())
        return layout

    def get_input_nonblocking(self) -> Optional[str]:
        """Get keyboard input without blocking"""
        import select
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None

    def pause_live_display(self):
        """Pause the live display for input"""
        if self.live_display:
            self.live_display.stop()
        import termios
        if self.terminal_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.terminal_settings)

    def resume_live_display(self):
        """Resume the live display after input"""
        import tty
        tty.setcbreak(sys.stdin.fileno())
        if self.live_display:
            self.live_display.start()

    def handle_input(self, key: str):
        """Handle keyboard input"""
        if self.show_help:
            self.show_help = False
            return

        if key == 'q':
            self.running = False
        elif key == '?':
            self.show_help = True
        elif key == 's':
            if self.timer.state == TimerState.RUNNING:
                self.timer.pause()
            else:
                self.timer.start()
        elif key == 'k':
            self.timer.skip()
        elif key == 'a':
            self.add_task_interactive()
        elif key == 'e':
            self.edit_task_interactive()
        elif key == 'c':
            self.complete_task_interactive()
        elif key == 'd':
            self.delete_task_interactive()
        elif key.isdigit() and '1' <= key <= '9':
            # Set active task by position (using same sort order as display)
            tasks = self.task_manager.get_incomplete_tasks(sort_by_priority=True)
            idx = int(key) - 1
            if idx < len(tasks):
                self.task_manager.set_active_task(tasks[idx].id)

    def add_task_interactive(self):
        """Prompt user to add a task"""
        self.pause_live_display()
        try:
            self.console.clear()
            self.console.print("[bold cyan]Add New Task[/bold cyan]\n")

            title = self.console.input("Task title: ")
            if not title:
                return

            self.console.print("\nPriority: [1] High  [2] Medium  [3] Low")
            priority_input = self.console.input("Choose (1-3): ")
            priority_map = {'1': 'High', '2': 'Medium', '3': 'Low'}
            priority = priority_map.get(priority_input, 'Medium')

            estimated_input = self.console.input("Estimated pomodoros: ")
            try:
                estimated = int(estimated_input) if estimated_input else 1
            except ValueError:
                estimated = 1

            self.task_manager.add_task(title, priority, estimated)
            self.console.print(f"\n[green]✓[/green] Task added!")
            time.sleep(1)
        finally:
            self.resume_live_display()

    def edit_task_interactive(self):
        """Prompt user to edit a task"""
        self.pause_live_display()
        try:
            self.console.clear()
            task_id_input = self.console.input("Task ID to edit: ")
            try:
                task_id = int(task_id_input)
            except ValueError:
                return

            task = self.task_manager.get_task(task_id)
            if not task:
                self.console.print("[red]Task not found![/red]")
                time.sleep(1)
                return

            self.console.print(f"\nEditing: {task.title}")
            self.console.print("(Press Enter to keep current value)\n")

            new_title = self.console.input(f"New title [{task.title}]: ")

            self.console.print("\nPriority: [1] High  [2] Medium  [3] Low")
            priority_input = self.console.input(f"Choose [{task.priority}]: ")
            priority_map = {'1': 'High', '2': 'Medium', '3': 'Low'}
            new_priority = priority_map.get(priority_input) if priority_input else None

            estimated_input = self.console.input(f"Estimated pomodoros [{task.estimated_pomodoros}]: ")
            new_estimated = int(estimated_input) if estimated_input else None

            self.task_manager.edit_task(
                task_id,
                title=new_title if new_title else None,
                priority=new_priority,
                estimated=new_estimated
            )
            self.console.print(f"\n[green]✓[/green] Task updated!")
            time.sleep(1)
        finally:
            self.resume_live_display()

    def complete_task_interactive(self):
        """Prompt user to complete a task"""
        self.pause_live_display()
        try:
            self.console.clear()
            task_id_input = self.console.input("Task ID to complete: ")
            try:
                task_id = int(task_id_input)
            except ValueError:
                return

            self.task_manager.complete_task(task_id)
            self.console.print(f"\n[green]✓[/green] Task completed!")
            time.sleep(1)
        finally:
            self.resume_live_display()

    def delete_task_interactive(self):
        """Prompt user to delete a task"""
        self.pause_live_display()
        try:
            self.console.clear()
            task_id_input = self.console.input("Task ID to delete: ")
            try:
                task_id = int(task_id_input)
            except ValueError:
                return

            self.task_manager.delete_task(task_id)
            self.console.print(f"\n[green]✓[/green] Task deleted!")
            time.sleep(1)
        finally:
            self.resume_live_display()

    def on_session_complete(self):
        """Handle session completion"""
        # Play meditation bell sound
        SoundPlayer.play_completion_sound()

        # Record work session
        if self.timer.session_type == SessionType.WORK:
            active_task = self.task_manager.get_active_task()
            if active_task:
                self.task_manager.increment_task_pomodoro(active_task.id)
                self.stats.record_pomodoro(active_task.title)
            else:
                self.stats.record_pomodoro("No task")

    def run(self):
        """Main application loop"""
        # Setup terminal for non-blocking input
        import tty
        import termios

        self.terminal_settings = termios.tcgetattr(sys.stdin)

        try:
            tty.setcbreak(sys.stdin.fileno())

            self.live_display = Live(self.render(), refresh_per_second=4, screen=True)
            self.live_display.start()

            try:
                while self.running:
                    # Update timer
                    if self.timer.update():
                        self.on_session_complete()

                    # Handle input
                    key = self.get_input_nonblocking()
                    if key:
                        self.handle_input(key)

                    # Update display
                    self.live_display.update(self.render())

                    # Small sleep to prevent CPU spinning
                    time.sleep(0.1)
            finally:
                self.live_display.stop()

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.terminal_settings)
            self.console.clear()
            self.console.print("\n[bold cyan]Pomodoro session ended. Have a productive day![/bold cyan]\n")


def main():
    """Entry point"""
    try:
        app = PomodoroApp()
        app.run()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
