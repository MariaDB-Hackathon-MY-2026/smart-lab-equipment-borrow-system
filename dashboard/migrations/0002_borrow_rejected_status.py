from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='borrow',
            name='status',
            field=models.CharField(
                choices=[
                    ('Active', 'Active'),
                    ('Returned', 'Returned'),
                    ('Overdue', 'Overdue'),
                    ('Pending', 'Pending'),
                    ('Rejected', 'Rejected'),
                ],
                default='Active',
                max_length=20,
            ),
        ),
    ]
