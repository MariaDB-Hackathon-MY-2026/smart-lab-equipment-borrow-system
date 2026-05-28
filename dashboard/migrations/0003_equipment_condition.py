from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0002_borrow_rejected_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipment',
            name='condition',
            field=models.CharField(
                choices=[
                    ('excellent', 'Excellent'),
                    ('good', 'Good'),
                    ('fair', 'Fair'),
                    ('damaged', 'Damaged'),
                    ('needs_repair', 'Needs Repair'),
                ],
                default='good',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='equipment',
            name='condition_remarks',
            field=models.TextField(blank=True),
        ),
    ]
