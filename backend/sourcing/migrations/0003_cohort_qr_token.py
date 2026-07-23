from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sourcing', '0002_program_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='cohort',
            name='qr_token',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
    ]
