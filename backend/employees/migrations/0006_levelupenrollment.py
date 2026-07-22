import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('employees', '0005_recruitmentsource'),
    ]

    operations = [
        migrations.CreateModel(
            name='LevelUpEnrollment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target_position', models.CharField(max_length=100)),
                ('zone', models.CharField(blank=True, max_length=10)),
                ('from_level', models.CharField(blank=True, max_length=10)),
                ('target_level', models.CharField(blank=True, max_length=10)),
                ('exam_batch', models.CharField(blank=True, max_length=20)),
                ('status', models.CharField(choices=[('registered', 'Đăng ký'), ('training', 'Đang đào tạo'), ('completed', 'Hoàn thành (lên level)'), ('failed', 'Không đạt')], default='registered', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='level_up_enrollments', to='employees.employee')),
                ('registered_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='level_up_registered', to='accounts.user')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='level_up_enrollments', to='accounts.tenant')),
            ],
        ),
    ]
