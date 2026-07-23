import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('sourcing', '0003_cohort_qr_token'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrainingContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('code', models.CharField(blank=True, max_length=50)),
                ('category', models.CharField(choices=[('common', 'Chung / Nền tảng'), ('foh', 'FOH'), ('boh', 'BOH'), ('management', 'Quản lý')], default='common', max_length=20)),
                ('target_roles', models.CharField(blank=True, max_length=200)),
                ('is_prerequisite', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('note', models.TextField(blank=True)),
                ('order', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='training_contents', to='accounts.tenant')),
            ],
            options={'ordering': ['order', 'name']},
        ),
    ]
