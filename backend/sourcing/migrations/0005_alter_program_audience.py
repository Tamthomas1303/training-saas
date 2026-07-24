from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sourcing', '0004_trainingcontent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='program',
            name='audience',
            field=models.CharField(
                choices=[
                    ('source', 'Nhân sự nguồn'),
                    ('management', 'Ban quản lý (nguồn)'),
                    ('middle', 'Cấp trung (AM/KCS)'),
                    ('other', 'Khác'),
                ],
                default='source', max_length=20,
            ),
        ),
    ]
