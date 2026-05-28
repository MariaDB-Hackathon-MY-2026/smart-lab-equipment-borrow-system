from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import connection


def is_mariadb_connection() -> bool:
    if connection.vendor != 'mysql':
        return False

    server_info = getattr(connection, 'mysql_server_info', '') or ''
    return 'mariadb' in server_info.lower()


def refresh_overdue_borrows() -> None:
    if not is_mariadb_connection():
        return

    with connection.cursor() as cursor:
        cursor.execute('CALL refresh_overdue_borrows()')


def calculate_penalty_in_db(borrow_id: int, as_of_date: date | None = None) -> Decimal | None:
    if not is_mariadb_connection():
        return None

    effective_date = as_of_date or date.today()
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT borrow_penalty_amount(%s, %s)',
            [borrow_id, effective_date],
        )
        row = cursor.fetchone()

    return row[0] if row else None


def finalize_borrow_return_in_db(borrow_id: int, return_date: date) -> Decimal | None:
    if not is_mariadb_connection():
        return None

    with connection.cursor() as cursor:
        cursor.execute('CALL finalize_borrow_return(%s, %s)', [borrow_id, return_date])
        cursor.execute('SELECT penalty FROM dashboard_borrow WHERE id = %s', [borrow_id])
        row = cursor.fetchone()

    return row[0] if row else None


def fetch_equipment_history(equipment_id: int) -> list[dict]:
    if not is_mariadb_connection():
        return []

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                name,
                category,
                serial_number,
                status,
                `condition`,
                condition_remarks,
                daily_penalty,
                created_at,
                row_start,
                row_end
            FROM dashboard_equipment
            FOR SYSTEM_TIME ALL
            WHERE id = %s
            ORDER BY row_start DESC
            """,
            [equipment_id],
        )
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()

    return [dict(zip(columns, row)) for row in rows]
