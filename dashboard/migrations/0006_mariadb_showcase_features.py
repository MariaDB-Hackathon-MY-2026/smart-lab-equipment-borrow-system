from django.db import DatabaseError, migrations


def install_mariadb_showcase_features(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'mysql':
        return

    with connection.cursor() as cursor:
        cursor.execute('SELECT VERSION()')
        version = (cursor.fetchone() or [''])[0]

    if 'mariadb' not in str(version).lower():
        return

    statements = [
        'ALTER TABLE dashboard_equipment ADD SYSTEM VERSIONING',
        'ALTER TABLE dashboard_borrow ADD SYSTEM VERSIONING',
        """
        CREATE OR REPLACE FUNCTION borrow_penalty_amount(p_borrow_id BIGINT, p_as_of_date DATE)
        RETURNS DECIMAL(8,2)
        READS SQL DATA
        BEGIN
            DECLARE v_due_date DATE;
            DECLARE v_return_date DATE;
            DECLARE v_status VARCHAR(20);
            DECLARE v_daily_penalty DECIMAL(8,2);
            DECLARE v_effective_date DATE;

            SELECT b.due_date, b.return_date, b.status, e.daily_penalty
            INTO v_due_date, v_return_date, v_status, v_daily_penalty
            FROM dashboard_borrow b
            JOIN dashboard_equipment e ON e.id = b.equipment_id
            WHERE b.id = p_borrow_id;

            IF v_due_date IS NULL THEN
                RETURN NULL;
            END IF;

            SET v_effective_date = COALESCE(v_return_date, p_as_of_date, CURDATE());

            IF v_status NOT IN ('Overdue', 'Returned') AND v_effective_date <= v_due_date THEN
                RETURN NULL;
            END IF;

            RETURN GREATEST(DATEDIFF(v_effective_date, v_due_date), 0) * v_daily_penalty;
        END
        """,
        """
        CREATE OR REPLACE PROCEDURE refresh_overdue_borrows()
        BEGIN
            UPDATE dashboard_borrow b
            JOIN dashboard_equipment e ON e.id = b.equipment_id
            SET b.status = 'Overdue',
                b.penalty = GREATEST(DATEDIFF(CURDATE(), b.due_date), 0) * e.daily_penalty
            WHERE b.status = 'Active'
              AND b.return_date IS NULL
              AND b.due_date < CURDATE();
        END
        """,
        """
        CREATE OR REPLACE PROCEDURE finalize_borrow_return(p_borrow_id BIGINT, p_return_date DATE)
        BEGIN
            UPDATE dashboard_borrow b
            JOIN dashboard_equipment e ON e.id = b.equipment_id
            SET b.status = 'Returned',
                b.return_date = p_return_date,
                b.penalty = CASE
                    WHEN p_return_date > b.due_date THEN GREATEST(DATEDIFF(p_return_date, b.due_date), 0) * e.daily_penalty
                    ELSE NULL
                END
            WHERE b.id = p_borrow_id;
        END
        """,
        """
        CREATE OR REPLACE EVENT lendr_refresh_overdue_borrows
        ON SCHEDULE EVERY 1 HOUR
        DO CALL refresh_overdue_borrows()
        """,
    ]

    for statement in statements:
        try:
            with connection.cursor() as cursor:
                cursor.execute(statement)
        except DatabaseError:
            # Keep migrations portable when a MariaDB-specific capability is unavailable.
            continue


def uninstall_mariadb_showcase_features(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'mysql':
        return

    with connection.cursor() as cursor:
        cursor.execute('SELECT VERSION()')
        version = (cursor.fetchone() or [''])[0]

    if 'mariadb' not in str(version).lower():
        return

    statements = [
        'DROP EVENT IF EXISTS lendr_refresh_overdue_borrows',
        'DROP PROCEDURE IF EXISTS finalize_borrow_return',
        'DROP PROCEDURE IF EXISTS refresh_overdue_borrows',
        'DROP FUNCTION IF EXISTS borrow_penalty_amount',
        'ALTER TABLE dashboard_borrow DROP SYSTEM VERSIONING',
        'ALTER TABLE dashboard_equipment DROP SYSTEM VERSIONING',
    ]

    for statement in statements:
        try:
            with connection.cursor() as cursor:
                cursor.execute(statement)
        except DatabaseError:
            continue


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0005_borrowrequest_email_faculty_department'),
    ]

    operations = [
        migrations.RunPython(
            install_mariadb_showcase_features,
            uninstall_mariadb_showcase_features,
        ),
    ]
