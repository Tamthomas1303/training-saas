from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sourcing', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='program',
            name='mode',
            field=models.CharField(
                choices=[('offline', 'Offline (điểm danh trực tiếp)'), ('online', 'Online (học/thi trên nền tảng)')],
                default='offline', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='program',
            name='source_url',
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
