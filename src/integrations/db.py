"""SQLite database module for MapleStory Discord Bot."""

import sqlite3
import logging
import os
from typing import Any, List, Optional, Tuple, Dict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def normalize_week_date(week_date: str) -> datetime:
    """Convert week date string to datetime for proper sorting."""
    try:
        # Handle different formats: MM/DD/YYYY, M/D/YY, MM/DD/YY
        if len(week_date.split("/")[2]) == 2:  # Two-digit year
            return datetime.strptime(week_date, "%m/%d/%y")
        else:  # Four-digit year
            return datetime.strptime(week_date, "%m/%d/%Y")
    except ValueError:
        # If parsing fails, return a very old date so it sorts first
        logger.warning(f"Could not parse week date: {week_date}")
        return datetime(1970, 1, 1)


# Database path
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "../../data/maple_bot.db")


@dataclass
class Player:
    """Player data model."""

    id: int
    server_id: str
    maplestory_username: str
    discord_username: Optional[str] = None
    discord_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class GPQScore:
    """GPQ Score data model."""

    id: int
    player_id: int
    week_date: str
    score: int
    created_at: Optional[str] = None


@dataclass
class ServerProfile:
    """Server profile data model."""

    id: int
    server_id: str
    guild_name: str
    maplestory_world: str
    is_setup_complete: bool
    setup_by_user_id: Optional[str] = None
    setup_at: Optional[str] = None
    updated_at: Optional[str] = None


