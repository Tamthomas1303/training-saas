import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        ('employees', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Program',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('audience', models.CharField(choices=[('source', 'Nhân sự nguồn'), ('management', 'Quản lý cấp trung'), ('other', 'Khác')], default='source', max_length=20)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='programs', to='accounts.tenant')),
            ],
        ),
        migrations.CreateModel(
            name='ProgramContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_no', models.IntegerField(blank=True, null=True)),
                ('topic', models.CharField(blank=True, max_length=255)),
                ('content', models.CharField(max_length=500)),
                ('doc_url', models.URLField(blank=True, max_length=500)),
                ('order', models.IntegerField(default=0)),
                ('program', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contents', to='sourcing.program')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='program_contents', to='accounts.tenant')),
            ],
            options={'ordering': ['order']},
        ),
        migrations.CreateModel(
            name='Cohort',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('location', models.CharField(blank=True, max_length=255)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('open', 'Đang mở đăng ký'), ('ongoing', 'Đang đào tạo'), ('closed', 'Đã kết thúc')], default='open', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cohorts_created', to='accounts.user')),
                ('program', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cohorts', to='sourcing.program')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cohorts', to='accounts.tenant')),
            ],
        ),
        migrations.CreateModel(
            name='CohortSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_no', models.IntegerField(blank=True, null=True)),
                ('title', models.CharField(blank=True, max_length=255)),
                ('date', models.DateField(blank=True, null=True)),
                ('start_time', models.TimeField(blank=True, null=True)),
                ('end_time', models.TimeField(blank=True, null=True)),
                ('location', models.CharField(blank=True, max_length=255)),
                ('qr_token', models.CharField(blank=True, db_index=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('cohort', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='sourcing.cohort')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cohort_sessions', to='accounts.tenant')),
            ],
            options={'ordering': ['date', 'session_no']},
        ),
        migrations.CreateModel(
            name='Enrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('registered', 'Đăng ký'), ('studying', 'Đang học'), ('completed', 'Hoàn thành'), ('failed', 'Không đạt')], default='registered', max_length=20)),
                ('result', models.CharField(blank=True, max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('added_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cohort_enrollments_added', to='accounts.user')),
                ('cohort', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='sourcing.cohort')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cohort_enrollments', to='employees.employee')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cohort_enrollments', to='accounts.tenant')),
            ],
            options={'unique_together': {('cohort', 'employee')}},
        ),
        migrations.CreateModel(
            name='Attendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('present', models.BooleanField(default=True)),
                ('method', models.CharField(choices=[('self', 'Tự quét QR'), ('manual', 'Người phụ trách')], default='self', max_length=10)),
                ('checked_in_at', models.DateTimeField(blank=True, null=True)),
                ('enrollment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='sourcing.enrollment')),
                ('marked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendances_marked', to='accounts.user')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='sourcing.cohortsession')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='accounts.tenant')),
            ],
            options={'unique_together': {('session', 'enrollment')}},
        ),
        migrations.CreateModel(
            name='ContentProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('done', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('content', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progress_entries', to='sourcing.programcontent')),
                ('enrollment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='content_progress', to='sourcing.enrollment')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='content_progress', to='accounts.tenant')),
            ],
            options={'unique_together': {('enrollment', 'content')}},
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('body', models.TextField(blank=True)),
                ('link', models.CharField(blank=True, max_length=255)),
                ('category', models.CharField(blank=True, max_length=50)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='accounts.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='accounts.user')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
