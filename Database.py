"""
SQLite-backed persistence for the chess app: saves every game's metadata
and full move history as it's played, so a game can be resumed later.

Schema
------
players(id, display_name, created_at, last_played_at, games_won, games_lost, draws)
games(id, started_at, ended_at, player_id, player_one_human,
      player_two_id, player_two_human, ai_depth, status, result)
    status : 'in_progress' | 'finished' | 'abandoned'
    result : 'checkmate_white' | 'checkmate_black' | 'stalemate' | None

moves(id, game_id, ply, start_row, start_col, end_row, end_col,
      piece_moved, piece_captured, en_passant, pawn_promotion,
      promotion_choice, castle, notation, created_at)
    ply : 1-based half-move index within the game (matches len(gs.moveLog)
          after the move is applied), so "undo" just deletes the highest ply.
"""

import sqlite3
from datetime import datetime, timezone


# Name of the profile that stands in for the AI opponent. It is a real row in
# `players` so its wins/losses are tracked, but it is not a human profile.
COMPUTER_NAME = "Computer"


SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name      TEXT NOT NULL COLLATE NOCASE UNIQUE,
    created_at        TEXT NOT NULL,
    last_played_at    TEXT NOT NULL,
    games_won         INTEGER NOT NULL DEFAULT 0,
    games_lost        INTEGER NOT NULL DEFAULT 0,
    draws             INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS games (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at        TEXT NOT NULL,
    ended_at          TEXT,
    player_id         INTEGER REFERENCES players(id),
    player_two_id     INTEGER REFERENCES players(id),
    player_one_human  INTEGER NOT NULL,
    player_two_human  INTEGER NOT NULL,
    ai_depth          INTEGER,
    status            TEXT NOT NULL DEFAULT 'in_progress',
    result            TEXT
);

CREATE TABLE IF NOT EXISTS moves (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id           INTEGER NOT NULL REFERENCES games(id),
    ply               INTEGER NOT NULL,
    start_row         INTEGER NOT NULL,
    start_col         INTEGER NOT NULL,
    end_row           INTEGER NOT NULL,
    end_col           INTEGER NOT NULL,
    piece_moved       TEXT NOT NULL,
    piece_captured    TEXT NOT NULL,
    en_passant        INTEGER NOT NULL,
    pawn_promotion    INTEGER NOT NULL,
    promotion_choice  TEXT,
    castle            INTEGER NOT NULL,
    notation          TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    UNIQUE(game_id, ply)
);

