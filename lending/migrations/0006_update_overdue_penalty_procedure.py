from django.db import migrations


def _is_mariadb(schema_editor):
    connection = schema_editor.connection
    return connection.vendor == 'mysql' and getattr(connection, 'mysql_is_mariadb', False)


def _install_procedure(apps, schema_editor):
    if not _is_mariadb(schema_editor):
        return

    equipment_table = 'equipment_equipment'
    lending_request_table = 'lending_lendingrequest'
    penalty_table = 'lending_penalty'

    with schema_editor.connection.cursor() as cursor:
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
                    product_penalty_amount,
                    days_overdue,
                    status,
                    note,
                    created_at,
                    updated_at
                )
                SELECT
                    lr.id,
                    DATEDIFF(CURDATE(), lr.requested_until) * e.daily_penalty_rate,
                    0.00,
                    DATEDIFF(CURDATE(), lr.requested_until),
                    'unpaid',
                    CONCAT(
                        'Late penalty: RM ',
                        DATEDIFF(CURDATE(), lr.requested_until) * e.daily_penalty_rate,
                        ' (',
                        DATEDIFF(CURDATE(), lr.requested_until),
                        ' day(s) x RM ',
                        e.daily_penalty_rate,
                        ').'
                    ),
                    NOW(),
                    NOW()
                FROM `{lending_request_table}` lr
                INNER JOIN `{equipment_table}` e ON e.id = lr.equipment_id
                WHERE lr.requested_until < CURDATE()
                  AND lr.status IN ('approved', 'borrowed', 'overdue')
                ON DUPLICATE KEY UPDATE
                    days_overdue = VALUES(days_overdue),
                    amount = CASE
                        WHEN `{penalty_table}`.status IN ('paid', 'waived') THEN `{penalty_table}`.amount
                        ELSE VALUES(amount) + `{penalty_table}`.product_penalty_amount
                    END,
                    note = CASE
                        WHEN `{penalty_table}`.status IN ('paid', 'waived') THEN `{penalty_table}`.note
                        WHEN `{penalty_table}`.product_penalty_amount > 0 THEN CONCAT(
                            VALUES(note),
                            ' Product return penalty: RM ',
                            `{penalty_table}`.product_penalty_amount,
                            '.'
                        )
                        ELSE VALUES(note)
                    END,
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


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('lending', '0005_penalty_product_penalty_amount'),
    ]

    operations = [
        migrations.RunPython(_install_procedure, migrations.RunPython.noop),
    ]
