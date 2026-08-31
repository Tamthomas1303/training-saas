# Khung noi dung dao tao cap O - Buoc 1 (Prompt_KhungNoiDung_CapO_Buoc1.md).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_gradingconfig_kpi_mode'),
        ('checklist', '0008_document_standard_minutes'),
        ('employees', '0019_seed_positions'),
    ]

    operations = [
        migrations.CreateModel(
            name='CurriculumItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.CharField(max_length=20)),
                ('is_shared', models.BooleanField(default=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('phase', models.CharField(blank=True, max_length=20, null=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='curriculum_items', to='checklist.document')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='curriculum_items', to='accounts.tenant')),
            ],
            options={
                'ordering': ['position', 'order'],
                'unique_together': {('tenant', 'position', 'document')},
            },
        ),
    ]
