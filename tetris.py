#!/usr/bin/env python3
"""Terminal Tetris - Python curses implementation."""

import curses
import json
import os
import random
import time
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


def random_piece():
    name = random.choice(list(SHAPES.keys()))
    return [row[:] for row in SHAPES[name]], COLORS[name]


def original_piece(color):
    """Return the original (unrotated) shape for a given color ID."""
    name = COLOR_TO_NAME[color]
    return [row[:] for row in SHAPES[name]], color


def draw(stdscr, board, piece, px, py, next_piece, hold_piece, hold_used, score, level, lines, paused, game_over=False):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    shape, color = piece
    next_shape, next_color = next_piece

    board_pixel_w = BOARD_WIDTH * CELL_W
    board_pixel_h = BOARD_HEIGHT * CELL_H

    # Position board accounting for left (Next) and right (Hold/stats) panels
    bx = max(LEFT_W + 2, (w - board_pixel_w - 20 - LEFT_W) // 2 + LEFT_W)
    by = max(1, (h - board_pixel_h - 2) // 2)

    # Left panel x position
    lx = bx - LEFT_W

    # --- Compute ghost piece position ---
    ghost_y = py
    while is_valid(board, shape, px, ghost_y + 1):
        ghost_y += 1

    # --- Draw border ---
    for r in range(board_pixel_h + 2):
        try:
            stdscr.addch(by + r, bx, '|')
            stdscr.addch(by + r, bx + board_pixel_w + 1, '|')
        except curses.error:
            pass
    for c in range(board_pixel_w + 2):
        try:
            stdscr.addch(by, bx + c, '-')
            stdscr.addch(by + board_pixel_h + 1, bx + c, '-')
        except curses.error:
            pass
    for corner in [(by, bx), (by, bx + board_pixel_w + 1),
                   (by + board_pixel_h + 1, bx), (by + board_pixel_h + 1, bx + board_pixel_w + 1)]:
        try:
            stdscr.addch(corner[0], corner[1], '+')
        except curses.error:
            pass

    # --- Draw locked cells ---
    for row_i, row in enumerate(board):
        for col_i, cell in enumerate(row):
            sx = bx + 1 + col_i * CELL_W
            for h_i in range(CELL_H):
                sy = by + 1 + row_i * CELL_H + h_i
                try:
                    if cell:
                        stdscr.addstr(sy, sx, '    ', curses.color_pair(cell))
                    else:
                        stdscr.addstr(sy, sx, '    ')
                except curses.error:
                    pass

    # --- Draw ghost piece ---
    if ghost_y != py:
        for row_i, row in enumerate(shape):
            for col_i, cell in enumerate(row):
                if cell:
                    sx = bx + 1 + (px + col_i) * CELL_W
                    for h_i in range(CELL_H):
                        sy = by + 1 + (ghost_y + row_i) * CELL_H + h_i
                        if by < sy <= by + board_pixel_h:
                            try:
                                stdscr.addstr(sy, sx, '::::', curses.A_DIM)
                            except curses.error:
                                pass

    # --- Draw current piece (on top of ghost) ---
    for row_i, row in enumerate(shape):
        for col_i, cell in enumerate(row):
            if cell:
                sx = bx + 1 + (px + col_i) * CELL_W
                for h_i in range(CELL_H):
                    sy = by + 1 + (py + row_i) * CELL_H + h_i
                    if by < sy <= by + board_pixel_h:
                        try:
                            stdscr.addstr(sy, sx, '    ', curses.color_pair(color))
                        except curses.error:
                            pass

    # --- Left panel: Hold piece ---
    try:
        stdscr.addstr(by, lx, 'Hold:', curses.A_BOLD)
    except curses.error:
        pass
    if hold_piece is not None:
        hold_shape, hold_color = hold_piece
        piece_attr = curses.color_pair(hold_color) | (curses.A_DIM if hold_used else 0)
        for row_i, row in enumerate(hold_shape):
            for col_i, cell in enumerate(row):
                if cell:
                    for h_i in range(CELL_H):
                        try:
                            stdscr.addstr(by + 2 + row_i * CELL_H + h_i, lx + col_i * CELL_W,
                                          '    ', piece_attr)
                        except curses.error:
                            pass
    else:
        try:
            stdscr.addstr(by + 2, lx, 'EMPTY')
        except curses.error:
            pass

    # --- Right panel: stats + Hold ---
    ix = bx + board_pixel_w + 4
    iy = by

    def info(row, text, bold=False):
        attr = curses.A_BOLD if bold else 0
        try:
            stdscr.addstr(iy + row, ix, text, attr)
        except curses.error:
            pass

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
                    try:
                        stdscr.addstr(iy + 13 + row_i * CELL_H + h_i,
                                      ix + col_i * CELL_W, '    ', curses.color_pair(next_color))
                    except curses.error:
                        pass

    info(19, 'Controls:', bold=True)
    info(20, '\u2190\u2192  Move')
    info(21, '\u2191    Rotate')
    info(22, '\u2193    Soft drop')
    info(23, 'Spc  Hard drop')
    info(24, 'F    Hold')
    info(25, 'P    Pause')
    info(26, 'L    Leaderboard')
    info(27, 'R    Restart')
    info(28, 'Q    Quit')

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


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)

    # Initialise colors (done once)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN,    curses.COLOR_CYAN)      # I
    curses.init_pair(2, curses.COLOR_YELLOW,  curses.COLOR_YELLOW)    # O
    curses.init_pair(3, curses.COLOR_MAGENTA, curses.COLOR_MAGENTA)   # T
    curses.init_pair(4, curses.COLOR_GREEN,   curses.COLOR_GREEN)     # S
    curses.init_pair(5, curses.COLOR_RED,     curses.COLOR_RED)       # Z
    curses.init_pair(6, curses.COLOR_BLUE,    curses.COLOR_BLUE)      # J
    curses.init_pair(7, curses.COLOR_WHITE,   curses.COLOR_WHITE)     # L

    while True:  # restart loop
        board = create_board()
        piece = random_piece()
        next_piece = random_piece()
        shape, color = piece
        px = BOARD_WIDTH // 2 - len(shape[0]) // 2
        py = 0

        score = 0
        level = 0
        total_lines = 0
        paused = False
        last_fall = time.time()
        hold_piece = None
        hold_used = False

        stdscr.nodelay(True)
        game_result = None  # 'quit' or 'restart'

        while game_result is None:
            now = time.time()
            key = stdscr.getch()

            # --- Quit ---
            if key in (ord('q'), ord('Q')):
                game_result = 'quit'
                break

            # --- Pause toggle ---
            if key in (ord('p'), ord('P')):
                paused = not paused
                if not paused:
                    last_fall = time.time()

            if paused:
                draw(stdscr, board, piece, px, py, next_piece, hold_piece, hold_used,
                     score, level, total_lines, paused=True)
                time.sleep(0.05)
                continue

            # --- Leaderboard (during play) ---
            if key in (ord('l'), ord('L')):
                show_leaderboard(stdscr)
                last_fall = time.time()  # avoid sudden drop after return

            shape, color = piece

            # --- Input: movement & rotation ---
            if key == curses.KEY_LEFT:
                if is_valid(board, shape, px - 1, py):
                    px -= 1
            elif key == curses.KEY_RIGHT:
                if is_valid(board, shape, px + 1, py):
                    px += 1
            elif key == curses.KEY_UP:
                rotated = rotate_cw(shape)
                # Try wall kicks: 0, -1, +1, -2, +2
                for kick in (0, -1, 1, -2, 2):
                    if is_valid(board, rotated, px + kick, py):
                        piece = (rotated, color)
                        shape = rotated
                        px += kick
                        break
            elif key == curses.KEY_DOWN:
                if is_valid(board, shape, px, py + 1):
                    py += 1
                    last_fall = now
            elif key == ord(' '):
                # Hard drop
                while is_valid(board, shape, px, py + 1):
                    py += 1
                last_fall = 0  # force lock on next gravity tick
            elif key == HOLD_KEY:
                # Hold: swap current piece with held piece (once per piece)
                if not hold_used:
                    hold_used = True
                    if hold_piece is None:
                        hold_piece = original_piece(color)
                        piece = next_piece
                        next_piece = random_piece()
                    else:
                        new_hold = original_piece(color)
                        piece = hold_piece
                        hold_piece = new_hold
                    shape, color = piece
                    px = BOARD_WIDTH // 2 - len(shape[0]) // 2
                    py = 0
                    if not is_valid(board, shape, px, py):
                        name = input_name(stdscr, score)
                        save_score(score, level, total_lines, name)
                        stdscr.nodelay(False)
                        while True:
                            draw(stdscr, board, piece, px, py, next_piece, hold_piece, hold_used,
                                 score, level, total_lines, paused=False, game_over=True)
                            k = stdscr.getch()
                            if k in (ord('q'), ord('Q')):
                                game_result = 'quit'
                                break
                            if k in (ord('r'), ord('R')):
                                game_result = 'restart'
                                break
                            if k in (ord('l'), ord('L')):
                                show_leaderboard(stdscr, highlight_score=score)
                        break

            # --- Gravity ---
            if now - last_fall >= get_fall_speed(level):
                if is_valid(board, shape, px, py + 1):
                    py += 1
                else:
                    # Lock piece and spawn next
                    lock_piece(board, shape, px, py, color)
                    board, cleared = clear_lines(board)
                    total_lines += cleared
                    score += LINE_SCORES.get(cleared, 0) * (level + 1)
                    level = total_lines // 10

                    piece = next_piece
                    next_piece = random_piece()
                    shape, color = piece
                    px = BOARD_WIDTH // 2 - len(shape[0]) // 2
                    py = 0
                    hold_used = False  # reset hold availability for new piece

                    if not is_valid(board, shape, px, py):
                        name = input_name(stdscr, score)
                        save_score(score, level, total_lines, name)
                        stdscr.nodelay(False)
                        while True:
                            draw(stdscr, board, piece, px, py, next_piece, hold_piece, hold_used,
                                 score, level, total_lines, paused=False, game_over=True)
                            k = stdscr.getch()
                            if k in (ord('q'), ord('Q')):
                                game_result = 'quit'
                                break
                            if k in (ord('r'), ord('R')):
                                game_result = 'restart'
                                break
                            if k in (ord('l'), ord('L')):
                                show_leaderboard(stdscr, highlight_score=score)
                        break
                last_fall = now

            draw(stdscr, board, piece, px, py, next_piece, hold_piece, hold_used,
                 score, level, total_lines, paused=False)
            time.sleep(0.02)

        if game_result == 'quit':
            break
        # game_result == 'restart': outer while loop continues


if __name__ == '__main__':
    curses.wrapper(main)
