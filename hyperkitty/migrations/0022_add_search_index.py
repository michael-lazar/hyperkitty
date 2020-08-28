from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hyperkitty', '0021_add_owners_mods'),
    ]

    operations = [
        migrations.RunSQL(
            (
                'CREATE FULLTEXT INDEX hyperkitty_email_subject_search_index ON hyperkitty_email (subject)',
                'CREATE FULLTEXT INDEX hyperkitty_email_content_search_index ON hyperkitty_email (content)',
            ),
            (
                'DROP INDEX hyperkitty_email_subject_search_index ON hyperkitty_email',
                'DROP INDEX hyperkitty_email_content_search_index ON hyperkitty_email',
            )
        ),
    ]
