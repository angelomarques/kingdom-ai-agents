"""Tkinter GUI for image selection across slides."""

import logging
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

from PIL import Image, ImageTk

from agents.image_selector.models import ImageItem, ImageSelection, Slide

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Theme constants
# ──────────────────────────────────────────────
_BG = "#1a1a2e"
_BG_CARD = "#16213e"
_BG_CARD_HOVER = "#1c2d50"
_BG_SELECTED = "#0f3460"
_ACCENT = "#e94560"
_TEXT = "#eaeaea"
_TEXT_DIM = "#8d99ae"
_TEXT_TAG = "#a3bffa"
_BORDER_SELECTED = "#e94560"
_BORDER_DEFAULT = "#2b3a55"
_BTN_SKIP_BG = "#2b3a55"
_BTN_SKIP_FG = "#8d99ae"
_PROGRESS_BG = "#2b3a55"
_PROGRESS_FILL = "#e94560"

_THUMB_SIZE = (220, 220)
_WINDOW_MIN_W = 900
_WINDOW_MIN_H = 700


class ImageSelectorGUI:
    """Slide-based image selector using tkinter.

    Usage:
        gui = ImageSelectorGUI(slides, image_paths)
        gui.run()  # blocks until all slides are done or window is closed
        selections = gui.selections
        skipped = gui.skipped_slides
    """

    def __init__(
        self,
        slides: list[Slide],
        image_paths: dict[str, Path | None],
    ):
        """Initialize the GUI.

        Args:
            slides: List of Slide objects to present.
            image_paths: Mapping of image URL -> local file path (or None).
        """
        self._slides = slides
        self._image_paths = image_paths
        self._current_index = 0
        self._selected_image_index: int | None = None

        # History stack for go-back support: list of (action, slide_index)
        # action is "select" or "skip"
        self._history: list[tuple[str, int]] = []

        # Results
        self.selections: list[ImageSelection] = []
        self.skipped_slides: list[int] = []

        # Tk image references (prevent garbage collection)
        self._tk_images: list[ImageTk.PhotoImage] = []

        # Build the window
        self._root = tk.Tk()
        self._root.title("Image Selector")
        self._root.configure(bg=_BG)
        self._root.minsize(_WINDOW_MIN_W, _WINDOW_MIN_H)
        self._root.geometry("1100x800")

        # Center on screen
        self._root.update_idletasks()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = (sw - 1100) // 2
        y = (sh - 800) // 2
        self._root.geometry(f"+{x}+{y}")

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Fonts
        self._font_title = tkfont.Font(family="Helvetica", size=20, weight="bold")
        self._font_desc = tkfont.Font(family="Helvetica", size=12)
        self._font_img_desc = tkfont.Font(family="Helvetica", size=10)
        self._font_tag = tkfont.Font(family="Helvetica", size=9)
        self._font_btn = tkfont.Font(family="Helvetica", size=12, weight="bold")
        self._font_progress = tkfont.Font(family="Helvetica", size=10)

        self._build_layout()
        self._render_slide()

    # ──────────────────────────────────────────
    # Layout
    # ──────────────────────────────────────────

    def _build_layout(self) -> None:
        """Build the main window layout structure."""
        # Main container
        self._main_frame = tk.Frame(self._root, bg=_BG)
        self._main_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=16)

        # ── Top section: progress + title ──
        top_frame = tk.Frame(self._main_frame, bg=_BG)
        top_frame.pack(fill=tk.X, pady=(0, 12))

        # Progress bar canvas
        self._progress_canvas = tk.Canvas(
            top_frame, height=6, bg=_PROGRESS_BG, highlightthickness=0
        )
        self._progress_canvas.pack(fill=tk.X, pady=(0, 12))

        # Slide counter
        self._progress_label = tk.Label(
            top_frame, text="", font=self._font_progress,
            bg=_BG, fg=_TEXT_DIM, anchor="e",
        )
        self._progress_label.pack(fill=tk.X)

        # Title
        self._title_label = tk.Label(
            top_frame, text="", font=self._font_title,
            bg=_BG, fg=_TEXT, anchor="w", wraplength=1000, justify="left",
        )
        self._title_label.pack(fill=tk.X, pady=(4, 0))

        # Description
        self._desc_label = tk.Label(
            top_frame, text="", font=self._font_desc,
            bg=_BG, fg=_TEXT_DIM, anchor="w", wraplength=1000, justify="left",
        )
        self._desc_label.pack(fill=tk.X, pady=(2, 0))

        # ── Middle section: scrollable image grid ──
        grid_container = tk.Frame(self._main_frame, bg=_BG)
        grid_container.pack(fill=tk.BOTH, expand=True, pady=(8, 8))

        self._canvas = tk.Canvas(grid_container, bg=_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(
            grid_container, orient="vertical", command=self._canvas.yview
        )
        self._canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._grid_frame = tk.Frame(self._canvas, bg=_BG)
        self._grid_window = self._canvas.create_window(
            (0, 0), window=self._grid_frame, anchor="nw"
        )

        self._grid_frame.bind("<Configure>", self._on_grid_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse wheel scrolling
        self._canvas.bind_all("<Button-4>", self._on_mousewheel_up)
        self._canvas.bind_all("<Button-5>", self._on_mousewheel_down)

        # ── Bottom section: buttons ──
        btn_frame = tk.Frame(self._main_frame, bg=_BG)
        btn_frame.pack(fill=tk.X, pady=(12, 0))

        self._back_btn = tk.Button(
            btn_frame, text="← Go Back", font=self._font_btn,
            bg=_BTN_SKIP_BG, fg=_BTN_SKIP_FG,
            activebackground=_BG_CARD_HOVER, activeforeground=_TEXT,
            relief="flat", cursor="hand2", padx=24, pady=10,
            command=self._on_go_back,
        )
        self._back_btn.pack(side=tk.LEFT)

        self._skip_btn = tk.Button(
            btn_frame, text="Skip →", font=self._font_btn,
            bg=_BTN_SKIP_BG, fg=_BTN_SKIP_FG,
            activebackground=_BG_CARD_HOVER, activeforeground=_TEXT,
            relief="flat", cursor="hand2", padx=24, pady=10,
            command=self._on_skip,
        )
        self._skip_btn.pack(side=tk.RIGHT)

    # ──────────────────────────────────────────
    # Slide rendering
    # ──────────────────────────────────────────

    def _render_slide(self) -> None:
        """Render the current slide."""
        if self._current_index >= len(self._slides):
            self._finish()
            return

        slide = self._slides[self._current_index]
        self._selected_image_index = None
        self._tk_images.clear()

        # Update header
        total = len(self._slides)
        current = self._current_index + 1
        self._progress_label.config(text=f"Slide {current} of {total}")
        self._title_label.config(text=slide.title)
        self._desc_label.config(text=slide.description if slide.description else "")

        # Update progress bar
        self._draw_progress_bar(current, total)

        # Show/hide the back button depending on whether we can go back
        if self._current_index == 0:
            self._back_btn.pack_forget()
        else:
            self._back_btn.pack(side=tk.LEFT)

        # Clear the grid
        for widget in self._grid_frame.winfo_children():
            widget.destroy()

        # Render image cards
        self._image_cards: list[tk.Frame] = []

        for img_idx, image_item in enumerate(slide.images):
            self._render_image_card(img_idx, image_item)

        # Reset scroll
        self._canvas.yview_moveto(0)

    def _render_image_card(self, idx: int, image_item: ImageItem) -> None:
        """Render a single image card in the grid."""
        # Determine grid position (3 columns)
        cols = 3
        row = idx // cols
        col = idx % cols

        # Card frame
        card = tk.Frame(
            self._grid_frame, bg=_BG_CARD, cursor="hand2",
            highlightbackground=_BORDER_DEFAULT, highlightthickness=2,
            padx=8, pady=8,
        )
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        # Configure column weights for even distribution
        self._grid_frame.columnconfigure(col, weight=1)

        # Load and display thumbnail
        local_path = self._image_paths.get(image_item.url)
        tk_img = self._load_thumbnail(local_path)
        self._tk_images.append(tk_img)

        img_label = tk.Label(card, image=tk_img, bg=_BG_CARD, cursor="hand2")
        img_label.pack(pady=(4, 6))

        # Image description
        desc_label = tk.Label(
            card, text=image_item.description, font=self._font_img_desc,
            bg=_BG_CARD, fg=_TEXT, wraplength=200, justify="center",
        )
        desc_label.pack(pady=(0, 4))

        # Tags
        if image_item.tags:
            tags_text = " · ".join(f"#{t}" for t in image_item.tags[:5])
            tags_label = tk.Label(
                card, text=tags_text, font=self._font_tag,
                bg=_BG_CARD, fg=_TEXT_TAG, wraplength=200, justify="center",
            )
            tags_label.pack(pady=(0, 4))

        # Store reference
        self._image_cards.append(card)

        # Bind click events to the card and all children
        for widget in [card, img_label, desc_label]:
            widget.bind("<Button-1>", lambda e, i=idx: self._on_image_click(i))

        # Hover effects
        def on_enter(e, c=card, i=idx):
            if self._selected_image_index != i:
                c.configure(bg=_BG_CARD_HOVER)
                for child in c.winfo_children():
                    try:
                        child.configure(bg=_BG_CARD_HOVER)
                    except tk.TclError:
                        pass

        def on_leave(e, c=card, i=idx):
            if self._selected_image_index != i:
                c.configure(bg=_BG_CARD)
                for child in c.winfo_children():
                    try:
                        child.configure(bg=_BG_CARD)
                    except tk.TclError:
                        pass

        for widget in [card, img_label, desc_label]:
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)

    def _load_thumbnail(self, path: Path | None) -> ImageTk.PhotoImage:
        """Load an image file and return a tkinter-compatible thumbnail."""
        if path and path.exists():
            try:
                img = Image.open(path)
                img.thumbnail(_THUMB_SIZE, Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
            except Exception as e:
                logger.warning(f"Failed to load image {path}: {e}")

        # Placeholder — dark gray rectangle with "No Image" text
        img = Image.new("RGB", _THUMB_SIZE, color=(43, 58, 85))
        return ImageTk.PhotoImage(img)

    def _draw_progress_bar(self, current: int, total: int) -> None:
        """Draw the progress bar on the canvas."""
        self._progress_canvas.delete("all")
        self._progress_canvas.update_idletasks()
        w = self._progress_canvas.winfo_width()
        h = self._progress_canvas.winfo_height()

        if w <= 1:
            w = 800  # Fallback before first render

        # Background
        self._progress_canvas.create_rectangle(
            0, 0, w, h, fill=_PROGRESS_BG, outline=""
        )

        # Fill
        fill_w = int(w * (current / total))
        if fill_w > 0:
            self._progress_canvas.create_rectangle(
                0, 0, fill_w, h, fill=_PROGRESS_FILL, outline=""
            )

    # ──────────────────────────────────────────
    # Event handlers
    # ──────────────────────────────────────────

    def _on_image_click(self, idx: int) -> None:
        """Handle clicking on an image card — immediately selects and advances."""
        # Briefly highlight the selected card for visual feedback
        card = self._image_cards[idx]
        card.configure(highlightbackground=_BORDER_SELECTED, bg=_BG_SELECTED)
        for child in card.winfo_children():
            try:
                child.configure(bg=_BG_SELECTED)
            except tk.TclError:
                pass

        # Record the selection
        slide = self._slides[self._current_index]
        selected_image = slide.images[idx]

        selection = ImageSelection(
            slide_index=self._current_index,
            slide_title=slide.title,
            selected_image=selected_image,
        )
        self.selections.append(selection)
        # Track the action so _on_go_back knows what to undo
        self._history.append(("select", self._current_index))
        logger.info(
            f"   Selected image {idx + 1} "
            f"on slide {self._current_index + 1}: {selected_image.description}"
        )

        self._current_index += 1
        # Small delay so the user sees the highlight before moving on
        self._root.after(150, self._render_slide)

    def _on_skip(self) -> None:
        """Skip the current slide."""
        logger.info(f"   Skipped slide {self._current_index + 1}")
        self.skipped_slides.append(self._current_index)
        self._history.append(("skip", self._current_index))
        self._current_index += 1
        self._render_slide()

    def _on_go_back(self) -> None:
        """Go back to the previous slide and undo the last action."""
        if not self._history:
            return

        action, slide_idx = self._history.pop()

        if action == "select":
            # Remove the last selection
            if self.selections and self.selections[-1].slide_index == slide_idx:
                removed = self.selections.pop()
                logger.info(
                    f"   Undid selection on slide {slide_idx + 1}: "
                    f"{removed.selected_image.description}"
                )
        elif action == "skip":
            # Remove from skipped list
            if slide_idx in self.skipped_slides:
                self.skipped_slides.remove(slide_idx)
                logger.info(f"   Undid skip on slide {slide_idx + 1}")

        self._current_index = slide_idx
        self._render_slide()

    def _on_close(self) -> None:
        """Handle window close — save partial results."""
        logger.info("Window closed by user — saving partial selections")
        self._root.destroy()

    def _finish(self) -> None:
        """All slides completed."""
        logger.info("All slides completed")
        self._root.destroy()

    def _on_grid_configure(self, event: tk.Event) -> None:
        """Update scrollregion when grid size changes."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Resize the grid frame to fill the canvas width."""
        self._canvas.itemconfig(self._grid_window, width=event.width)

    def _on_mousewheel_up(self, event: tk.Event) -> None:
        """Scroll up."""
        self._canvas.yview_scroll(-1, "units")

    def _on_mousewheel_down(self, event: tk.Event) -> None:
        """Scroll down."""
        self._canvas.yview_scroll(1, "units")

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def run(self) -> None:
        """Start the GUI main loop (blocks until closed)."""
        self._root.mainloop()
