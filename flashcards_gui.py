#!/usr/bin/env python3
"""
Flashcards Publisher - Professional GUI
A modern interface for creating and publishing flashcards.
"""
import os
import json
import shutil
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk
from typing import Optional
import subprocess
import sys
import time
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LUCAS_BASE_GRADE = "六下"
LUCY_BASE_GRADE = "八下"
CUSTOM_UNIT_OPTION = "用户自定义"
LUCAS_UNITS = ("1", "2", "3", "4", "5", "6", "期中复习", "期末复习", "其他", CUSTOM_UNIT_OPTION)
PASSAGE_GRADES = ("六下", "六上", "七下", "七上", "八下", "八上", "九下", "九上")
DEFAULT_PASSAGE_GRADE = "六下"


# ==================== Modern Color Scheme ====================
class Colors:
    """Modern color palette for the application."""
    BG_PRIMARY = "#f5f7fa"      # Light gray background
    BG_CARD = "#ffffff"         # White card background
    BG_SECONDARY = "#e8ecf1"    # Secondary background
    TEXT_PRIMARY = "#2c3e50"    # Dark text
    TEXT_SECONDARY = "#7f8c8d"  # Secondary text
    TEXT_MUTED = "#95a5a6"      # Muted text
    ACCENT_PRIMARY = "#3498db"  # Blue accent
    ACCENT_SUCCESS = "#27ae60"  # Green for success
    ACCENT_LUCAS = "#9b59b6"    # Purple for Lucas
    ACCENT_LUCY = "#e74c3c"     # Red for Lucy
    ACCENT_WENYANWEN = "#ff6b6b"  # Red for Wenyanwen
    ACCENT_PASSAGE = "#2193b0"    # Teal for English Passages
    BORDER = "#dfe6e9"          # Border color
    SHADOW = "#bdc3c7"          # Shadow color


# ==================== Utility Functions ====================

def _grade_value(base_grade: str, unit: str) -> str:
    unit = unit.strip()
    if unit.isdigit():
        return f"{base_grade}U{unit}"
    return f"{base_grade}{unit}"


