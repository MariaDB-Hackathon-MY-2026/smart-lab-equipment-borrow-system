from django.db import migrations


def _is_mariadb(schema_editor):
    connection = schema_editor.connection
    return connection.vendor == 'mysql' and getattr(connection, 'mysql_is_mariadb', False)


def _show_create_table(cursor, table_name):
    cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
    row = cursor.fetchone()
    return row[1] if row else ''


def _table_has_system_versioning(cursor, table_name):
    return 'WITH SYSTEM VERSIONING' in _show_create_table(cursor, table_name).upper()


def _install_mariadb_features(apps, schema_editor):
    if not _is_mariadb(schema_editor):
        return

    equipment_table = 'equipment_equipment'
    lending_request_table = 'lending_lendingrequest'
    penalty_table = 'lending_penalty'

    with schema_editor.connection.cursor() as cursor:
        if not _table_has_system_versioning(cursor, equipment_table):
            cursor.execute(f"ALTER TABLE `{equipment_table}` ADD SYSTEM VERSIONING")

        if not _table_has_system_versioning(cursor, lending_request_table):
            cursor.execute(f"ALTER TABLE `{lending_request_table}` ADD SYSTEM VERSIONING")

        cursor.execute("DROP EVENT IF EXISTS ev_refresh_overdue_penalties")
        cursor.execute("DROP PROCEDURE IF EXISTS sp_refresh_overdue_penalties")

        cursor.execute(
            f"""
            CREATE PROCEDURE sp_refresh_overdue_penalties()
            BEGIN
                UPDATE `{lending_request_table}`
                SET status = 'overdue',
                    updated_at = NOW()
                WHERE requested_until < CURDATE()
                  AND status IN ('approved', 'borrowed');

                INSERT INTO `{penalty_table}` (
                    lending_request_id,
                    amount,
                    days_overdue,
                    status,
                    note,
                    created_at,
                    updated_at
                )
                SELECT
                    lr.id,
                    DATEDIFF(CURDATE(), lr.requested_until) * e.daily_penalty_rate,
                    DATEDIFF(CURDATE(), lr.requested_until),
                    'unpaid',
                    '',
                    NOW(),
                    NOW()
                FROM `{lending_request_table}` lr
                INNER JOIN `{equipment_table}` e ON e.id = lr.equipment_id
                WHERE lr.requested_until < CURDATE()
                  AND lr.status IN ('approved', 'borrowed', 'overdue')
                ON DUPLICATE KEY UPDATE
                    amount = VALUES(amount),
                    days_overdue = VALUES(days_overdue),
                    updated_at = VALUES(updated_at),
                    status = CASE
                        WHEN `{penalty_table}`.status IN ('paid', 'waived') THEN `{penalty_table}`.status
                        ELSE 'unpaid'
                    END;
            END
            """
        )

        cursor.execute(
            """
            CREATE EVENT ev_refresh_overdue_penalties
            ON SCHEDULE EVERY 5 MINUTE
            STARTS CURRENT_TIMESTAMP + INTERVAL 1 MINUTE
            DO
                CALL sp_refresh_overdue_penalties()
            """
        )


def _remove_mariadb_features(apps, schema_editor):
    if not _is_mariadb(schema_editor):
        return

    equipment_table = 'equipment_equipment'
    lending_request_table = 'lending_lendingrequest'

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP EVENT IF EXISTS ev_refresh_overdue_penalties")
        cursor.execute("DROP PROCEDURE IF EXISTS sp_refresh_overdue_penalties")

        if _table_has_system_versioning(cursor, lending_request_table):
            cursor.execute(f"ALTER TABLE `{lending_request_table}` DROP SYSTEM VERSIONING")

        if _table_has_system_versioning(cursor, equipment_table):
            cursor.execute(f"ALTER TABLE `{equipment_table}` DROP SYSTEM VERSIONING")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('equipment', '0001_initial'),
        ('lending', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(_install_mariadb_features, _remove_mariadb_features),
    ]
