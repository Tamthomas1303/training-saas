from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0007_hrsyncsource'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='is_legacy',
            field=models.BooleanField(default=False),
        ),
    ]
