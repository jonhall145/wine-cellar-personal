"""
Offline operation queue for wine cellar Pi client.

Stores operations locally when server is unavailable and
syncs them when connectivity is restored.
"""

import json
import sqlite3
import time
import threading
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import base64


class OperationType(Enum):
    """Types of queued operations."""
    ADD_WINE = "add_wine"
    REMOVE_WINE = "remove_wine"
    UPDATE_WINE = "update_wine"
    POSITION_CHANGE = "position_change"
    RACK_SNAPSHOT = "rack_snapshot"


class OperationStatus(Enum):
    """Operation sync status."""
    PENDING = "pending"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QueuedOperation:
    """Queued operation data."""
    id: Optional[int] = None
    operation_type: str = ""
    data: Dict[str, Any] = None
    image_data: Optional[bytes] = None
    created_at: float = 0.0
    status: str = OperationStatus.PENDING.value
    retry_count: int = 0
    last_error: str = ""

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.created_at == 0.0:
            self.created_at = time.time()


class OfflineQueue:
    """
    SQLite-based offline operation queue.

    Persists operations to disk so they survive Pi restarts.
    """

    def __init__(self, db_path: str = "~/.wine_cellar/offline_queue.db"):
        """
        Initialize offline queue.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    image_data BLOB,
                    created_at REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status
                ON operations(status)
            """)
            conn.commit()

    def add(self, operation: QueuedOperation) -> int:
        """
        Add operation to queue.

        Args:
            operation: Operation to queue

        Returns:
            Operation ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO operations
                (operation_type, data, image_data, created_at, status, retry_count, last_error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                operation.operation_type,
                json.dumps(operation.data),
                operation.image_data,
                operation.created_at,
                operation.status,
                operation.retry_count,
                operation.last_error,
            ))
            conn.commit()
            return cursor.lastrowid

    def get_pending(self, limit: int = 100) -> List[QueuedOperation]:
        """
        Get pending operations in order.

        Args:
            limit: Maximum operations to return

        Returns:
            List of pending operations
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM operations
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,)).fetchall()

        return [self._row_to_operation(row) for row in rows]

    def get_all(self, include_completed: bool = False) -> List[QueuedOperation]:
        """Get all operations."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if include_completed:
                rows = conn.execute(
                    "SELECT * FROM operations ORDER BY created_at ASC"
                ).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM operations
                    WHERE status != 'completed'
                    ORDER BY created_at ASC
                """).fetchall()

        return [self._row_to_operation(row) for row in rows]

    def update_status(
        self,
        operation_id: int,
        status: OperationStatus,
        error: str = ""
    ) -> None:
        """Update operation status."""
        with sqlite3.connect(self.db_path) as conn:
            if status == OperationStatus.FAILED:
                conn.execute("""
                    UPDATE operations
                    SET status = ?, last_error = ?, retry_count = retry_count + 1
                    WHERE id = ?
                """, (status.value, error, operation_id))
            else:
                conn.execute("""
                    UPDATE operations
                    SET status = ?, last_error = ?
                    WHERE id = ?
                """, (status.value, error, operation_id))
            conn.commit()

    def mark_syncing(self, operation_id: int) -> None:
        """Mark operation as currently syncing."""
        self.update_status(operation_id, OperationStatus.SYNCING)

    def mark_completed(self, operation_id: int) -> None:
        """Mark operation as successfully synced."""
        self.update_status(operation_id, OperationStatus.COMPLETED)

    def mark_failed(self, operation_id: int, error: str) -> None:
        """Mark operation as failed."""
        self.update_status(operation_id, OperationStatus.FAILED, error)

    def reset_failed(self, max_retries: int = 3) -> int:
        """
        Reset failed operations for retry (if under max retries).

        Returns:
            Number of operations reset
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE operations
                SET status = 'pending'
                WHERE status = 'failed' AND retry_count < ?
            """, (max_retries,))
            conn.commit()
            return cursor.rowcount

    def clear_completed(self, older_than_hours: int = 24) -> int:
        """
        Remove old completed operations.

        Args:
            older_than_hours: Remove completed ops older than this

        Returns:
            Number of operations removed
        """
        cutoff = time.time() - (older_than_hours * 3600)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM operations
                WHERE status = 'completed' AND created_at < ?
            """, (cutoff,))
            conn.commit()
            return cursor.rowcount

    def count_pending(self) -> int:
        """Get count of pending operations."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT COUNT(*) FROM operations WHERE status = 'pending'
            """).fetchone()
            return row[0] if row else 0

    def _row_to_operation(self, row: sqlite3.Row) -> QueuedOperation:
        """Convert database row to operation."""
        return QueuedOperation(
            id=row["id"],
            operation_type=row["operation_type"],
            data=json.loads(row["data"]),
            image_data=row["image_data"],
            created_at=row["created_at"],
            status=row["status"],
            retry_count=row["retry_count"],
            last_error=row["last_error"],
        )


class SyncManager:
    """
    Manages synchronization between offline queue and server.

    Monitors connectivity and syncs queued operations
    when server becomes available.
    """

    def __init__(
        self,
        queue: OfflineQueue,
        api_client: 'APIClient',  # Forward reference
        check_interval: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Initialize sync manager.

        Args:
            queue: Offline queue instance
            api_client: API client for server communication
            check_interval: Seconds between connectivity checks
            max_retries: Max retries per operation
        """
        self.queue = queue
        self.api_client = api_client
        self.check_interval = check_interval
        self.max_retries = max_retries

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_sync_complete: Optional[Callable[[int], None]] = None
        self._on_sync_error: Optional[Callable[[str], None]] = None

    def set_callbacks(
        self,
        on_sync_complete: Optional[Callable[[int], None]] = None,
        on_sync_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Set callback functions for sync events."""
        self._on_sync_complete = on_sync_complete
        self._on_sync_error = on_sync_error

    def start(self) -> None:
        """Start background sync thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background sync thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def sync_now(self) -> int:
        """
        Immediately sync all pending operations.

        Returns:
            Number of operations synced
        """
        if not self.api_client.is_online():
            return 0

        synced = 0
        pending = self.queue.get_pending()

        for op in pending:
            try:
                self.queue.mark_syncing(op.id)
                self._sync_operation(op)
                self.queue.mark_completed(op.id)
                synced += 1
            except Exception as e:
                self.queue.mark_failed(op.id, str(e))
                if self._on_sync_error:
                    self._on_sync_error(str(e))

        if synced > 0 and self._on_sync_complete:
            self._on_sync_complete(synced)

        return synced

    def _sync_loop(self) -> None:
        """Background sync loop."""
        while self._running:
            try:
                # Reset failed operations for retry
                self.queue.reset_failed(self.max_retries)

                # Sync pending operations
                pending_count = self.queue.count_pending()
                if pending_count > 0:
                    self.sync_now()

                # Clean up old completed operations
                self.queue.clear_completed()

            except Exception as e:
                if self._on_sync_error:
                    self._on_sync_error(f"Sync loop error: {e}")

            # Wait for next check
            time.sleep(self.check_interval)

    def _sync_operation(self, op: QueuedOperation) -> None:
        """
        Sync single operation to server.

        Args:
            op: Operation to sync

        Raises:
            Exception on sync failure
        """
        op_type = op.operation_type

        if op_type == OperationType.ADD_WINE.value:
            self._sync_add_wine(op)
        elif op_type == OperationType.REMOVE_WINE.value:
            self._sync_remove_wine(op)
        elif op_type == OperationType.UPDATE_WINE.value:
            self._sync_update_wine(op)
        elif op_type == OperationType.POSITION_CHANGE.value:
            self._sync_position_change(op)
        elif op_type == OperationType.RACK_SNAPSHOT.value:
            self._sync_rack_snapshot(op)
        else:
            raise ValueError(f"Unknown operation type: {op_type}")

    def _sync_add_wine(self, op: QueuedOperation) -> None:
        """Sync add wine operation."""
        data = op.data
        wine_id = data.get("wine_id")
        rack_id = data.get("rack_id")
        row = data.get("row")
        col = data.get("col")

        if wine_id and rack_id is not None:
            self.api_client.add_wine_to_position(wine_id, rack_id, row, col)

    def _sync_remove_wine(self, op: QueuedOperation) -> None:
        """Sync remove wine operation."""
        data = op.data
        rack_id = data.get("rack_id")
        row = data.get("row")
        col = data.get("col")

        if rack_id is not None:
            self.api_client.remove_wine_from_position(rack_id, row, col)

    def _sync_update_wine(self, op: QueuedOperation) -> None:
        """Sync update wine operation."""
        from .api_client import Wine
        wine = Wine.from_dict(op.data.get("wine", {}))
        if wine.id:
            self.api_client.update_wine(wine)

    def _sync_position_change(self, op: QueuedOperation) -> None:
        """Sync position change report."""
        data = op.data
        self.api_client.report_position_change(
            rack_id=data.get("rack_id"),
            row=data.get("row"),
            col=data.get("col"),
            change_type=data.get("change_type"),
            wine_id=data.get("wine_id"),
            confidence=data.get("confidence", 0.0),
            image=op.image_data,
        )

    def _sync_rack_snapshot(self, op: QueuedOperation) -> None:
        """Sync rack snapshot."""
        data = op.data
        self.api_client.upload_rack_snapshot(
            rack_id=data.get("rack_id"),
            image=op.image_data,
            grid_state=data.get("grid_state"),
        )


# Convenience functions for queuing operations

def queue_add_wine(
    queue: OfflineQueue,
    wine_id: int,
    rack_id: int,
    row: int,
    col: int,
) -> int:
    """Queue add wine operation."""
    op = QueuedOperation(
        operation_type=OperationType.ADD_WINE.value,
        data={
            "wine_id": wine_id,
            "rack_id": rack_id,
            "row": row,
            "col": col,
        }
    )
    return queue.add(op)


def queue_remove_wine(
    queue: OfflineQueue,
    rack_id: int,
    row: int,
    col: int,
) -> int:
    """Queue remove wine operation."""
    op = QueuedOperation(
        operation_type=OperationType.REMOVE_WINE.value,
        data={
            "rack_id": rack_id,
            "row": row,
            "col": col,
        }
    )
    return queue.add(op)


def queue_position_change(
    queue: OfflineQueue,
    rack_id: int,
    row: int,
    col: int,
    change_type: str,
    wine_id: Optional[int] = None,
    confidence: float = 0.0,
    image: Optional[bytes] = None,
) -> int:
    """Queue position change report."""
    op = QueuedOperation(
        operation_type=OperationType.POSITION_CHANGE.value,
        data={
            "rack_id": rack_id,
            "row": row,
            "col": col,
            "change_type": change_type,
            "wine_id": wine_id,
            "confidence": confidence,
        },
        image_data=image,
    )
    return queue.add(op)


def queue_rack_snapshot(
    queue: OfflineQueue,
    rack_id: int,
    image: bytes,
    grid_state: Optional[Dict] = None,
) -> int:
    """Queue rack snapshot."""
    op = QueuedOperation(
        operation_type=OperationType.RACK_SNAPSHOT.value,
        data={
            "rack_id": rack_id,
            "grid_state": grid_state,
        },
        image_data=image,
    )
    return queue.add(op)
