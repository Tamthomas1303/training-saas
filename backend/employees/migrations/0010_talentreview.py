import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('employees', '0009_mgmtdevelopment'),
    ]

    operations = [
        migrations.CreateModel(
            name='TalentReview',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('decision', models.CharField(choices=[('pending', 'Chờ đánh giá'), ('approved', 'Duyệt vào nguồn'), ('rejected', 'Chưa sẵn sàng')], default='pending', max_length=20)),
                ('note', models.TextField(blank=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('employee', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='talent_review', to='employees.employee')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='talent_reviews_done', to='accounts.user')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='talent_reviews', to='accounts.tenant')),
            ],
        ),
    ]