class MapleDatabase:
    """SQLite database handler for MapleStory Discord Bot."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._ensure_data_directory()
        self._init_database()

    def _ensure_data_directory(self):
        """Ensure the data directory exists."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _init_database(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Check if this is a fresh database or needs migration
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='players'"
            )
            table_exists = cursor.fetchone() is not None

            if table_exists:
                # Check if server_id column exists
                cursor = conn.execute("PRAGMA table_info(players)")
                columns = [row[1] for row in cursor.fetchall()]

                if "server_id" not in columns:
                    # Migrate existing tables
                    self._migrate_to_multiserver(conn)
                else:
                    # Tables already have server_id, ensure all tables exist and create indexes
                    self._ensure_all_tables(conn)
                    self._create_indexes(conn)
            else:
                # Fresh database, create with new schema
                self._create_fresh_tables(conn)
                self._create_indexes(conn)

            conn.commit()

    def _create_fresh_tables(self, conn):
        """Create fresh tables with server_id support."""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                maplestory_username TEXT NOT NULL COLLATE NOCASE,
                discord_username TEXT,
                discord_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(server_id, maplestory_username)
            )
        """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gpq_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                week_date TEXT NOT NULL,  -- Format: 'MM/DD/YYYY'
                score INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players (id),
                UNIQUE(player_id, week_date)
            )
        """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS left_kicked_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                maplestory_username TEXT NOT NULL,
                discord_username TEXT,
                discord_id TEXT,
                reason TEXT DEFAULT 'left',  -- 'left' or 'kicked'
                left_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS server_macros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                macro_name TEXT NOT NULL,
                attachment_id INTEGER,
                message_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(server_id, macro_name)
            )
        """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS server_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT UNIQUE NOT NULL,
                guild_name TEXT NOT NULL,
                maplestory_world TEXT NOT NULL, -- 'Kronos', 'Hyperion', 'Scania', 'Bera'
                is_setup_complete BOOLEAN DEFAULT TRUE,
                setup_by_user_id TEXT,
                setup_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

    def _migrate_to_multiserver(self, conn):
        """Migrate existing database to support multiple servers."""
        from core.constants import GUILD_ID

        print("Migrating existing database to multi-server support...")

        # Add server_id columns
        conn.execute("ALTER TABLE players ADD COLUMN server_id TEXT")
        conn.execute("ALTER TABLE left_kicked_players ADD COLUMN server_id TEXT")

        # Set default server_id for existing data
        conn.execute(
            "UPDATE players SET server_id = ? WHERE server_id IS NULL", (str(GUILD_ID),)
        )
        conn.execute(
            "UPDATE left_kicked_players SET server_id = ? WHERE server_id IS NULL",
            (str(GUILD_ID),),
        )

        # Create new tables
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS server_macros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                macro_name TEXT NOT NULL,
                attachment_id INTEGER,
                message_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(server_id, macro_name)
            )
        """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS server_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT UNIQUE NOT NULL,
                guild_name TEXT NOT NULL,
                maplestory_world TEXT NOT NULL, -- 'Kronos', 'Hyperion', 'Scania', 'Bera'
                is_setup_complete BOOLEAN DEFAULT TRUE,
                setup_by_user_id TEXT,
                setup_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create profile for existing main guild
        conn.execute(
            """
            INSERT OR IGNORE INTO server_profiles (server_id, guild_name, maplestory_world, is_setup_complete, setup_by_user_id)
            VALUES (?, 'Spookie', 'Bera', TRUE, 'migration')
        """,
            (str(GUILD_ID),),
        )

    def _ensure_all_tables(self, conn):
        """Ensure all tables exist, including new ones."""
        # Create server_profiles table if it doesn't exist
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS server_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT UNIQUE NOT NULL,
                guild_name TEXT NOT NULL,
                maplestory_world TEXT NOT NULL, -- 'Kronos', 'Hyperion', 'Scania', 'Bera'
                is_setup_complete BOOLEAN DEFAULT TRUE,
                setup_by_user_id TEXT,
                setup_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

    def _create_indexes(self, conn):
        """Create database indexes."""
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_players_server_maplestory ON players (server_id, maplestory_username)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_players_server_discord_id ON players (server_id, discord_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gpq_scores_player_week ON gpq_scores (player_id, week_date)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_left_kicked_server ON left_kicked_players (server_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_server_macros ON server_macros (server_id, macro_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_server_profiles ON server_profiles (server_id)"
        )

    # Player Management
    def get_player_by_id(self, player_id: int) -> Optional[Player]:
        """Get a player by their ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT id, server_id, maplestory_username, discord_username, discord_id, created_at, updated_at
                FROM players WHERE id = ?
            """,
                (player_id,),
            )
            result = cursor.fetchone()
            return Player(*result) if result else None

    def get_player_by_maplestory_username(
        self,
        server_id: str,
        username: str,
        create_if_not_exists: bool = False,
        case_sensitive: bool = False,
    ) -> Optional[Player]:
        """Get a player by their MapleStory username within a specific server."""
        with sqlite3.connect(self.db_path) as conn:
            if case_sensitive:
                cursor = conn.execute(
                    """
                    SELECT id, server_id, maplestory_username, discord_username, discord_id, created_at, updated_at
                    FROM players WHERE server_id = ? AND maplestory_username = ?
                """,
                    (server_id, username),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, server_id, maplestory_username, discord_username, discord_id, created_at, updated_at
                    FROM players WHERE server_id = ? AND LOWER(maplestory_username) = LOWER(?)
                """,
                    (server_id, username),
                )
            result = cursor.fetchone()

            if result:
                return Player(*result)

            if create_if_not_exists:
                return self.create_player(server_id, username)

            return None

    def find_player_by_maplestory_username(
        self, server_id: str, username: str, case_sensitive: bool = False
    ) -> Optional[Player]:
        """Find a player by MapleStory username, return None if not found."""
        return self.get_player_by_maplestory_username(
            server_id,
            username,
            create_if_not_exists=False,
            case_sensitive=case_sensitive,
        )

    def find_or_create_player_by_maplestory_username(
        self, server_id: str, username: str, case_sensitive: bool = False
    ) -> Player:
        """Find a player by MapleStory username, create if not found."""
        return self.get_player_by_maplestory_username(
            server_id,
            username,
            create_if_not_exists=True,
            case_sensitive=case_sensitive,
        )

    def get_players_by_discord_id(
        self, server_id: str, discord_id: int
    ) -> List[Player]:
        """Get all players linked to a Discord ID in a specific server."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT id, server_id, maplestory_username, discord_username, discord_id, created_at, updated_at
                FROM players WHERE server_id = ? AND discord_id = ?
            """,
                (server_id, str(discord_id)),
            )
            results = cursor.fetchall()
            return [Player(*result) for result in results]

    def get_player_by_discord_id(
        self, server_id: str, discord_id: int
    ) -> Optional[Player]:
        """Get the first player linked to a Discord ID in a specific server."""
        players = self.get_players_by_discord_id(server_id, discord_id)
        return players[0] if players else None

    def get_discord_id(self, player_id: int) -> Optional[str]:
        """Get Discord ID for a player."""
        player = self.get_player_by_id(player_id)
        return player.discord_id if player else None

    def get_maplestory_username(self, player_id: int) -> Optional[str]:
        """Get MapleStory username for a player."""
        player = self.get_player_by_id(player_id)
        return player.maplestory_username if player else None

    def create_player(
        self,
        server_id: str,
        maplestory_username: str,
        discord_username: str = None,
        discord_id: str = None,
    ) -> Player:
        """Create a new player."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO players (server_id, maplestory_username, discord_username, discord_id)
                VALUES (?, ?, ?, ?)
            """,
                (server_id, maplestory_username, discord_username, discord_id),
            )
            conn.commit()
            player_id = cursor.lastrowid

            # Return the created player
            return self.get_player_by_id(player_id)

    def update_player(
        self,
        player_id: int,
        maplestory_username: str = None,
        discord_username: str = None,
        discord_id: str = None,
    ) -> bool:
        """Update a player's information."""
        updates = []
        params = []

        if maplestory_username is not None:
            updates.append("maplestory_username = ?")
            params.append(maplestory_username)
        if discord_username is not None:
            updates.append("discord_username = ?")
            params.append(discord_username)
        if discord_id is not None:
            updates.append("discord_id = ?")
            params.append(str(discord_id))

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(player_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"""
                UPDATE players SET {', '.join(updates)}
                WHERE id = ?
            """,
                params,
            )
            conn.commit()
            return cursor.rowcount > 0

    def link_discord_to_player(
        self, player_id: int, discord_user, maplestory_username: str = None
    ) -> bool:
        """Link a Discord user to a MapleStory player."""
        # Handle both old discriminator format and new username format
        if hasattr(discord_user, "discriminator") and discord_user.discriminator != "0":
            discord_username = f"@{discord_user.name}#{discord_user.discriminator}"
        else:
            discord_username = f"@{discord_user.name}"

        logger.info(
            f"Linking Discord user {discord_username} (ID: {discord_user.id}) to player {player_id}"
        )

        updates = {
            "discord_username": discord_username,
            "discord_id": str(discord_user.id),
        }

        if maplestory_username:
            updates["maplestory_username"] = maplestory_username

        success = self.update_player(player_id, **updates)

        if success:
            logger.info(f"Successfully linked {discord_username} to player {player_id}")
        else:
            logger.warning(f"Failed to link Discord user to player {player_id}")

        return success

    def unlink_discord_from_player(self, player_id: int) -> bool:
        """Unlink Discord from a MapleStory player."""
        return self.update_player(player_id, discord_username=None, discord_id=None)

    def delete_player(self, player_id: int) -> bool:
        """Delete a player and all their scores."""
        with sqlite3.connect(self.db_path) as conn:
            # Delete scores first (foreign key constraint)
            conn.execute("DELETE FROM gpq_scores WHERE player_id = ?", (player_id,))
            # Delete player
            cursor = conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_all_players(self, server_id: str = None) -> List[Player]:
        """Get all players, optionally filtered by server."""
        with sqlite3.connect(self.db_path) as conn:
            if server_id:
                cursor = conn.execute(
                    """
                    SELECT id, server_id, maplestory_username, discord_username, discord_id, created_at, updated_at
                    FROM players
                    WHERE server_id = ?
                    ORDER BY LOWER(maplestory_username)
                """,
                    (server_id,),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, server_id, maplestory_username, discord_username, discord_id, created_at, updated_at
                    FROM players
                    ORDER BY LOWER(maplestory_username)
                """
                )
            results = cursor.fetchall()
            return [Player(*result) for result in results]

    # GPQ Score Management
    def record_gpq_score(self, player_id: int, week_date: str, score: int) -> bool:
        """Record a GPQ score for a player."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO gpq_scores (player_id, week_date, score)
                VALUES (?, ?, ?)
            """,
                (player_id, week_date, score),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_player_scores(
        self, player_id: int, week_dates: List[str] = None
    ) -> List[GPQScore]:
        """Get GPQ scores for a player, sorted chronologically."""
        with sqlite3.connect(self.db_path) as conn:
            if week_dates:
                placeholders = ",".join(["?" for _ in week_dates])
                cursor = conn.execute(
                    f"""
                    SELECT id, player_id, week_date, score, created_at
                    FROM gpq_scores
                    WHERE player_id = ? AND week_date IN ({placeholders})
                """,
                    [player_id] + week_dates,
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, player_id, week_date, score, created_at
                    FROM gpq_scores
                    WHERE player_id = ?
                """,
                    (player_id,),
                )

            results = cursor.fetchall()
            scores = [GPQScore(*result) for result in results]

            # Sort by date using our normalize function for proper chronological order
            scores.sort(key=lambda score: normalize_week_date(score.week_date))

            return scores

    def get_scores_for_week(
        self, server_id: str, week_date: str
    ) -> List[Tuple[Player, Optional[int]]]:
        """Get all player scores for a specific week in a specific server."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT p.id, p.server_id, p.maplestory_username, p.discord_username, p.discord_id, p.created_at, p.updated_at, gs.score
                FROM players p
                LEFT JOIN gpq_scores gs ON p.id = gs.player_id AND gs.week_date = ?
                WHERE p.server_id = ?
                ORDER BY LOWER(p.maplestory_username)
            """,
                (week_date, server_id),
            )
            results = cursor.fetchall()

            players_with_scores = []
            for result in results:
                player = Player(*result[:7])
                score = result[7]
                players_with_scores.append((player, score))

            return players_with_scores

    def get_guild_cumulative_scores_by_weeks(
        self, server_id: str, num_weeks: int
    ) -> Dict[str, int]:
        """Get cumulative GPQ scores for all players by week for the last N weeks."""
        from datetime import datetime

        with sqlite3.connect(self.db_path) as conn:
            # Get all weeks with scores for this server
            cursor = conn.execute(
                """
                SELECT DISTINCT week_date FROM gpq_scores gs
                JOIN players p ON p.id = gs.player_id
                WHERE p.server_id = ?
            """,
                (server_id,),
            )

            all_weeks = [row[0] for row in cursor.fetchall()]

            # Filter out future dates and sort chronologically
            current_time = datetime.now()
            valid_weeks = []

            for week in all_weeks:
                try:
                    week_date = normalize_week_date(week)
                    # Only include weeks that are not in the future
                    if week_date <= current_time:
                        valid_weeks.append((week, week_date))
                except:
                    continue

            # Sort by actual date and take last N weeks
            valid_weeks.sort(key=lambda x: x[1])
            recent_weeks = (
                valid_weeks[-num_weeks:]
                if len(valid_weeks) > num_weeks
                else valid_weeks
            )

            cumulative_scores = {}

            for week, _ in recent_weeks:
                # Get total scores for this week
                cursor = conn.execute(
                    """
                    SELECT SUM(gs.score) FROM gpq_scores gs
                    JOIN players p ON p.id = gs.player_id
                    WHERE p.server_id = ? AND gs.week_date = ?
                """,
                    (server_id, week),
                )

                total = cursor.fetchone()[0] or 0
                cumulative_scores[week] = total

            return cumulative_scores

    def get_player_scores_range(
        self, player_id: int, start_week: str, end_week: str
    ) -> Dict[str, int]:
        """Get player scores within a week range."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT week_date, score FROM gpq_scores
                WHERE player_id = ? AND week_date BETWEEN ? AND ?
                ORDER BY week_date
            """,
                (player_id, start_week, end_week),
            )

            return {week_date: score for week_date, score in cursor.fetchall()}

    # Left/Kicked Players Management
    def move_player_to_left_kicked(self, player_id: int, reason: str = "left") -> bool:
        """Move a player to the left/kicked table."""
        player = self.get_player_by_id(player_id)
        if not player:
            return False

        with sqlite3.connect(self.db_path) as conn:
            # Insert into left_kicked_players
            conn.execute(
                """
                INSERT INTO left_kicked_players (maplestory_username, discord_username, discord_id, reason)
                VALUES (?, ?, ?, ?)
            """,
                (
                    player.maplestory_username,
                    player.discord_username,
                    player.discord_id,
                    reason,
                ),
            )

            # Delete from players and scores
            conn.execute("DELETE FROM gpq_scores WHERE player_id = ?", (player_id,))
            cursor = conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
            conn.commit()

            return cursor.rowcount > 0

    def add_to_left_kicked(self, players_data: List[List[str]]) -> bool:
        """Add multiple players to left/kicked table."""
        with sqlite3.connect(self.db_path) as conn:
            for player_data in players_data:
                maplestory_username = player_data[0] if len(player_data) > 0 else ""
                discord_username = player_data[1] if len(player_data) > 1 else None
                discord_id = player_data[2] if len(player_data) > 2 else None

                if maplestory_username:
                    conn.execute(
                        """
                        INSERT INTO left_kicked_players (maplestory_username, discord_username, discord_id)
                        VALUES (?, ?, ?)
                    """,
                        (maplestory_username, discord_username, discord_id),
                    )
            conn.commit()
            return True

    def get_player_data(self, player_id: int) -> List[str]:
        """Get player data as a list (for compatibility with existing code)."""
        player = self.get_player_by_id(player_id)
        if not player:
            return []

        return [
            player.maplestory_username or "",
            player.discord_username or "",
            player.discord_id or "",
        ]

    def insert_player_data(self, player_data: List[str], position: int = None) -> int:
        """Insert a new player from data list."""
        maplestory_username = player_data[0] if len(player_data) > 0 else ""
        discord_username = player_data[1] if len(player_data) > 1 else None
        discord_id = player_data[2] if len(player_data) > 2 else None

        player = self.create_player(maplestory_username, discord_username, discord_id)
        return player.id if player else None

    # Utility Methods
    def get_player_count(self) -> int:
        """Get total number of active players."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM players")
            return cursor.fetchone()[0]

    def get_week_participation(self, week_date: str) -> Tuple[int, int]:
        """Get participation stats for a week (players_with_scores, total_players)."""
        with sqlite3.connect(self.db_path) as conn:
            # Players with scores
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM gpq_scores WHERE week_date = ?
            """,
                (week_date,),
            )
            with_scores = cursor.fetchone()[0]

            # Total players
            cursor = conn.execute("SELECT COUNT(*) FROM players")
            total = cursor.fetchone()[0]

            return with_scores, total

    # Server-specific macro management
    def create_macro(
        self,
        server_id: str,
        macro_name: str,
        attachment_id: int = None,
        message_content: str = None,
    ) -> bool:
        """Create a macro for a specific server."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO server_macros (server_id, macro_name, attachment_id, message_content)
                    VALUES (?, ?, ?, ?)
                """,
                    (server_id, macro_name, attachment_id, message_content),
                )
                conn.commit()
                return cursor.rowcount > 0
            except sqlite3.IntegrityError:
                # Macro already exists
                return False

    def get_macro(
        self, server_id: str, macro_name: str
    ) -> Optional[Tuple[Optional[int], Optional[str]]]:
        """Get a macro for a specific server."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT attachment_id, message_content FROM server_macros
                WHERE server_id = ? AND macro_name = ?
            """,
                (server_id, macro_name),
            )
            result = cursor.fetchone()
            return result if result else None

    def delete_macro(self, server_id: str, macro_name: str) -> bool:
        """Delete a macro for a specific server."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM server_macros WHERE server_id = ? AND macro_name = ?
            """,
                (server_id, macro_name),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_all_macros(self, server_id: str) -> List[str]:
        """Get all macro names for a specific server."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT macro_name FROM server_macros WHERE server_id = ? ORDER BY macro_name
            """,
                (server_id,),
            )
            results = cursor.fetchall()
            return [row[0] for row in results]

    # Server Profile Management
    def get_server_profile(self, server_id: str) -> Optional[ServerProfile]:
        """Get server profile by server ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT id, server_id, guild_name, maplestory_world, is_setup_complete, setup_by_user_id, setup_at, updated_at
                FROM server_profiles WHERE server_id = ?
            """,
                (server_id,),
            )
            result = cursor.fetchone()
            return ServerProfile(*result) if result else None

    def is_server_setup_complete(self, server_id: str) -> bool:
        """Check if server has completed setup."""
        profile = self.get_server_profile(server_id)
        return profile.is_setup_complete if profile else False

    def create_server_profile(
        self,
        server_id: str,
        guild_name: str,
        maplestory_world: str,
        setup_by_user_id: str,
    ) -> bool:
        """Create a new server profile."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO server_profiles (server_id, guild_name, maplestory_world, is_setup_complete, setup_by_user_id)
                    VALUES (?, ?, ?, TRUE, ?)
                """,
                    (server_id, guild_name, maplestory_world, setup_by_user_id),
                )
                conn.commit()
                return cursor.rowcount > 0
            except sqlite3.IntegrityError:
                # Server profile already exists
                return False

    def update_server_profile(
        self, server_id: str, guild_name: str = None, maplestory_world: str = None
    ) -> bool:
        """Update an existing server profile."""
        updates = []
        params = []

        if guild_name is not None:
            updates.append("guild_name = ?")
            params.append(guild_name)
        if maplestory_world is not None:
            updates.append("maplestory_world = ?")
            params.append(maplestory_world)

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(server_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"""
                UPDATE server_profiles SET {', '.join(updates)}
                WHERE server_id = ?
            """,
                params,
            )
            conn.commit()
            return cursor.rowcount > 0

    # Legacy compatibility methods for smooth transition
    # Properly named database methods (no "row" terminology)
    def find_or_create_player_id_by_username(
        self,
        server_id: str,
        username: str,
        fail_if_not_found: bool = False,
        case_sensitive: bool = False,
    ) -> Optional[int]:
        """Get player ID by MapleStory username, optionally create if not found."""
        player = self.find_player_by_maplestory_username(
            server_id, username, case_sensitive
        )
        if player:
            return player.id

        if fail_if_not_found:
            return None

        # Create player if not found and fail_if_not_found is False
        player = self.create_player(server_id, username)
        return player.id if player else None

    def get_player_ids_by_discord_id(
        self, server_id: str, discord_id: int
    ) -> Optional[List[int]]:
        """Get all player IDs linked to a Discord ID in a specific server."""
        players = self.get_players_by_discord_id(server_id, discord_id)
        return [player.id for player in players] if players else None

    # Legacy methods - DEPRECATED, use proper method names
    def get_row_for_maplestory_username(
        self,
        server_id: str,
        username: str,
        fail_on_not_found: bool,
        case_sensitive: bool = False,
    ) -> Optional[int]:
        """DEPRECATED: Use find_or_create_player_id_by_username() instead."""
        return self.find_or_create_player_id_by_username(
            server_id, username, fail_on_not_found, case_sensitive
        )

    def get_rows_for_discord_id(
        self, server_id: str, discord_id: int
    ) -> Optional[List[int]]:
        """DEPRECATED: Use get_player_ids_by_discord_id() instead."""
        return self.get_player_ids_by_discord_id(server_id, discord_id)

    def get_discord_id_for_row(self, player_id: int) -> Optional[str]:
        """DEPRECATED: Use get_discord_id() instead."""
        return self.get_discord_id(player_id)

    def get_maplestory_username_for_row(self, player_id: int) -> Optional[str]:
        """DEPRECATED: Use get_maplestory_username() instead."""
        return self.get_maplestory_username(player_id)

    # DEPRECATED spreadsheet methods - for backward compatibility only
    def record_value(self, player_id: int, column: int, value: int) -> bool:
        """DEPRECATED: Use record_score_for_week() instead."""
        from utils.time_utils import get_current_week

        current_week = get_current_week()
        return self.record_gpq_score(player_id, current_week, value)

    def get_column_for_week(self, week: str) -> Optional[int]:
        """DEPRECATED: Use week_exists_in_database() instead."""
        # Return a fake column number for compatibility
        return 4 if self.week_exists_in_database(week) else None

    def get_range(
        self, start_row: int, start_col: int, end_row: int, end_col: int
    ) -> List:
        """DEPRECATED: Use proper database query methods instead."""
        # Return mock data for compatibility
        from dataclasses import dataclass

        @dataclass
        class MockCell:
            row: int
            col: int
            value: Any

        # For score queries, return player's historical scores
        if start_row == end_row:  # Single player query
            player_id = start_row
            player = self.get_player_by_id(player_id)
            if not player:
                return []

            from utils.time_utils import get_current_week, get_last_week

            current_week = get_current_week()

            # Get scores for this player
            scores = self.get_player_scores(player_id)
            score_dict = {score.week_date: score.score for score in scores}

            cells = []
            for col in range(start_col, end_col + 1):
                # Mock up some recent weeks for compatibility
                value = score_dict.get(current_week) if col >= 4 else None
                cells.append(MockCell(row=start_row, col=col, value=value))

            return cells

        return []  # Empty for unsupported ranges

    def link_user(self, player_id: int, discord_user, maple_name: str) -> bool:
        """Legacy method: Link Discord user to player."""
        return self.link_discord_to_player(player_id, discord_user, maple_name)

    def unlink_user(self, player_id: int, discord_user, maple_name: str) -> bool:
        """Legacy method: Unlink Discord user from player."""
        return self.unlink_discord_from_player(player_id)

    def record_score_for_week(self, player_id: int, week_date: str, score: int) -> bool:
        """Record a player's score for a specific week."""
        return self.record_gpq_score(player_id, week_date, score)

    def get_player_scores_for_weeks(
        self, player_id: int, week_dates: List[str]
    ) -> List[Optional[int]]:
        """Get player scores for specific weeks in order."""
        with sqlite3.connect(self.db_path) as conn:
            if not week_dates:
                return []

            placeholders = ",".join(["?" for _ in week_dates])
            cursor = conn.execute(
                f"""
                SELECT week_date, score FROM gpq_scores 
                WHERE player_id = ? AND week_date IN ({placeholders})
                ORDER BY week_date
            """,
                [player_id] + week_dates,
            )

            score_dict = {week_date: score for week_date, score in cursor.fetchall()}
            # Return scores in the same order as requested weeks
            return [score_dict.get(week_date) for week_date in week_dates]

    def get_all_players_with_current_week_score(
        self, current_week: str
    ) -> List[Tuple[Player, Optional[int]]]:
        """Get all players with their current week scores."""
        return self.get_scores_for_week(current_week)

    def get_all_players_discord_ids(self) -> List[Optional[str]]:
        """Get Discord IDs for all players (in username order)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT discord_id FROM players 
                ORDER BY LOWER(maplestory_username)
            """
            )
            return [row[0] for row in cursor.fetchall()]

    def get_all_gpq_cells(self) -> List[List[Any]]:
        """Legacy method: Get all GPQ data as 2D array."""
        with sqlite3.connect(self.db_path) as conn:
            # Get all players
            cursor = conn.execute(
                """
                SELECT id, maplestory_username, discord_username, discord_id
                FROM players
                ORDER BY LOWER(maplestory_username)
            """
            )
            players = cursor.fetchall()

            # Get all unique weeks
            weeks_cursor = conn.execute(
                """
                SELECT DISTINCT week_date FROM gpq_scores
            """
            )
            weeks = [row[0] for row in weeks_cursor.fetchall()]

            # Sort weeks chronologically using our normalize function
            weeks.sort(key=normalize_week_date)

            # Create header row
            headers = ["MapleStory Username", "Discord Username", "Discord ID"] + weeks
            rows = [headers]

            # Create data rows
            for player_id, maplestory_username, discord_username, discord_id in players:
                row_data = [
                    maplestory_username or "",
                    discord_username or "",
                    discord_id or "",
                ]

                # Add scores for each week
                for week in weeks:
                    score_cursor = conn.execute(
                        """
                        SELECT score FROM gpq_scores 
                        WHERE player_id = ? AND week_date = ?
                    """,
                        (player_id, week),
                    )
                    score_result = score_cursor.fetchone()
                    score = score_result[0] if score_result else ""
                    row_data.append(str(score) if score else "")

                rows.append(row_data)

            return rows

    def week_exists_in_database(self, week_date: str) -> bool:
        """Check if a week exists in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 1 FROM gpq_scores WHERE week_date = ? LIMIT 1
            """,
                (week_date,),
            )
            return cursor.fetchone() is not None

    # Direct database methods (no more worksheet terminology)
    def get_player_data(self, player_id: int) -> List[str]:
        """Get player data as a list."""
        player = self.get_player_by_id(player_id)
        if not player:
            return []

        return [
            player.maplestory_username or "",
            player.discord_username or "",
            player.discord_id or "",
        ]

    def delete_player_by_id(self, player_id: int) -> bool:
        """Delete a player by ID."""
        return self.delete_player(player_id)

    def create_player_from_data(self, data: List[str]) -> int:
        """Create a player from data list and return player ID."""
        maplestory_username = data[0] if len(data) > 0 else ""
        discord_username = data[1] if len(data) > 1 else None
        discord_id = data[2] if len(data) > 2 else None

        player = self.create_player(maplestory_username, discord_username, discord_id)
        return player.id if player else None

    def add_players_to_left_kicked(self, players_data: List[List[str]]) -> bool:
        """Add multiple players to left/kicked table."""
        return self.add_to_left_kicked(players_data)

    # Legacy compatibility properties - DEPRECATED, use direct methods instead
    @property
    def worksheet(self):
        """DEPRECATED: Use direct database methods instead."""
        return WorksheetCompatibilityLayer(self)

    @property
    def left_worksheet(self):
        """DEPRECATED: Use add_players_to_left_kicked() instead."""
        return LeftKickedWorksheetCompatibility(self)


class WorksheetCompatibilityLayer:
    """Compatibility layer for old worksheet methods."""

    def __init__(self, db: MapleDatabase):
        self.db = db

    def delete_rows(self, player_id: int):
        """Delete a player."""
        return self.db.delete_player(player_id)

    def row_values(self, player_id: int) -> List[str]:
        """Get player data as list."""
        return self.db.get_player_data(player_id)

    def insert_row(self, data: List[str], position: int = None) -> int:
        """Insert new player."""
        return self.db.insert_player_data(data, position)


class LeftKickedWorksheetCompatibility:
    """Compatibility layer for left/kicked worksheet methods."""

    def __init__(self, db: MapleDatabase):
        self.db = db

    def append_rows(self, players_data: List[List[str]]):
        """Add players to left/kicked table."""
        return self.db.add_to_left_kicked(players_data)


# Create a singleton instance
_db_instance = None


def get_database() -> MapleDatabase:
    """Get the singleton database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = MapleDatabase()
    return _db_instance
