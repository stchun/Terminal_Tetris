#!/usr/bin/env python3
"""Terminal Tetris - Python curses implementation."""

import curses
import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime

# Board dimensions
BOARD_WIDTH = 10
BOARD_HEIGHT = 20

# Tetromino shapes
SHAPES = {
    'I': [[1, 1, 1, 1]],
    'O': [[1, 1],
          [1, 1]],
    'T': [[0, 1, 0],
          [1, 1, 1]],
    'S': [[0, 1, 1],
          [1, 1, 0]],
    'Z': [[1, 1, 0],
          [0, 1, 1]],
    'J': [[1, 0, 0],
          [1, 1, 1]],
    'L': [[0, 0, 1],
          [1, 1, 1]],
}

# Color pair IDs for each piece type
COLORS = {'I': 1, 'O': 2, 'T': 3, 'S': 4, 'Z': 5, 'J': 6, 'L': 7}

# Reverse lookup: color ID → piece name (for resetting hold piece rotation)
COLOR_TO_NAME = {v: k for k, v in COLORS.items()}

# Score per lines cleared (multiplied by level+1)
LINE_SCORES = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}

# Fall interval in seconds per level
FALL_SPEEDS = [0.80, 0.72, 0.63, 0.55, 0.47, 0.38, 0.30, 0.22, 0.13, 0.10, 0.08]

# Cell display size in terminal characters
CELL_W = 4   # columns per board cell
CELL_H = 2   # rows    per board cell

LEFT_W = 18  # width reserved for the left (Next) panel

HOLD_KEY = ord('f')   # F — Hold 키

SCORE_FILE = os.path.expanduser("~/.tetris_scores.json")


# ---------------------------------------------------------------------------
# Score persistence
# ---------------------------------------------------------------------------