CREATE INDEX IF NOT EXISTS idx_moves_game ON moves(game_id, ply);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class GameDatabase:
    """Thin wrapper around sqlite3 for saving/loading chess games."""

    def __init__(self, db_path="chess_games.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate_games()
        self.conn.commit()

    def _migrate_games(self):
        """Add columns introduced after the first version of the local database."""
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(games)")}
        if "player_id" not in columns:
            self.conn.execute("ALTER TABLE games ADD COLUMN player_id INTEGER REFERENCES players(id)")
        if "player_two_id" not in columns:
            self.conn.execute("ALTER TABLE games ADD COLUMN player_two_id INTEGER REFERENCES players(id)")

    # ---- local profiles -------------------------------------------------

    def list_players(self, include_computer=True):
        """
        All profiles, most recently played first. The built-in computer opponent
        is a profile too (so its record shows up in the history screens); pass
        include_computer=False for screens where a human picks who they are.
        """
        where = "" if include_computer else "WHERE p.display_name <> ? "
        params = () if include_computer else (COMPUTER_NAME,)
        rows = self.conn.execute(
            "SELECT p.*, COUNT(DISTINCT g.id) AS game_count "
            "FROM players p LEFT JOIN games g "
            "ON (g.player_id = p.id OR g.player_two_id = p.id) AND g.status = 'finished' "
            + where +
            "GROUP BY p.id ORDER BY p.last_played_at DESC, p.created_at ASC",
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def get_or_create_player(self, display_name):
        name = " ".join(display_name.strip().split())
        if not name:
            raise ValueError("A player name is required.")
        row = self.conn.execute(
            "SELECT * FROM players WHERE lower(display_name) = lower(?)", (name,)
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE players SET last_played_at = ? WHERE id = ?", (_now(), row["id"])
            )
            self.conn.commit()
            return dict(row)
        cur = self.conn.execute(
            "INSERT INTO players (display_name, created_at, last_played_at) VALUES (?, ?, ?)",
            (name, _now(), _now()),
        )
        self.conn.commit()
        return dict(self.conn.execute(
            "SELECT * FROM players WHERE id = ?", (cur.lastrowid,)
        ).fetchone())

    def get_player(self, player_id):
        row = self.conn.execute(
            "SELECT * FROM players WHERE id = ?", (player_id,)
        ).fetchone()
        return dict(row) if row else None

    # ---- game lifecycle -------------------------------------------------

    def start_game(
        self, player_one_human, player_two_human, ai_depth,
        player_id=None, player_two_id=None
    ):
        cur = self.conn.execute(
            "INSERT INTO games (started_at, player_id, player_two_id, player_one_human, "
            "player_two_human, ai_depth, status) VALUES (?, ?, ?, ?, ?, ?, 'in_progress')",
            (_now(), player_id, player_two_id, int(player_one_human),
             int(player_two_human), ai_depth),
        )
        self.conn.commit()
        for participant_id in (player_id, player_two_id):
            if participant_id is not None:
                self.conn.execute(
                    "UPDATE players SET last_played_at = ? WHERE id = ?",
                    (_now(), participant_id),
                )
        if player_id is not None or player_two_id is not None:
            self.conn.commit()
        return cur.lastrowid

    def end_game(self, game_id, result):
        """result: 'checkmate_white' | 'checkmate_black' | 'stalemate'"""
        cur = self.conn.execute(
            "UPDATE games SET ended_at = ?, status = 'finished', result = ? "
            "WHERE id = ? AND status = 'in_progress'",
            (_now(), result, game_id),
        )
        if cur.rowcount == 0:
            return
        game = self.conn.execute(
            "SELECT player_id, player_two_id, player_one_human, player_two_human "
            "FROM games WHERE id = ?", (game_id,)
        ).fetchone()
        if game:
            participants = (
                (game["player_id"], True),
                (game["player_two_id"], False),
            )
            for participant_id, is_white in participants:
                if participant_id is None:
                    continue
                won = (
                    result == "checkmate_white" and is_white
                ) or (
                    result == "checkmate_black" and not is_white
                )
                lost = result.startswith("checkmate_") and not won
                column = "games_won" if won else "games_lost" if lost else "draws"
                self.conn.execute(
                    f"UPDATE players SET {column} = {column} + 1, last_played_at = ? "
                    "WHERE id = ?",
                    (_now(), participant_id),
                )
        self.conn.commit()

    def abandon_game(self, game_id):
        """Called when the player quits or resets mid-game without a result."""
        self.conn.execute(
            "UPDATE games SET ended_at = ?, status = 'abandoned' "
            "WHERE id = ? AND status = 'in_progress'",
            (_now(), game_id),
        )
        self.conn.commit()

    # ---- move recording ---------------------------------------------------

    def record_move(self, game_id, ply, move):
        """move: a ChessEngine.Move instance that has just been applied."""
        self.conn.execute(
            "INSERT OR REPLACE INTO moves "
            "(game_id, ply, start_row, start_col, end_row, end_col, piece_moved, "
            " piece_captured, en_passant, pawn_promotion, promotion_choice, castle, "
            " notation, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                game_id, ply, move.startRow, move.startCol, move.endRow, move.endCol,
                move.pieceMoved, move.pieceCaptured, int(move.enPassant),
                int(move.pawnPromotion), move.promotionChoice, int(move.castle),
                str(move), _now(),
            ),
        )
        self.conn.commit()

    def undo_last_move(self, game_id):
        """Deletes the highest-ply move row for this game (mirrors GameState.undoMove())."""
        row = self.conn.execute(
            "SELECT MAX(ply) AS max_ply FROM moves WHERE game_id = ?", (game_id,)
        ).fetchone()
        if row and row["max_ply"] is not None:
            self.conn.execute(
                "DELETE FROM moves WHERE game_id = ? AND ply = ?", (game_id, row["max_ply"])
            )
            self.conn.commit()

    # ---- loading / resuming ------------------------------------------------

    def get_unfinished_game(self, player_id=None):
        """Most recent in-progress game (as either side, if player_id is given), or None."""
        if player_id is None:
            row = self.conn.execute(
                "SELECT * FROM games WHERE status = 'in_progress' "
                "ORDER BY started_at DESC, id DESC LIMIT 1"
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM games WHERE status = 'in_progress' "
                "AND (player_id = ? OR player_two_id = ?) "
                "ORDER BY started_at DESC, id DESC LIMIT 1", (player_id, player_id)
            ).fetchone()
        return dict(row) if row else None

    def get_moves(self, game_id):
        """Ordered list of move dicts for replaying a game."""
        rows = self.conn.execute(
            "SELECT * FROM moves WHERE game_id = ? ORDER BY ply ASC", (game_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def list_recent_games(self, limit=10):
        rows = self.conn.execute(
            "SELECT g.*, white.display_name AS white_player, "
            "black.display_name AS black_player, "
            "(SELECT COUNT(*) FROM moves m WHERE m.game_id = g.id) AS move_count "
            "FROM games g "
            "LEFT JOIN players white ON white.id = g.player_id "
            "LEFT JOIN players black ON black.id = g.player_two_id "
            "ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- cleanup -------------------------------------------------------

    def close(self):
        self.conn.close()