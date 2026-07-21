import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('employees', '0004_employee_interview'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecruitmentSource',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('csv_url', models.URLField(blank=True, max_length=1000)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='recruitment_source', to='accounts.tenant')),
            ],
        ),
    ]
