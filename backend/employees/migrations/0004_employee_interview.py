from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0003_employee_probation_result_pdf_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='interview_score',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='employee',
            name='interview_result',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
