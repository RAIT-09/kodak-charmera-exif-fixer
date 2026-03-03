import queue
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from typing import Callable, Optional

from ..core.models import (
    CameraFile, FileType, ProcessingPlan, ProcessingStatus, ProgressEvent,
)
from ..ports.presenter_port import PresenterPort

_POLL_INTERVAL_MS = 50


class TkinterPresenter(PresenterPort):

    def __init__(self) -> None:
        self._root: Optional[tk.Tk] = None
        self._confirm_event = threading.Event()
        self._confirmed = False
        self._plan: Optional[ProcessingPlan] = None
        self._dest_result: Optional[Path] = None
        self._queue: queue.Queue[Callable[[], None]] = queue.Queue()

        # Widgets
        self._dest_var: Optional[tk.StringVar] = None
        self._tree: Optional[ttk.Treeview] = None
        self._progress_var: Optional[tk.DoubleVar] = None
        self._progress_bar: Optional[ttk.Progressbar] = None
        self._status_label: Optional[ttk.Label] = None
        self._start_btn: Optional[ttk.Button] = None
        self._dest_entry: Optional[ttk.Entry] = None

    def run(self, on_start_callback: Callable[[], None]) -> None:
        self._on_start = on_start_callback
        self._root = tk.Tk()
        self._root.title("Kodak Charmera EXIF Fixer")
        self._root.geometry("700x500")
        self._root.minsize(600, 400)
        self._build_ui()

        # Start polling the queue on the main thread
        self._poll_queue()

        # Run pipeline in background thread with error handling
        def _safe_run() -> None:
            try:
                self._on_start()
            except Exception as e:
                tb = traceback.format_exc()
                self._enqueue(lambda: self._set_status(f"Error: {e}"))
                print(f"Pipeline error:\n{tb}")

        thread = threading.Thread(target=_safe_run, daemon=True)
        thread.start()

        self._root.mainloop()

    def _poll_queue(self) -> None:
        """Drain the queue on the main thread."""
        try:
            while True:
                func = self._queue.get_nowait()
                func()
        except queue.Empty:
            pass
        if self._root:
            self._root.after(_POLL_INTERVAL_MS, self._poll_queue)

    def _enqueue(self, func: Callable[[], None]) -> None:
        """Thread-safe: put a UI update on the queue."""
        self._queue.put(func)

    def _build_ui(self) -> None:
        assert self._root is not None

        # Destination frame
        dest_frame = ttk.LabelFrame(self._root, text="Destination", padding=8)
        dest_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        self._dest_var = tk.StringVar(
            value=str(Path.home() / "Pictures" / "KodakCharmera")
        )
        self._dest_entry = ttk.Entry(dest_frame, textvariable=self._dest_var)
        self._dest_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        browse_btn = ttk.Button(dest_frame, text="Browse...", command=self._browse)
        browse_btn.pack(side=tk.RIGHT)

        # File list frame
        list_frame = ttk.LabelFrame(self._root, text="Files", padding=8)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("name", "type", "size", "fixes")
        self._tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        self._tree.heading("name", text="File")
        self._tree.heading("type", text="Type")
        self._tree.heading("size", text="Size")
        self._tree.heading("fixes", text="Fixes")
        self._tree.column("name", width=200)
        self._tree.column("type", width=80)
        self._tree.column("size", width=80)
        self._tree.column("fixes", width=250)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Progress frame
        progress_frame = ttk.Frame(self._root, padding=8)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)

        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            progress_frame, variable=self._progress_var, maximum=100,
        )
        self._progress_bar.pack(fill=tk.X)

        self._status_label = ttk.Label(progress_frame, text="Scanning camera...")
        self._status_label.pack(fill=tk.X, pady=(5, 0))

        # Button frame
        btn_frame = ttk.Frame(self._root, padding=8)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self._start_btn = ttk.Button(
            btn_frame, text="Start", command=self._on_confirm, state=tk.DISABLED,
        )
        self._start_btn.pack(side=tk.RIGHT, padx=(5, 0))

        cancel_btn = ttk.Button(btn_frame, text="Close", command=self._on_cancel)
        cancel_btn.pack(side=tk.RIGHT)

    def _browse(self) -> None:
        assert self._dest_var is not None
        path = filedialog.askdirectory(initialdir=self._dest_var.get())
        if path:
            self._dest_var.set(path)

    def _on_confirm(self) -> None:
        self._confirmed = True
        # Read destination on main thread (safe) before unblocking pipeline thread
        if self._dest_var:
            self._dest_result = Path(self._dest_var.get())
        if self._start_btn:
            self._start_btn.config(state=tk.DISABLED)
        if self._dest_entry:
            self._dest_entry.config(state=tk.DISABLED)
        self._confirm_event.set()

    def _on_cancel(self) -> None:
        self._confirmed = False
        self._confirm_event.set()
        if self._root:
            self._root.after(100, self._root.destroy)

    def _set_status(self, text: str) -> None:
        if self._status_label:
            self._status_label.config(text=text)

    # PresenterPort implementation

    def show_scanning(self, volume_path: Path) -> None:
        self._enqueue(lambda: self._set_status(f"Scanning {volume_path}..."))

    def show_preview(self, plan: ProcessingPlan) -> bool:
        self._plan = plan
        self._enqueue(self._populate_preview)
        # Block pipeline thread until user clicks Start or Cancel
        self._confirm_event.wait()
        self._confirm_event.clear()
        return self._confirmed

    def _populate_preview(self) -> None:
        assert self._tree is not None and self._plan is not None

        for f in self._plan.files:
            size_str = self._format_size(f.file_size)
            fixes = self._describe_fixes(f)
            self._tree.insert(
                "", tk.END,
                values=(f.source_path.name, f.file_type.value, size_str, fixes),
            )

        self._set_status(
            f"Found {self._plan.photo_count} photo(s), "
            f"{self._plan.video_count} video(s). "
            f"Total: {self._format_size(self._plan.total_copy_bytes)}"
        )
        if self._start_btn:
            self._start_btn.config(state=tk.NORMAL)

    def on_progress(self, event: ProgressEvent) -> None:
        self._enqueue(lambda: self._update_progress(event))

    def _update_progress(self, event: ProgressEvent) -> None:
        if self._progress_var:
            self._progress_var.set(event.progress_percent)
        self._set_status(f"{event.file.source_path.name}: {event.message}")

    def on_complete(self, results: list[CameraFile]) -> None:
        succeeded = sum(1 for f in results if f.status == ProcessingStatus.COMPLETED)
        failed = sum(1 for f in results if f.status == ProcessingStatus.FAILED)

        def _update() -> None:
            if self._progress_var:
                self._progress_var.set(100)
            self._set_status(f"Complete: {succeeded} succeeded, {failed} failed")
            if self._start_btn:
                self._start_btn.config(text="Done", state=tk.DISABLED)

        self._enqueue(_update)

    def on_error(self, message: str, exception: Exception | None = None) -> None:
        self._enqueue(lambda: self._set_status(f"Error: {message}"))

    def prompt_destination(self, default: Path) -> Path:
        if self._dest_result:
            return self._dest_result
        return default

    def show_no_camera(self) -> None:
        self._enqueue(
            lambda: self._set_status(
                "No Kodak Charmera detected. Connect the camera and restart."
            )
        )

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / 1024 / 1024:.1f} MB"

    @staticmethod
    def _describe_fixes(f: CameraFile) -> str:
        if f.file_type == FileType.VIDEO:
            return "Convert to MP4"
        if f.exif_fix and f.exif_fix.has_fixes:
            fixes = []
            if f.exif_fix.fixed_modify_date:
                fixes.append("date format")
            if f.exif_fix.fixed_width:
                fixes.append("dimensions")
            return ", ".join(fixes)
        return "No fixes needed"