def _safe_filename_component(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "untitled"
    for ch in ("/", "\\", ":", "\n", "\r", "\t"):
        s = s.replace(ch, "_")
    return s


def _slugify(s: str) -> str:
    """Convert to ASCII-safe string for URLs (e.g. 'lucas_六下U4' -> 'lucas_G6-2U4')."""
    import unicodedata
    # Replace known Chinese grade/unit terms first
    replacements = {
        "六下": "G6-2", "六上": "G6-1",
        "七下": "G7-2", "七上": "G7-1",
        "八下": "G8-2", "八上": "G8-1",
        "九下": "G9-2", "九上": "G9-1",
        "期中复习": "midterm", "期末复习": "final",
        "期中": "midterm", "期末": "final",
        "作文": "writing",
        "其他": "other",
    }
    for cn, en in replacements.items():
        s = s.replace(cn, en)
    # Strip remaining non-ASCII
    parts = []
    for ch in s:
        if ch.isascii() and (ch.isalnum() or ch in ('_', '-', '.')):
            parts.append(ch)
    return ''.join(parts).strip('_') or 'flashcard'


def _resolve_unit_from_ui(unit_choice: str) -> Optional[str]:
    unit_choice = (unit_choice or "").strip()
    if unit_choice != CUSTOM_UNIT_OPTION:
        return unit_choice

    custom = simpledialog.askstring(
        "Custom unit",
        "Enter unit name (examples: U7, 期中复习, 单元复习):",
    )
    if custom is None:
        return None
    custom = custom.strip()
    return custom if custom else None


def _infer_base_grade_from_template(template: str) -> Optional[str]:
    """Try to infer base grade from an existing 'grade:' line."""
    for line in template.splitlines():
        s = line.strip()
        if not s.startswith("grade:"):
            continue
        value = s[len("grade:") :].strip()
        if not value:
            return None
        if "U" in value:
            left = value.split("U", 1)[0]
            return left.rstrip("-_ /").strip() or None
        for sep in ("-", "_", " "):
            if sep in value:
                return value.split(sep, 1)[0].strip() or None
        return value.strip() or None
    return None


def _today_yyyymmdd() -> str:
    return datetime.now().strftime("%Y%m%d")


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _inject_preset(html_path: str, preset_js: str) -> None:
    """Inject a new preset entry into the presets array of an HTML file."""
    content = _read_text(html_path)
    # Find 'const presets = [' and insert after the opening bracket
    pattern = r'(const presets\s*=\s*\[)'
    match = re.search(pattern, content)
    if not match:
        raise RuntimeError(f"Could not find 'const presets = [' in {html_path}")
    insert_pos = match.end()
    new_content = content[:insert_pos] + "\n    " + preset_js + "," + content[insert_pos:]
    _write_text(html_path, new_content)


def _ensure_index_card(tab_id: str, grade: str, grade_slug: str, css_class: str,
                       icon: str, desc: str) -> None:
    """Add a grade card to index.html under the given tab if not already present."""
    index_path = os.path.join(BASE_DIR, "index.html")
    content = _read_text(index_path)
    filename = f"{tab_id}_{grade_slug}.html"
    # Already has a card for this grade file
    if filename in content:
        return

    card_html = (
        f'                <a href="https://bexiang.github.io/{filename}" '
        f'class="nav-card {css_class}">\n'
        f'                    <div class="card-header">\n'
        f'                        <span class="card-icon">{icon}</span>\n'
        f'                        <span class="card-title">{desc}（{grade}）</span>\n'
        f'                    </div>\n'
        f'                </a>\n'
    )

    # Find the card-list inside the target tab section
    tab_marker = f'<div class="tab-content" id="{tab_id}">'
    tab_idx = content.find(tab_marker)
    if tab_idx == -1:
        return
    list_marker = '<div class="card-list">'
    list_idx = content.find(list_marker, tab_idx)
    if list_idx == -1:
        return
    insert_pos = list_idx + len(list_marker)
    new_content = content[:insert_pos] + "\n" + card_html + content[insert_pos:]
    _write_text(index_path, new_content)


def _run_v5_and_move_html(*, config_path: str, html_dir: str) -> str:
    """Run v5.py on the given config file and move/rename the generated HTML."""
    v5_path = os.path.join(BASE_DIR, "v5.py")
    if not os.path.exists(v5_path):
        raise FileNotFoundError(f"v5.py not found at: {v5_path}")

    config_dir = os.path.dirname(os.path.abspath(config_path))
    config_base = os.path.basename(config_path)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    start = time.time()
    proc = subprocess.run(
        [sys.executable, v5_path, config_base],
        cwd=config_dir,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or f"v5.py failed with code {proc.returncode}"
        raise RuntimeError(msg)

    candidates = []
    for fn in os.listdir(config_dir):
        if not fn.lower().endswith(".html"):
            continue
        full = os.path.join(config_dir, fn)
        try:
            mtime = os.path.getmtime(full)
        except OSError:
            continue
        if mtime >= start - 2:
            candidates.append((mtime, full))
    if not candidates:
        for fn in os.listdir(config_dir):
            if fn.lower().endswith(".html"):
                full = os.path.join(config_dir, fn)
                try:
                    candidates.append((os.path.getmtime(full), full))
                except OSError:
                    pass
    if not candidates:
        raise RuntimeError("v5.py succeeded but no HTML file was produced.")

    candidates.sort(key=lambda t: t[0], reverse=True)
    produced_html = candidates[0][1]

    _ensure_dir(html_dir)
    final_name = os.path.splitext(config_base)[0] + ".html"
    final_path = os.path.join(html_dir, final_name)
    os.replace(produced_html, final_path)
    return final_path


def _run_v5cat_and_move_html(*, config_path: str, html_dir: str) -> str:
    """Run v5cat.py on the given config file and move/rename the generated HTML."""
    v5cat_path = os.path.join(BASE_DIR, "v5cat.py")
    if not os.path.exists(v5cat_path):
        raise FileNotFoundError(f"v5cat.py not found at: {v5cat_path}")

    config_dir = os.path.dirname(os.path.abspath(config_path))
    config_base = os.path.basename(config_path)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    start = time.time()
    proc = subprocess.run(
        [sys.executable, v5cat_path, config_base],
        cwd=config_dir,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or f"v5cat.py failed with code {proc.returncode}"
        raise RuntimeError(msg)

    candidates = []
    for fn in os.listdir(config_dir):
        if not fn.lower().endswith(".html"):
            continue
        full = os.path.join(config_dir, fn)
        try:
            mtime = os.path.getmtime(full)
        except OSError:
            continue
        if mtime >= start - 2:
            candidates.append((mtime, full))
    if not candidates:
        for fn in os.listdir(config_dir):
            if fn.lower().endswith(".html"):
                full = os.path.join(config_dir, fn)
                try:
                    candidates.append((os.path.getmtime(full), full))
                except OSError:
                    pass
    if not candidates:
        raise RuntimeError("v5cat.py succeeded but no HTML file was produced.")

    candidates.sort(key=lambda t: t[0], reverse=True)
    produced_html = candidates[0][1]

    _ensure_dir(html_dir)
    final_name = os.path.splitext(config_base)[0] + ".html"
    final_path = os.path.join(html_dir, final_name)
    os.replace(produced_html, final_path)
    return final_path


def _publish_html_to_github(*, html_path: str, publish_name: str = None) -> str:
    """Publish the given HTML file to GitHub Pages."""
    publisher = os.path.join(BASE_DIR, "publish_github.py")
    if not os.path.exists(publisher):
        raise FileNotFoundError(f"publish_github.py not found at: {publisher}")
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    cmd = [sys.executable, publisher, "--html-file", os.path.abspath(html_path)]
    if publish_name:
        cmd.extend(["--project-name", publish_name])

    proc = subprocess.run(
        cmd,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or f"publish_github.py failed with code {proc.returncode}"
        raise RuntimeError(msg)

    lines = (proc.stdout or "").strip().splitlines()
    url = lines[-1].strip() if lines else ""
    if not (url.startswith("http://") or url.startswith("https://")):
        raise RuntimeError(f"Unexpected publish output: {(proc.stdout or '').strip()}")
    return url


def _update_index_html(*, person: str, card_title: str, published_url: str) -> None:
    """Update index.html to add the new flashcard link to the corresponding tab with date grouping."""
    from datetime import datetime, timedelta

    index_path = os.path.join(BASE_DIR, "index.html")
    if not os.path.exists(index_path):
        print(f"Warning: index.html not found at {index_path}, skipping update")
        return

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Warning: Failed to read index.html: {e}")
        return

    person_lower_key = person.lower()
    person_title = person.title()  # Convert "LUCAS" to "Lucas", "LUCY" to "Lucy"
    tab_id = person_lower_key
    card_class = person_lower_key

    # Extract date from card title (format: lucas_六下U2_20260326)
    def extract_date_from_title(title):
        if '_' in title:
            date_part = title.split('_')[-1]
            if len(date_part) == 8 and date_part.isdigit():
                try:
                    return datetime.strptime(date_part, '%Y%m%d')
                except:
                    return None
        return None

    # Format date for display (YYYY-MM-DD)
    def format_display_date(date_obj):
        return date_obj.strftime('%Y-%m-%d')

    # Determine which group a date belongs to (natural month grouping)
    def get_date_group(card_date):
        today = datetime.now()
        if not card_date:
            return 'older', '更早', '99'

        # Calculate month difference
        year_diff = today.year - card_date.year
        month_diff = today.month - card_date.month
        total_months = year_diff * 12 + month_diff

        # This week (within 7 days)
        days_diff = (today - card_date).days
        if days_diff <= 7:
            return 'this_week', '本周', '1'

        # Natural month grouping
        if total_months == 0:
            return 'this_month', f'{today.month}月', '2'
        elif total_months == 1:
            return 'last_month', f'{card_date.month}月', '3'
        elif total_months == 2:
            return 'two_months_ago', f'{card_date.month}月', '4'
        elif total_months == 3:
            return 'three_months_ago', f'{card_date.month}月', '5'
        else:
            # Older: show year and month
            return 'older', f'{card_date.year}年{card_date.month}月', '99'

    # Parse existing cards in this tab
    # Match from comment to next tab comment or end of file
    tab_pattern = rf'<!-- Tab 内容: {person_title} -->(.*?)(?=<!-- Tab 内容:|$)'
    tab_match = re.search(tab_pattern, content, re.DOTALL)

    if tab_match:
        full_section = tab_match.group(1)
        print(f"ℹ️  Full section length for {person}: {len(full_section)} chars")
        # Find all cards in this section regardless of structure
        card_pattern = r'<a href="([^"]*)" class="nav-card ' + card_class + r'">.*?<span class="card-title">([^<]+)</span>.*?</a>'
        cards = re.findall(card_pattern, full_section, re.DOTALL)
        cards_data = [(title, url) for url, title in cards]
        print(f"ℹ️  Found {len(cards_data)} existing cards for {person}: {[t for t, _ in cards_data]}")
    else:
        cards_data = []
        print(f"⚠️  No existing content found for {person}")

    # Check if new card already exists
    if any(card_title == title for title, _ in cards_data):
        print(f"ℹ️  Card '{card_title}' already exists in index.html, skipping")
        return

    # Add new card
    cards_data.append((card_title, published_url))

    # Group all cards by date (dynamic grouping by natural month)
    from collections import OrderedDict
    grouped = OrderedDict()

    for title, url in cards_data:
        card_date = extract_date_from_title(title)
        group_key, group_name, order = get_date_group(card_date)
        dynamic_key = f"{order}_{group_name}"  # Use order for sorting

        if dynamic_key not in grouped:
            grouped[dynamic_key] = {
                'name': group_name,
                'order': order,
                'cards': []
            }
        grouped[dynamic_key]['cards'].append((title, url, card_date))

    # Sort groups by order
    sorted_groups = sorted(grouped.items(), key=lambda x: int(x[0].split('_')[0]))

    # Generate grouped HTML
    grouped_html_parts = []
    is_first_group = True

    for dynamic_key, group_info in sorted_groups:
        group_cards = group_info['cards']
        if not group_cards:
            continue

        # Sort cards within group by date (newest first)
        group_cards.sort(key=lambda x: (x[2] is not None, x[2]), reverse=True)

        card_count = len(group_cards)
        group_name = group_info['name']

        # Group header (first group expanded, others collapsed)
        grouped_html_parts.append(f'''            <div class="date-group">
                <div class="date-group-header" onclick="toggleGroup(this)">
                    <span>📅 {group_name} ({card_count})</span>
                    <span class="toggle-icon">{'▼' if is_first_group else '▶'}</span>
                </div>
                <div class="date-group-content{' collapsed' if not is_first_group else ''}">
                    <div class="card-list">''')

        # Cards in this group
        for title, url, card_date in group_cards:
            formatted_date = format_display_date(card_date) if card_date else ""

            grouped_html_parts.append(f'''                    <a href="{url}" class="nav-card {card_class}">
                        <div class="card-header">
                            <span class="card-icon">📝</span>
                            <span class="card-title">{title}</span>
                            <span class="card-date">{formatted_date}</span>
                        </div>
                    </a>''')

        # Close group
        grouped_html_parts.append('''                    </div>
                </div>
            </div>''')

        is_first_group = False

    # Build new tab content
    if grouped_html_parts:
        # Add 'active' class to Lucas tab by default
        active_class = ' active' if person_lower_key == 'lucas' else ''
        new_tab_content = f'''        <div class="tab-content{active_class}" id="{tab_id}">
{''.join(grouped_html_parts)}
        </div>'''

        # Replace the entire tab section (from comment to next tab comment)
        # Stop before next tab comment or before closing divs + footer
        tab_replace_pattern = rf'<!-- Tab 内容: {person_title} -->.*?(?=\s*<!-- Tab 内容:|<div class="footer">|$)'
        new_tab_full = f'''<!-- Tab 内容: {person_title} -->
{new_tab_content}
'''

        content = re.sub(tab_replace_pattern, new_tab_full, content, flags=re.DOTALL)

    # Write back
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✓ Updated index.html with new {person} flashcard link: {card_title}")
    except Exception as e:
        print(f"Warning: Failed to write index.html: {e}")


def _set_date_line(template: str, yyyymmdd: str) -> str:
    lines = template.splitlines(True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("date:"):
            newline = "\n" if line.endswith("\n") else ""
            lines[i] = f"date: {yyyymmdd}{newline}"
            return "".join(lines)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] = lines[-1] + "\n"
    lines.append(f"\ndate: {yyyymmdd}\n")
    return "".join(lines)


def _set_grade_line(template: str, grade_value: str) -> str:
    lines = template.splitlines(True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("grade:") or stripped.startswith("# grade:"):
            newline = "\n" if line.endswith("\n") else ""
            lines[i] = f"grade: {grade_value}{newline}"
            return "".join(lines)

    for i, line in enumerate(lines):
        if "年级信息" in line:
            insert_at = i + 1
            newline = "\n" if (insert_at == 0 or lines[insert_at - 1].endswith("\n")) else "\n"
            lines.insert(insert_at, f"{newline}grade: {grade_value}\n")
            return "".join(lines)

    if lines and not lines[-1].endswith("\n"):
        lines[-1] = lines[-1] + "\n"
    lines.append(f"\ngrade: {grade_value}\n")
    return "".join(lines)


def _append_user_content(base: str, user_text: str) -> str:
    user_text = _extract_flashcard_text(user_text)
    user_text = user_text.rstrip()
    if not user_text:
        return base if base.endswith("\n") else base + "\n"
    if not base.endswith("\n"):
        base += "\n"
    return base + "\n" + user_text + "\n"


def _strip_flashcards_section_content(template: str) -> str:
    """Keep the first '# 闪卡内容' line, but remove any existing content after it."""
    lines = template.splitlines(True)
    for i, line in enumerate(lines):
        if "闪卡内容" in line:
            kept = lines[: i + 1]
            if kept and not kept[-1].endswith("\n"):
                kept[-1] = kept[-1] + "\n"
            return "".join(kept)
    return template


def _extract_flashcard_text(user_text: str) -> str:
    """Normalize pasted content so the generated config only contains flashcard lines."""
    if user_text is None:
        return ""

    lines = user_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    header_idxs = []
    for i, line in enumerate(lines):
        if "闪卡内容" in line or "闪卡信息" in line:
            header_idxs.append(i)
    if header_idxs:
        lines = lines[header_idxs[-1] + 1 :]

    cleaned = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("```"):
            continue
        if s.startswith("#"):
            continue
        if s.lower().startswith("date:") or s.lower().startswith("grade:"):
            continue
        if "|" in s:
            cleaned.append(s)

    return "\n".join(cleaned).strip()


def _resolve_person(person: str) -> dict:
    person_upper = person.upper()
    person_dir = os.path.join(BASE_DIR, person_upper)

    template_txt = os.path.join(person_dir, "template.txt")
    config_dir = os.path.join(person_dir, "config")

    if not os.path.exists(template_txt):
        fallback = os.path.join(person_dir, "config.txt")
        if os.path.exists(fallback):
            template_txt = fallback

    return {
        "key": person_upper,
        "person_dir": person_dir,
        "template_path": template_txt,
        "config_dir": config_dir,
        "filename_prefix": person_lower(person_upper),
    }


def person_lower(s: str) -> str:
    return s.lower()


# ==================== Modern Styled Widgets ====================

class ModernButton(tk.Canvas):
    """A modern button with hover effects and custom styling."""

    def __init__(self, parent, text, command=None, bg_color=Colors.ACCENT_PRIMARY,
                 text_color="white", width=120, height=38, corner_radius=8, **kwargs):
        super().__init__(parent, width=width, height=height,
                        highlightthickness=0, bg=parent.cget('bg'), **kwargs)
        self.command = command
        self.bg_color = bg_color
        self.hover_color = self._adjust_color(bg_color, -15)
        self.text_color = text_color
        self.corner_radius = corner_radius
        self.width = width
        self.height = height
        self._enabled = True
        self._click_pending = False  # 防止重复点击

        # Draw button background
        self._draw_button(bg_color)
        # Create text
        self.text_id = self.create_text(
            width / 2, height / 2,
            text=text,
            fill=text_color,
            font=("SF Pro Display", 13, "bold"),
            tags="text"
        )

        # Only bind to canvas, not to individual elements
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<ButtonRelease-1>", self._on_click_release)

    def _draw_button(self, color):
        """Draw the button with rounded corners using rectangle."""
        self.delete("button")
        w, h = self.width, self.height
        self.create_rectangle(
            0, 0, w, h,
            fill=color,
            outline="",
            tags="button"
        )
        self.tag_lower("button")

    def _adjust_color(self, hex_color, amount):
        """Darken or lighten a hex color."""
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = max(0, min(255, r + amount))
        g = max(0, min(255, g + amount))
        b = max(0, min(255, b + amount))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _on_enter(self, event):
        if self._enabled:
            self._draw_button(self.hover_color)

    def _on_leave(self, event):
        if self._enabled:
            self._draw_button(self.bg_color)

    def _on_click(self, event):
        # 只在按钮按下时记录状态，不执行命令
        pass

    def _on_click_release(self, event):
        # 在按钮释放时执行命令（标准的按钮行为）
        if self._enabled and self.command and not self._click_pending:
            # 检查鼠标是否还在按钮范围内
            if 0 <= event.x <= self.width and 0 <= event.y <= self.height:
                self._click_pending = True
                self.after(100, self._execute_command_and_reset)

    def _execute_command_and_reset(self):
        """Execute command and reset pending state."""
        if self.command:
            self.command()
        self._click_pending = False

    def set_enabled(self, enabled):
        """Enable or disable the button."""
        self._enabled = enabled
        if not enabled:
            self._draw_button(Colors.BG_SECONDARY)
            self.itemconfig(self.text_id, fill=Colors.TEXT_MUTED)
        else:
            self._draw_button(self.bg_color)
            self.itemconfig(self.text_id, fill=self.text_color)


class CardFrame(tk.Frame):
    """A frame with a card-like appearance."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=Colors.BG_CARD, **kwargs)
        self.config(
            relief="flat",
            borderwidth=0,
        )


class StyledLabel(tk.Label):
    """A label with modern styling."""

    def __init__(self, parent, text, size=12, weight="normal",
                 color=Colors.TEXT_PRIMARY, bg=Colors.BG_PRIMARY, **kwargs):
        font_spec = ("SF Pro Display", size, weight)
        super().__init__(parent, text=text, font=font_spec,
                        fg=color, bg=bg, **kwargs)


# ==================== Main GUI Application ====================

class FlashcardsGUI:
    """Professional Flashcards Publisher GUI."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self._setup_window()
        self._setup_styles()
        self._create_widgets()

    def _setup_window(self):
        """Configure the main window."""
        self.root.title("✨ Flashcards Publisher")
        self.root.geometry("960x720")
        self.root.configure(bg=Colors.BG_PRIMARY)
        self.root.minsize(800, 600)

        # Set window icon (using emoji as fallback)
        try:
            # Try to use a modern window appearance on macOS
            if sys.platform == "darwin":
                self.root.tk.call("tk", "scaling", 1.0)
        except:
            pass

    def _setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use("clam")

        # Custom combobox style
        style.configure("Modern.TCombobox",
                       fieldbackground=Colors.BG_CARD,
                       background=Colors.BG_CARD,
                       foreground=Colors.TEXT_PRIMARY,
                       borderwidth=1,
                        relief="flat")
        style.map("Modern.TCombobox",
                 background=[("readonly", Colors.BG_CARD)],
                 bordercolor=[("readonly", Colors.BORDER)])

    def _create_widgets(self):
        """Create all GUI widgets."""
        self._create_header()
        self._create_content_area()
        self._create_footer()

    def _create_header(self):
        """Create the header section."""
        header = tk.Frame(self.root, bg=Colors.ACCENT_PRIMARY, height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # App title
        title_frame = tk.Frame(header, bg=Colors.ACCENT_PRIMARY)
        title_frame.pack(expand=True)

        StyledLabel(
            title_frame,
            text="Flashcards Publisher",
            size=24,
            weight="bold",
            color="white",
            bg=Colors.ACCENT_PRIMARY
        ).pack(side=tk.LEFT, padx=(20, 10))

        StyledLabel(
            title_frame,
            text="Create and publish beautiful flashcards",
            size=13,
            weight="normal",
            color="#e3f2fd",
            bg=Colors.ACCENT_PRIMARY
        ).pack(side=tk.LEFT, padx=10)

    def _create_content_area(self):
        """Create the main content area."""
        content = tk.Frame(self.root, bg=Colors.BG_PRIMARY)
        content.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        # Mode selector bar
        self._create_mode_bar(content)

        # Input card
        input_card = self._create_input_card(content)
        input_card.pack(fill=tk.BOTH, expand=True)

        # Controls section
        controls_card = self._create_controls_card(content)
        controls_card.pack(fill=tk.X, pady=(16, 0))

    def _create_mode_bar(self, parent):
        """Create the mode selector bar."""
        bar = tk.Frame(parent, bg=Colors.BG_PRIMARY)
        bar.pack(fill=tk.X, pady=(0, 12))

        self.mode_var = tk.StringVar(value="english")

        modes = [
            ("english", "📝 English Flashcards", Colors.ACCENT_PRIMARY),
            ("wenyanwen", "📜 Wenyanwen 文言文", Colors.ACCENT_WENYANWEN),
            ("passages", "📖 English Passages", Colors.ACCENT_PASSAGE),
        ]

        self.mode_buttons = {}
        for mode_key, label, color in modes:
            btn = ModernButton(
                bar,
                text=label,
                command=lambda m=mode_key: self._switch_mode(m),
                bg_color=color,
                width=200,
                height=36,
            )
            btn.pack(side=tk.LEFT, padx=(0, 8))
            self.mode_buttons[mode_key] = btn

    def _switch_mode(self, mode: str) -> None:
        """Switch between modes and show/hide appropriate controls."""
        self.mode_var.set(mode)

        # Highlight active mode button, dim others
        for key, btn in self.mode_buttons.items():
            if key == mode:
                btn._draw_button(btn.bg_color)
                btn.itemconfig(btn.text_id, fill=btn.text_color)
            else:
                btn._draw_button(Colors.BG_SECONDARY)
                btn.itemconfig(btn.text_id, fill=Colors.TEXT_MUTED)

        # Show/hide English-only controls
        english_only = [self.unit_label, self.unit_combo, self.lucas_btn, self.lucy_btn]
        for widget in english_only:
            if mode == "english":
                widget.pack()
            else:
                widget.pack_forget()

        # Show/hide passage controls
        if mode == "wenyanwen":
            self.passage_title_frame.pack(fill=tk.X, pady=(0, 8), before=self.left_section)
            self.grade_label.pack(side=tk.LEFT, padx=(0, 4))
            self.grade_menu.pack(side=tk.LEFT, padx=(0, 12))
            self.author_label.pack(side=tk.LEFT, padx=(0, 4))
            self.author_entry.pack(side=tk.LEFT, padx=(0, 12))
            self.title_label.pack(side=tk.LEFT, padx=(0, 4))
            self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.publish_wenyanwen_btn.pack(side=tk.RIGHT)
            self.publish_passage_btn.pack_forget()
        elif mode == "passages":
            self.passage_title_frame.pack(fill=tk.X, pady=(0, 8), before=self.left_section)
            self.grade_label.pack(side=tk.LEFT, padx=(0, 4))
            self.grade_menu.pack(side=tk.LEFT, padx=(0, 12))
            self.author_label.pack_forget()
            self.author_entry.pack_forget()
            self.title_label.pack(side=tk.LEFT, padx=(0, 4))
            self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.publish_wenyanwen_btn.pack_forget()
            self.publish_passage_btn.pack(side=tk.RIGHT)
        else:
            self.passage_title_frame.pack_forget()

        # Update placeholder text
        if mode == "english":
            self.placeholder = "Enter your flashcards here...\n\nExample:\napple | 苹果\nbanana | 香蕉\norange | 橙子"
        elif mode == "wenyanwen":
            self.placeholder = "粘贴文言文内容...\n\n例如:\n弈秋，通国之善弈者也。使弈秋诲二人弈..."
        else:
            self.placeholder = "Paste the English passage here...\n\nExample:\nI want to recommend Paul for our school Music Club..."

        if not self.has_content:
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", self.placeholder)
            self.text.configure(fg=Colors.TEXT_MUTED)

    def _create_input_card(self, parent):
        """Create the input text area card."""
        card = CardFrame(parent, padx=20, pady=16)
        card.pack(fill=tk.BOTH, expand=True)

        # Card header
        header = tk.Frame(card, bg=Colors.BG_CARD)
        header.pack(fill=tk.X, pady=(0, 12))

        StyledLabel(
            header,
            text="📝 Flashcard Content",
            size=16,
            weight="bold",
            bg=Colors.BG_CARD
        ).pack(side=tk.LEFT)

        StyledLabel(
            header,
            text="Paste flashcard lines as: English | 中文",
            size=12,
            weight="normal",
            color=Colors.TEXT_MUTED,
            bg=Colors.BG_CARD
        ).pack(side=tk.RIGHT)

        # Text area with border
        text_container = tk.Frame(card, bg=Colors.BG_CARD)
        text_container.pack(fill=tk.BOTH, expand=True)

        # Create a border frame
        border_frame = tk.Frame(text_container, bg=Colors.BORDER, bd=0)
        border_frame.pack(fill=tk.BOTH, expand=True)

        # Inner frame with white background
        inner_frame = tk.Frame(border_frame, bg="white", bd=0)
        inner_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Scrolled text
        self.text = ScrolledText(
            inner_frame,
            wrap=tk.WORD,
            font=("Menlo", 13),
            bg="white",
            fg=Colors.TEXT_PRIMARY,
            relief="flat",
            borderwidth=0,
            insertbackground=Colors.ACCENT_PRIMARY,
            selectbackground=Colors.ACCENT_PRIMARY,
            selectforeground="white"
        )
        self.text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Placeholder text
        self.placeholder = "Enter your flashcards here...\n\nExample:\napple | 苹果\nbanana | 香蕉\norange | 橙子"
        self.text.insert("1.0", self.placeholder)
        self.text.configure(fg=Colors.TEXT_MUTED)

        self.text.bind("<FocusIn>", self._on_text_focus)
        self.text.bind("<FocusOut>", self._on_text_focus_out)
        self.has_content = False

        return card

    def _on_text_focus(self, event):
        """Handle text focus in."""
        if not self.has_content:
            self.text.delete("1.0", tk.END)
            self.text.configure(fg=Colors.TEXT_PRIMARY)
            self.has_content = True

    def _on_text_focus_out(self, event):
        """Handle text focus out."""
        content = self.text.get("1.0", tk.END).strip()
        if not content:
            self.text.insert("1.0", self.placeholder)
            self.text.configure(fg=Colors.TEXT_MUTED)
            self.has_content = False

    def _create_controls_card(self, parent):
        """Create the controls card."""
        card = CardFrame(parent, padx=24, pady=18)
        card.pack(fill=tk.X)

        # --- Passage title row (hidden by default) ---
        self.passage_title_frame = tk.Frame(card, bg=Colors.BG_CARD)

        self.grade_label = StyledLabel(
            self.passage_title_frame, text="Grade:", size=12, weight="bold",
            bg=Colors.BG_CARD, color=Colors.TEXT_SECONDARY)
        self.passage_grade_var = tk.StringVar(value=DEFAULT_PASSAGE_GRADE)
        self.grade_menu = tk.OptionMenu(
            self.passage_title_frame,
            self.passage_grade_var,
            DEFAULT_PASSAGE_GRADE,
            *PASSAGE_GRADES,
        )
        self.grade_menu.config(
            font=("SF Pro Display", 12),
            bg=Colors.BG_CARD,
            fg=Colors.TEXT_PRIMARY,
            activebackground=Colors.ACCENT_PRIMARY,
            activeforeground="white",
            bd=1,
            relief="solid",
            highlightthickness=0,
            padx=10,
            pady=3,
        )

        self.author_label = StyledLabel(
            self.passage_title_frame, text="Author:", size=12, weight="bold",
            bg=Colors.BG_CARD, color=Colors.TEXT_SECONDARY)
        self.author_entry = tk.Entry(
            self.passage_title_frame, font=("SF Pro Display", 13), width=12,
            bg=Colors.BG_PRIMARY, fg=Colors.TEXT_PRIMARY, relief="solid", bd=1)

        self.title_label = StyledLabel(
            self.passage_title_frame, text="Title:", size=12, weight="bold",
            bg=Colors.BG_CARD, color=Colors.TEXT_SECONDARY)
        self.title_entry = tk.Entry(
            self.passage_title_frame, font=("SF Pro Display", 13),
            bg=Colors.BG_PRIMARY, fg=Colors.TEXT_PRIMARY, relief="solid", bd=1)

        self.publish_wenyanwen_btn = ModernButton(
            self.passage_title_frame,
            text="📜 Publish 文言文",
            command=self.on_publish_wenyanwen,
            bg_color=Colors.ACCENT_WENYANWEN,
            width=160,
            height=42,
        )

        self.publish_passage_btn = ModernButton(
            self.passage_title_frame,
            text="📖 Publish Passage",
            command=self.on_publish_passage,
            bg_color=Colors.ACCENT_PASSAGE,
            width=160,
            height=42,
        )

        # --- English mode controls ---
        # Left section - Unit selection
        self.left_section = tk.Frame(card, bg=Colors.BG_CARD)
        self.left_section.pack(side=tk.LEFT, fill=tk.Y)

        self.unit_label = StyledLabel(
            self.left_section,
            text="📚 Unit",
            size=13,
            weight="bold",
            bg=Colors.BG_CARD
        )
        self.unit_label.pack(anchor="w", pady=(0, 8))

        self.unit_var = tk.StringVar(value="2")

        unit_menu = tk.OptionMenu(
            self.left_section,
            self.unit_var,
            "2",
            *LUCAS_UNITS,
            command=self._on_unit_selected
        )
        unit_menu.config(
            font=("SF Pro Display", 12),
            bg=Colors.BG_CARD,
            fg=Colors.TEXT_PRIMARY,
            activebackground=Colors.ACCENT_PRIMARY,
            activeforeground="white",
            bd=1,
            relief="solid",
            highlightthickness=0,
            padx=15,
            pady=3
        )
        unit_menu.pack(pady=2, ipadx=5, ipady=2)
        self.unit_combo = unit_menu

        # Right section - Action buttons
        right_section = tk.Frame(card, bg=Colors.BG_CARD)
        right_section.pack(side=tk.RIGHT)

        buttons_frame = tk.Frame(right_section, bg=Colors.BG_CARD)
        buttons_frame.pack()

        self.lucas_btn = ModernButton(
            buttons_frame,
            text="👦 Generate for Lucas",
            command=lambda: self.on_publish("LUCAS"),
            bg_color=Colors.ACCENT_LUCAS,
            width=180,
            height=42
        )
        self.lucas_btn.pack(side=tk.LEFT, padx=(0, 12))

        self.lucy_btn = ModernButton(
            buttons_frame,
            text="👧 Generate for Lucy",
            command=lambda: self.on_publish("LUCY"),
            bg_color=Colors.ACCENT_LUCY,
            width=180,
            height=42
        )
        self.lucy_btn.pack(side=tk.LEFT)

        return card

    def _on_unit_selected(self, value):
        """Handle unit selection from dropdown."""
        # OptionMenu command passes the selected value directly
        self.unit_var.set(value)

    def _create_footer(self):
        """Create the footer section."""
        footer = tk.Frame(self.root, bg=Colors.BG_PRIMARY, height=40)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(
            footer,
            textvariable=self.status_var,
            font=("SF Pro Display", 11),
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_PRIMARY
        )
        self.status_label.pack(side=tk.LEFT, padx=24)

        # Version info
        StyledLabel(
            footer,
            text="Flashcards Publisher v2.0",
            size=10,
            color=Colors.TEXT_MUTED,
            bg=Colors.BG_PRIMARY
        ).pack(side=tk.RIGHT, padx=24)

    def _set_status(self, message, color=Colors.TEXT_MUTED):
        """Update the status bar."""
        self.status_var.set(message)
        self.status_label.config(fg=color)

    def on_publish(self, person: str) -> None:
        """Handle the publish action for a person."""
        info = _resolve_person(person)
        template_path = info["template_path"]
        if not template_path or not os.path.exists(template_path):
            messagebox.showerror(
                "Missing Template",
                f"Template not found for {person}.\n\nExpected location:\n{os.path.join(BASE_DIR, person, 'template.txt')}",
            )
            return

        user_text = self.text.get("1.0", tk.END)
        if not _extract_flashcard_text(user_text).strip():
            messagebox.showwarning(
                "No Flashcard Lines",
                "Please enter flashcard content first.\n\nFormat: English | 中文\n\nExample:\napple | 苹果\nbanana | 香蕉",
            )
            return

        unit_choice = self.unit_var.get().strip()
        if unit_choice not in LUCAS_UNITS:
            messagebox.showerror("Error", "Invalid unit selection.")
            return
        unit = _resolve_unit_from_ui(unit_choice)
        if not unit:
            return

        # Disable buttons during processing
        self._disable_all_buttons()
        self._set_status(f"Generating flashcards for {person}...", Colors.ACCENT_PRIMARY)
        self.root.update()

        try:
            if info["key"] == "LUCAS":
                grade_value = _grade_value(LUCAS_BASE_GRADE, unit)
                template = _read_text(template_path)
                template = _set_date_line(template, _today_yyyymmdd())
                template = _set_grade_line(template, grade_value)
                template = _strip_flashcards_section_content(template)
                final_text = _append_user_content(template, user_text)

                _ensure_dir(info["config_dir"])
                out_basename = _safe_filename_component(f"lucas_{grade_value}")
                out_name = f"{out_basename}_{_today_yyyymmdd()}.txt"
                out_path = os.path.join(info["config_dir"], out_name)
                _write_text(out_path, final_text)

                html_dir = os.path.join(info["person_dir"], "html")
                html_path = _run_v5_and_move_html(config_path=out_path, html_dir=html_dir)
            else:
                template = _read_text(template_path)
                base_grade = _infer_base_grade_from_template(template) or LUCY_BASE_GRADE
                grade_value = _grade_value(base_grade, unit)

                template = _set_date_line(template, _today_yyyymmdd())
                template = _set_grade_line(template, grade_value)
                template = _strip_flashcards_section_content(template)
                final_text = _append_user_content(template, user_text)

                _ensure_dir(info["config_dir"])
                out_basename = _safe_filename_component(f"lucy_{grade_value}")
                out_name = f"{out_basename}_{_today_yyyymmdd()}.txt"
                out_path = os.path.join(info["config_dir"], out_name)
                _write_text(out_path, final_text)

                html_dir = os.path.join(info["person_dir"], "html")
                html_path = _run_v5cat_and_move_html(config_path=out_path, html_dir=html_dir)

            self._set_status("Publishing to cloud...", Colors.ACCENT_PRIMARY)
            self.root.update()
            publish_name = _slugify(out_basename) + "_" + _today_yyyymmdd()
            published_url = _publish_html_to_github(html_path=html_path, publish_name=publish_name)

            # Update index.html with new link
            card_title = f"{out_basename}_{_today_yyyymmdd()}"
            _update_index_html(person=info["key"], card_title=card_title, published_url=published_url)

            # Publish updated index.html to GitHub Pages
            self._set_status("Updating index page...", Colors.ACCENT_PRIMARY)
            self.root.update()
            index_url = _publish_html_to_github(
                html_path=os.path.join(BASE_DIR, "index.html"),
            )
            print(f"✓ Index page updated: {index_url}")
        except Exception as e:
            self._set_status("Error occurred", Colors.ACCENT_LUCY)
            messagebox.showerror("Generation Failed", str(e))
            self._enable_all_buttons()
            return

        self._copy_to_clipboard(published_url)

        self._set_status("Done!", Colors.ACCENT_SUCCESS)
        self._enable_all_buttons()

        messagebox.showinfo(
            "✓ Generation Complete",
            f"Flashcards generated successfully for {person}!\n\n📎 Published URL:\n{published_url}\n\n(The link has been copied to your clipboard)",
        )

    def _disable_all_buttons(self):
        for btn in self.mode_buttons.values():
            btn.set_enabled(False)
        self.lucas_btn.set_enabled(False)
        self.lucy_btn.set_enabled(False)

    def _enable_all_buttons(self):
        mode = self.mode_var.get()
        for key, btn in self.mode_buttons.items():
            btn._enabled = True
            if key == mode:
                btn._draw_button(btn.bg_color)
                btn.itemconfig(btn.text_id, fill=btn.text_color)
            else:
                btn._draw_button(Colors.BG_SECONDARY)
                btn.itemconfig(btn.text_id, fill=Colors.TEXT_MUTED)
        self.lucas_btn.set_enabled(True)
        self.lucy_btn.set_enabled(True)

    def on_publish_wenyanwen(self) -> None:
        """Handle publishing a new wenyanwen passage."""
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("Missing Title", "Please enter a title for the passage.")
            return

        author = self.author_entry.get().strip()
        text = self.text.get("1.0", tk.END).strip()
        if not text or text == self.placeholder:
            messagebox.showwarning("No Content", "Please paste the 文言文 content first.")
            return

        grade = self.passage_grade_var.get()
        grade_slug = _slugify(grade)

        self._disable_all_buttons()
        self._set_status("Adding passage to wenyanwen.html...", Colors.ACCENT_PRIMARY)
        self.root.update()

        try:
            escaped_title = json.dumps(title)
            escaped_author = json.dumps(author)
            escaped_text = json.dumps(text)
            preset_js = f"{{\n        title: {escaped_title},\n        author: {escaped_author},\n        text: {escaped_text}\n    }}"

            # Create grade-specific file if it doesn't exist
            _ensure_dir(os.path.join(BASE_DIR, "wenyanwen"))
            grade_filename = f"wenyanwen_{grade_slug}.html"
            grade_html_path = os.path.join(BASE_DIR, "wenyanwen", grade_filename)
            template_path = os.path.join(BASE_DIR, "wenyanwen", "wenyanwen.html")
            if not os.path.exists(grade_html_path):
                shutil.copy2(template_path, grade_html_path)

            _inject_preset(grade_html_path, preset_js)

            self._set_status("Publishing to GitHub Pages...", Colors.ACCENT_PRIMARY)
            self.root.update()
            published_url = _publish_html_to_github(html_path=grade_html_path)

            # Update index.html with new grade card if needed
            _ensure_index_card("chinese", grade, grade_slug,
                               "chinese", "📖", "文言文背诵")
            _publish_html_to_github(html_path=os.path.join(BASE_DIR, "index.html"))
        except Exception as e:
            self._set_status("Error occurred", Colors.ACCENT_LUCY)
            messagebox.showerror("Publish Failed", str(e))
            self._enable_all_buttons()
            return

        self._copy_to_clipboard(published_url)
        self._set_status("Done!", Colors.ACCENT_SUCCESS)
        self._enable_all_buttons()
        messagebox.showinfo(
            "✓ Published",
            f"文言文 passage published!\n\n📎 URL:\n{published_url}\n\n(The link has been copied to your clipboard)",
        )

    def on_publish_passage(self) -> None:
        """Handle publishing a new English passage."""
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("Missing Title", "Please enter a title for the passage.")
            return

        text = self.text.get("1.0", tk.END).strip()
        if not text or text == self.placeholder:
            messagebox.showwarning("No Content", "Please paste the English passage first.")
            return

        grade = self.passage_grade_var.get()
        grade_slug = _slugify(grade)

        self._disable_all_buttons()
        self._set_status("Adding passage to english.html...", Colors.ACCENT_PRIMARY)
        self.root.update()

        try:
            escaped_title = json.dumps(title)
            escaped_text = json.dumps(text)
            preset_js = f"{{\n        title: {escaped_title},\n        text: {escaped_text}\n    }}"

            _ensure_dir(os.path.join(BASE_DIR, "english_passage"))
            grade_filename = f"english_{grade_slug}.html"
            grade_html_path = os.path.join(BASE_DIR, "english_passage", grade_filename)
            template_path = os.path.join(BASE_DIR, "english_passage", "english.html")
            if not os.path.exists(grade_html_path):
                shutil.copy2(template_path, grade_html_path)

            _inject_preset(grade_html_path, preset_js)

            self._set_status("Publishing to GitHub Pages...", Colors.ACCENT_PRIMARY)
            self.root.update()
            published_url = _publish_html_to_github(html_path=grade_html_path)

            # Update index.html with new grade card if needed
            _ensure_index_card("english", grade, grade_slug,
                               "english", "🔤", "英语课文背诵")
            _publish_html_to_github(html_path=os.path.join(BASE_DIR, "index.html"))
        except Exception as e:
            self._set_status("Error occurred", Colors.ACCENT_LUCY)
            messagebox.showerror("Publish Failed", str(e))
            self._enable_all_buttons()
            return

        self._copy_to_clipboard(published_url)
        self._set_status("Done!", Colors.ACCENT_SUCCESS)
        self._enable_all_buttons()
        messagebox.showinfo(
            "✓ Published",
            f"English passage published!\n\n📎 URL:\n{published_url}\n\n(The link has been copied to your clipboard)",
        )

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
        except Exception:
            try:
                subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=False)
            except Exception:
                pass

    def run(self) -> None:
        """Start the application."""
        self.root.mainloop()


def main() -> None:
    """Entry point for the application."""
    FlashcardsGUI().run()


if __name__ == "__main__":
    main()
