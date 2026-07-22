import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evaluation', '0002_council'),
        ('employees', '0006_levelupenrollment'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluation',
            name='enrollment',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='evaluations', to='employees.levelupenrollment',
            ),
        ),
    ]