def load_scores():
    """Load score list from JSON file. Returns list of dicts."""
    try:
        with open(SCORE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_score(score, level, lines, name=""):
    """Append current game result and keep top 50 entries."""
    scores = load_scores()
    scores.append({
        "name": name.strip() or "---",
        "score": score,
        "level": level,
        "lines": lines,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    scores.sort(key=lambda x: x["score"], reverse=True)
    with open(SCORE_FILE, 'w') as f:
        json.dump(scores[:50], f, indent=2)


def show_leaderboard(stdscr, highlight_score=None):
    """Display Top-10 leaderboard. Returns when any key is pressed."""
    scores = load_scores()[:10]
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    # Panel dimensions
    inner_w = 53   # inner content width (includes Name column)
    border   = "+" + "-" * inner_w + "+"
    rows = []
    rows.append(border)
    rows.append("|" + " TOP 10 LEADERBOARD ".center(inner_w) + "|")
    rows.append(border)
    rows.append("|" + f"{'Rank':<6}{'Name':<12}{'Score':>9}{'Level':>7}{'Lines':>7}  {'Date':<10}" + "|")
    rows.append(border)
    for i in range(10):
        if i < len(scores):
            e = scores[i]
            name = e.get('name', '---')[:10]
            line = f"  {i+1:<4}{name:<12}{e['score']:>9}{e['level']:>7}{e['lines']:>7}  {e['date'][:10]:<10}"
        else:
            line = f"  {i+1:<4}{'---':<12}{'---':>9}{'---':>7}{'---':>7}  {'---':<10}"
        rows.append("|" + line + "|")
    rows.append(border)
    rows.append("|" + " Press any key to return ".center(inner_w) + "|")
    rows.append(border)

    panel_h = len(rows)
    panel_w = inner_w + 2
    sy = max(0, (h - panel_h) // 2)
    sx = max(0, (w - panel_w) // 2)

    for r_i, row_text in enumerate(rows):
        # Highlight data rows that match the current game score
        is_score_row = (5 <= r_i <= 14) and highlight_score is not None
        score_idx = r_i - 5
        if is_score_row and score_idx < len(scores) and scores[score_idx]["score"] == highlight_score:
            attr = curses.A_BOLD | curses.A_REVERSE
        elif r_i in (0, 2, 4, panel_h - 2):
            attr = curses.A_BOLD
        else:
            attr = 0
        try:
            stdscr.addstr(sy + r_i, sx, row_text, attr)
        except curses.error:
            pass

    stdscr.refresh()
    stdscr.nodelay(False)
    stdscr.getch()
    stdscr.nodelay(True)


def input_name(stdscr, score):
    """Show name-input overlay after game over. Returns the entered name."""
    MAX_LEN = 10
    chars = []
    h, w = stdscr.getmaxyx()

    iw = 30   # inner content width
    bw = iw + 2
    bh = 8
    sy = max(0, (h - bh) // 2)
    sx = max(0, (w - bw) // 2)

    try:
        curses.curs_set(1)
    except curses.error:
        pass
    stdscr.nodelay(False)

    while True:
        stdscr.erase()
        name_disp = "".join(chars)
        # Name field: 10 chars wide, padded with spaces
        field = (name_disp + " " * MAX_LEN)[:MAX_LEN]
        trailing = " " * (iw - MAX_LEN - 2)

        def put(r, text, attr=0):
            try:
                stdscr.addstr(sy + r, sx, text[:bw], attr)
            except curses.error:
                pass

        sep = "+" + "-" * iw + "+"
        put(0, sep, curses.A_BOLD)
        put(1, "|" + "  GAME OVER".center(iw) + "|", curses.A_BOLD)
        put(2, "|" + f"  Score: {score}".ljust(iw) + "|")
        put(3, "|" + "-" * iw + "|", curses.A_BOLD)
        put(4, "|" + "  Enter your name:".ljust(iw) + "|")
        put(5, "|  " + field + trailing + "|", curses.A_UNDERLINE)
        put(6, "|" + "  Enter:OK  ESC:Skip".ljust(iw) + "|", curses.A_DIM)
        put(7, sep, curses.A_BOLD)

        # Position cursor at end of typed name
        try:
            stdscr.move(sy + 5, min(sx + 2 + len(chars), sx + 2 + MAX_LEN - 1))
        except curses.error:
            pass
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            break
        elif key == 27:           # ESC → skip, empty name
            chars = []
            break
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if chars:
                chars.pop()
        elif 32 <= key <= 126 and len(chars) < MAX_LEN:
            chars.append(chr(key))

    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.nodelay(True)
    return "".join(chars)


def rotate_cw(shape):
    """Rotate a shape 90 degrees clockwise."""
    return [list(row) for row in zip(*shape[::-1])]


def create_board():
    return [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]


def is_valid(board, shape, x, y):
    """Return True if the piece fits at (x, y) without going out of bounds or overlapping."""
    for row_i, row in enumerate(shape):
        for col_i, cell in enumerate(row):
            if cell:
                nx, ny = x + col_i, y + row_i
                if nx < 0 or nx >= BOARD_WIDTH or ny >= BOARD_HEIGHT:
                    return False
                if ny >= 0 and board[ny][nx]:
                    return False
    return True


def lock_piece(board, shape, x, y, color):
    """Stamp a piece onto the board."""
    for row_i, row in enumerate(shape):
        for col_i, cell in enumerate(row):
            if cell and y + row_i >= 0:
                board[y + row_i][x + col_i] = color


def clear_lines(board):
    """Remove full rows and return updated board + count of cleared lines."""
    kept = [row for row in board if not all(row)]
    cleared = BOARD_HEIGHT - len(kept)
    new_board = [[0] * BOARD_WIDTH for _ in range(cleared)] + kept
    return new_board, cleared


def get_fall_speed(level):
    return FALL_SPEEDS[min(level, len(FALL_SPEEDS) - 1)]


_bag = []

def random_piece():
    """Return next piece using 7-bag randomizer."""
    global _bag
    if not _bag:
        _bag = list(SHAPES.keys())
        random.shuffle(_bag)
    name = _bag.pop()
    return [row[:] for row in SHAPES[name]], COLORS[name]


def original_piece(color):
    """Return the original (unrotated) shape for a given color ID."""
    name = COLOR_TO_NAME[color]
    return [row[:] for row in SHAPES[name]], color


@dataclass
class GameState:
    board: list
    piece: tuple
    next_piece: tuple
    hold_piece: object
    hold_used: bool
    px: int
    py: int
    score: int
    level: int
    total_lines: int
    paused: bool
    last_fall: float
    game_over: bool = False


def renderer(stdscr, state):
    board, piece, px, py = state.board, state.piece, state.px, state.py
    next_piece, hold_piece, hold_used = state.next_piece, state.hold_piece, state.hold_used
    score, level, lines = state.score, state.level, state.total_lines
    paused, game_over = state.paused, state.game_over

    stdscr.erase()
    h, w = stdscr.getmaxyx()

    shape, color = piece
    next_shape, next_color = next_piece

    # Track terminal size issues — display warning if any rendering operation fails
    render_errors = []  # list of error description strings

    board_pixel_w = BOARD_WIDTH * CELL_W
    board_pixel_h = BOARD_HEIGHT * CELL_H

    # Position board accounting for left (Next) and right (Hold/stats) panels
    bx = max(LEFT_W + 2, (w - board_pixel_w - 20 - LEFT_W) // 2 + LEFT_W)
    by = max(1, (h - board_pixel_h - 2) // 2)

    # Left panel x position
    lx = bx - LEFT_W

    def _draw_safe(r, c, ch, attr=0):
        """Draw a single character; record error if terminal is too small."""
        try:
            stdscr.addch(r, c, ch)
        except curses.error:
            render_errors.append("terminal_too_small")

    def _draw_str_safe(y, x, text, attr=0):
        """Draw a string; record error if terminal is too small."""
        try:
            stdscr.addstr(y, x, text, attr)
        except curses.error:
            render_errors.append("terminal_too_small")

    # --- Compute ghost piece position ---
    ghost_y = py
    while is_valid(board, shape, px, ghost_y + 1):
        ghost_y += 1

    # --- Draw border ---
    for r in range(board_pixel_h + 2):
        _draw_safe(by + r, bx, '|')
        _draw_safe(by + r, bx + board_pixel_w + 1, '|')
    for c in range(board_pixel_w + 2):
        _draw_str_safe(by, bx + c, '-')
        _draw_str_safe(by + board_pixel_h + 1, bx + c, '-')
    for corner in [(by, bx), (by, bx + board_pixel_w + 1),
                   (by + board_pixel_h + 1, bx), (by + board_pixel_h + 1, bx + board_pixel_w + 1)]:
        _draw_safe(corner[0], corner[1], '+')

    # --- Draw locked cells ---
    for row_i, row in enumerate(board):
        for col_i, cell in enumerate(row):
            sx = bx + 1 + col_i * CELL_W
            for h_i in range(CELL_H):
                sy = by + 1 + row_i * CELL_H + h_i
                if cell:
                    _draw_str_safe(sy, sx, '    ', curses.color_pair(cell))
                else:
                    _draw_str_safe(sy, sx, '    ')

    # --- Draw ghost piece ---
    if ghost_y != py:
        for row_i, row in enumerate(shape):
            for col_i, cell in enumerate(row):
                if cell:
                    sx = bx + 1 + (px + col_i) * CELL_W
                    for h_i in range(CELL_H):
                        sy = by + 1 + (ghost_y + row_i) * CELL_H + h_i
                        if by < sy <= by + board_pixel_h:
                            _draw_str_safe(sy, sx, '::::', curses.A_DIM)

    # --- Draw current piece (on top of ghost) ---
    for row_i, row in enumerate(shape):
        for col_i, cell in enumerate(row):
            if cell:
                sx = bx + 1 + (px + col_i) * CELL_W
                for h_i in range(CELL_H):
                    sy = by + 1 + (py + row_i) * CELL_H + h_i
                    if by < sy <= by + board_pixel_h:
                        _draw_str_safe(sy, sx, '    ', curses.color_pair(color))

    # --- Left panel: Hold piece ---
    _draw_str_safe(by, lx, 'Hold:', curses.A_BOLD)
    if hold_piece is not None:
        hold_shape, hold_color = hold_piece
        piece_attr = curses.color_pair(hold_color) | (curses.A_DIM if hold_used else 0)
        for row_i, row in enumerate(hold_shape):
            for col_i, cell in enumerate(row):
                if cell:
                    for h_i in range(CELL_H):
                        _draw_str_safe(by + 2 + row_i * CELL_H + h_i, lx + col_i * CELL_W,
                                      '    ', piece_attr)
    else:
        _draw_str_safe(by + 2, lx, 'EMPTY')

    # --- Right panel: stats + Next ---
    ix = bx + board_pixel_w + 4
    iy = by

    def info(row, text, bold=False):
        attr = curses.A_BOLD if bold else 0
        _draw_str_safe(iy + row, ix, text, attr)

    info(0,  'TETRIS', bold=True)
    info(2,  'Score:')
    info(3,  str(score))
    info(5,  'Level:')
    info(6,  str(level))
    info(8,  'Lines:')
    info(9,  str(lines))
    info(11, 'Next:')

    for row_i, row in enumerate(next_shape):
        for col_i, cell in enumerate(row):
            if cell:
                for h_i in range(CELL_H):
                    _draw_str_safe(iy + 13 + row_i * CELL_H + h_i,
                                  ix + col_i * CELL_W, '    ', curses.color_pair(next_color))

    info(19, 'Controls:', bold=True)
    info(20, '←→  Move')
    info(21, '↑    Rotate')
    info(22, '↓    Soft drop')
    info(23, 'Spc  Hard drop')
    info(24, 'F    Hold')
    info(25, 'P    Pause')
    info(26, 'L    Leaderboard')
    info(27, 'R    Restart')
    info(28, 'Q    Quit')

    # --- Terminal size warning overlay ---
    if render_errors:
        msg = '  터미널 크기가 충분하지 않습니다. Q:종료 R:재시작  '
        try:
            stdscr.addstr(by + board_pixel_h // 2, bx + (board_pixel_w + 2 - len(msg)) // 2,
                          msg, curses.A_REVERSE | curses.A_BOLD)
        except curses.error:
            pass

    # --- Paused overlay ---
    if paused:
        msg = '  PAUSED  '
        try:
            stdscr.addstr(by + board_pixel_h // 2, bx + (board_pixel_w + 2 - len(msg)) // 2,
                          msg, curses.A_REVERSE | curses.A_BOLD)
        except curses.error:
            pass

    # --- Game Over overlay ---
    if game_over:
        overlay_msgs = ['  GAME OVER  ', f'  Score: {score}  ', '  R:Restart  L:Board  Q:Quit  ']
        mid_y = by + board_pixel_h // 2 - 1
        for i, msg in enumerate(overlay_msgs):
            try:
                stdscr.addstr(mid_y + i, bx + (board_pixel_w + 2 - len(msg)) // 2,
                              msg, curses.A_REVERSE | curses.A_BOLD)
            except curses.error:
                pass

    stdscr.refresh()


def init_colors():
    """Initialise curses color pairs (done once at startup)."""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN,    curses.COLOR_CYAN)      # I
    curses.init_pair(2, curses.COLOR_YELLOW,  curses.COLOR_YELLOW)    # O
    curses.init_pair(3, curses.COLOR_MAGENTA, curses.COLOR_MAGENTA)   # T
    curses.init_pair(4, curses.COLOR_GREEN,   curses.COLOR_GREEN)     # S
    curses.init_pair(5, curses.COLOR_RED,     curses.COLOR_RED)       # Z
    curses.init_pair(6, curses.COLOR_BLUE,    curses.COLOR_BLUE)      # J
    curses.init_pair(7, curses.COLOR_WHITE,   curses.COLOR_WHITE)     # L


def new_game_state():
    """Build a fresh GameState for the start of a game session."""
    global _bag
    _bag = []  # reset 7-bag on each game start
    piece = random_piece()
    next_piece = random_piece()
    shape, _ = piece
    px = BOARD_WIDTH // 2 - len(shape[0]) // 2

    return GameState(
        board=create_board(),
        piece=piece,
        next_piece=next_piece,
        hold_piece=None,
        hold_used=False,
        px=px,
        py=0,
        score=0,
        level=0,
        total_lines=0,
        paused=False,
        last_fall=time.time(),
    )


def handle_game_over(stdscr, state):
    """Save the score, show the game-over overlay, and wait for R/L/Q. Returns 'quit' or 'restart'."""
    name = input_name(stdscr, state.score)
    save_score(state.score, state.level, state.total_lines, name)
    state.game_over = True
    stdscr.nodelay(False)
    result = None
    while result is None:
        renderer(stdscr, state)
        k = stdscr.getch()
        if k in (ord('q'), ord('Q')):
            result = 'quit'
        elif k in (ord('r'), ord('R')):
            result = 'restart'
        elif k in (ord('l'), ord('L')):
            show_leaderboard(stdscr, highlight_score=state.score)
    return result


def handle_input(stdscr, state, key, now):
    """Process a single key press, mutating state in place. Returns 'quit'/'restart'/None."""
    if key in (ord('q'), ord('Q')):
        return 'quit'

    if key in (ord('p'), ord('P')):
        state.paused = not state.paused
        if not state.paused:
            state.last_fall = time.time()

    if state.paused:
        return None

    if key in (ord('l'), ord('L')):
        show_leaderboard(stdscr)
        state.last_fall = time.time()  # avoid sudden drop after return

    if key in (ord('r'), ord('R')):
        return 'restart'

    shape, color = state.piece

    if key == curses.KEY_LEFT:
        if is_valid(state.board, shape, state.px - 1, state.py):
            state.px -= 1
    elif key == curses.KEY_RIGHT:
        if is_valid(state.board, shape, state.px + 1, state.py):
            state.px += 1
    elif key == curses.KEY_UP:
        rotated = rotate_cw(shape)
        # Try wall kicks: 0, -1, +1, -2, +2
        for kick in (0, -1, 1, -2, 2):
            if is_valid(state.board, rotated, state.px + kick, state.py):
                state.piece = (rotated, color)
                state.px += kick
                break
    elif key == curses.KEY_DOWN:
        if is_valid(state.board, shape, state.px, state.py + 1):
            state.py += 1
            state.last_fall = now
            # Soft drop score: 1 point per cell moved down
            state.score += 1
    elif key == ord(' '):
        # Hard drop
        hard_drop_cells = 0
        while is_valid(state.board, shape, state.px, state.py + 1):
            state.py += 1
            hard_drop_cells += 1
        state.last_fall = 0  # force lock on next gravity tick
        # Hard drop score: 2 points per cell moved down
        state.score += hard_drop_cells * 2
    elif key == HOLD_KEY:
        # Hold: swap current piece with held piece (once per piece)
        if not state.hold_used:
            state.hold_used = True
            if state.hold_piece is None:
                state.hold_piece = original_piece(color)
                state.piece = state.next_piece
                state.next_piece = random_piece()
            else:
                new_hold = original_piece(color)
                state.piece = state.hold_piece
                state.hold_piece = new_hold
            shape, color = state.piece
            state.px = BOARD_WIDTH // 2 - len(shape[0]) // 2
            state.py = 0
            if not is_valid(state.board, shape, state.px, state.py):
                # Try once more with slight offset (board full → no room anywhere)
                shifted_ok = False
                for off in (-1, +1):
                    if is_valid(state.board, shape, state.px + off, state.py):
                        state.px += off
                        shifted_ok = True
                        break
                if not shifted_ok:
                    # Board full — show game over with retry option
                    return handle_game_over(stdscr, state)

    return None


def gravity_tick(stdscr, state, now):
    """Apply gravity: fall, lock, clear lines, spawn next piece. Returns 'quit'/'restart'/None."""
    shape, color = state.piece
    if now - state.last_fall < get_fall_speed(state.level):
        return None

    if is_valid(state.board, shape, state.px, state.py + 1):
        state.py += 1
    else:
        # Lock piece and spawn next
        lock_piece(state.board, shape, state.px, state.py, color)
        state.board, cleared = clear_lines(state.board)
        state.total_lines += cleared
        state.score += LINE_SCORES.get(cleared, 0) * (state.level + 1)
        state.level = state.total_lines // 10

        state.piece = state.next_piece
        state.next_piece = random_piece()
        shape, _ = state.piece
        state.px = BOARD_WIDTH // 2 - len(shape[0]) // 2
        state.py = 0
        state.hold_used = False  # reset hold availability for new piece

        if not is_valid(state.board, shape, state.px, state.py):
            return handle_game_over(stdscr, state)

    state.last_fall = now
    return None


def run_game(stdscr):
    """Play a single game session until the player quits or restarts. Returns 'quit' or 'restart'."""
    state = new_game_state()
    stdscr.nodelay(True)
    result = None

    while result is None:
        now = time.time()
        key = stdscr.getch()

        result = handle_input(stdscr, state, key, now)
        if result is not None:
            break

        if state.paused:
            renderer(stdscr, state)
            time.sleep(0.05)
            continue

        result = gravity_tick(stdscr, state, now)
        if result is not None:
            break

        renderer(stdscr, state)
        time.sleep(0.02)

    return result


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    init_colors()

    while True:
        result = run_game(stdscr)
        if result == 'quit':
            break
        # result == 'restart': loop continues with a fresh game


if __name__ == '__main__':
    curses.wrapper(main)
