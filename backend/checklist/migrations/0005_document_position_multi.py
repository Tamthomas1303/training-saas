from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('checklist', '0004_document_brand_document_code_document_position_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='document',
            name='position',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
