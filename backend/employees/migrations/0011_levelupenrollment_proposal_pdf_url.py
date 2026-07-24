from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0010_talentreview'),
    ]

    operations = [
        migrations.AddField(
            model_name='levelupenrollment',
            name='proposal_pdf_url',
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
