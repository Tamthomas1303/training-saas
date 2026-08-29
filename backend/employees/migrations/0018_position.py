# Muc 16 Phase 1 (Prompt_Muc16_Phase1_ViTri_CauHinhMenu.md phan A) - danh muc Vi tri chuc danh.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_pushsubscription'),
        ('employees', '0017_probation_reminder_automation'),
    ]

    operations = [
        migrations.CreateModel(
            name='Position',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('zone', models.CharField(blank=True, choices=[('FOH', 'FOH (mặt tiền)'), ('BOH', 'BOH (hậu trường)')], max_length=10)),
                ('level_group', models.CharField(blank=True, choices=[('S', 'Nhân viên (S)'), ('O', 'Giám sát/Quản lý (O)'), ('P', 'Cấp trung (P)')], max_length=10)),
                ('is_active', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='positions', to='accounts.tenant')),
            ],
            options={
                'ordering': ['order', 'name'],
                'unique_together': {('tenant', 'name')},
            },
        ),
    ]
