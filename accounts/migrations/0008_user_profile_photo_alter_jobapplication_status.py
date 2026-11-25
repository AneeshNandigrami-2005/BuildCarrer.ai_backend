# Generated manually to support profile photo and updated application statuses.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_alter_jobapplication_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile_photo",
            field=models.FileField(blank=True, null=True, upload_to="profile_photos/"),
        ),
        migrations.AlterField(
            model_name="jobapplication",
            name="status",
            field=models.CharField(
                choices=[
                    ("Applied", "Applied"),
                    ("CV Selected", "CV Selected"),
                    ("1st Round Qualified", "1st Round Qualified"),
                    ("2nd Round Qualified", "2nd Round Qualified"),
                    ("Selected", "Selected"),
                    ("Rejected", "Rejected"),
                    ("Withdrawn", "Withdrawn"),
                ],
                default="Applied",
                max_length=30,
            ),
        ),
    ]
