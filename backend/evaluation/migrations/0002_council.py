import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evaluation', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluationcriteria',
            name='position_group',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='evaluationcriteria',
            name='dept_role',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='evaluation',
            name='dish_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.CreateModel(
            name='Council',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('skill', 'Đánh giá tay nghề'), ('interview', 'Phỏng vấn')], max_length=20)),
                ('status', models.CharField(choices=[('open', 'Đang mở'), ('finalized', 'Đã chốt')], default='open', max_length=20)),
                ('note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='councils_created', to='accounts.user')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='councils', to='employees.employee')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='councils', to='accounts.tenant')),
            ],
        ),
        migrations.CreateModel(
            name='CouncilMember',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('guest_name', models.CharField(blank=True, max_length=255)),
                ('guest_dept', models.CharField(blank=True, max_length=100)),
                ('dept_role', models.CharField(blank=True, max_length=20)),
                ('token', models.CharField(blank=True, db_index=True, max_length=64)),
                ('submitted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('council', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='members', to='evaluation.council')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='council_members', to='accounts.tenant')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='council_memberships', to='accounts.user')),
            ],
        ),
        migrations.AddField(
            model_name='evaluation',
            name='council',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evaluations', to='evaluation.council'),
        ),
        migrations.AddField(
            model_name='evaluation',
            name='council_member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evaluations', to='evaluation.councilmember'),
        ),
    ]
