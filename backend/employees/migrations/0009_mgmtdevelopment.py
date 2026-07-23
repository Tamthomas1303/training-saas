import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('employees', '0008_employee_is_legacy'),
    ]

    operations = [
        migrations.CreateModel(
            name='MgmtDevelopment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target_code', models.CharField(blank=True, max_length=20)),
                ('final_status', models.CharField(blank=True, max_length=100)),
                ('employee_source', models.CharField(blank=True, max_length=100)),
                ('data', models.JSONField(blank=True, default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mgmt_dev', to='employees.employee')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mgmt_developments', to='accounts.tenant')),
            ],
        ),
    ]
