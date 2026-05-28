from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_borrowrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='borrowrequest',
            name='email',
            field=models.EmailField(default='', max_length=254),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='borrowrequest',
            name='faculty_department',
            field=models.CharField(blank=True, default='', max_length=120),
            preserve_default=False,
        ),
    ]
