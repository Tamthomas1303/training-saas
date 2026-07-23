import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('employees', '0006_levelupenrollment'),
    ]

    operations = [
        migrations.CreateModel(
            name='HrSyncSource',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[
                    ('lichsu', 'Data_LichSu (nhân sự cũ)'),
                    ('backup', 'DB_BACKUP (nhân sự mới từ 1/7)'),
                    ('lotrinh', 'Quanly_Lotrinh (vị trí đã pass cấp S)'),
                    ('bql', 'Daotao_BQL (đào tạo/đánh giá cấp O)'),
                    ('danhgia', 'Input_DanhGia_BQL (đánh giá cấp O)'),
                    ('courses', 'Raw_Data_Khoa_Hoc (tham gia khóa)'),
                    ('malop', 'Ma_Khoa_Hoc (danh mục khóa)'),
                ], max_length=20)),
                ('csv_url', models.URLField(blank=True, max_length=1000)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hr_sync_sources', to='accounts.tenant')),
            ],
            options={'unique_together': {('tenant', 'kind')}},
        ),
    ]
