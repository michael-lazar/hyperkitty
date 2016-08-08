# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

from django.db import migrations, models, IntegrityError


PROVIDERS_MAP = {
    "fedora": "fedora",
    "yahoo": "openid",
}


def populate_emailaddress(apps, schema_editor):
    # All current users have verified their email. Populate the EmailAddress
    # and mark is as such.
    User = apps.get_model("auth", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")
    for user in User.objects.all():
        try:
            EmailAddress.objects.create(
                email=user.email, user=user,
                verified=True, primary=True,
                )
        except IntegrityError as e:
            print("Can't create EmailAddress for %s: %s"
                  % (user.username, e))


#def migrate_social_users(apps, schema_editor):
#    # Migrate the Social Auth association to AllAuth
#    UserSocialAuth = apps.get_model("social_auth", "UserSocialAuth")
#    SocialAccount = apps.get_model("socialaccount", "SocialAccount")
#    for user_socialauth in UserSocialAuth.objects.all():
#        if user_socialauth.provider not in PROVIDERS_MAP:
#            continue  # unsupported provider
#        try:
#            SocialAccount.objects.create(
#                    provider=PROVIDERS_MAP[user_socialauth.provider],
#                    uid=user_socialauth.uid,
#                    user=user_socialauth.user,
#                    last_login=user_socialauth.user.last_login,
#                    date_joined=user_socialauth.user.date_joined,
#                    extra_data='{}',
#                )
#        except IntegrityError as e:
#            print("Can't create SocialAccount for %s: %s"
#                  % (user_socialauth.uid, e))


def get_social_users_migration_sql():
    # Migrate the Social Auth association to AllAuth
    # We can't use Python because the social_auth app has been removed, and
    # thus the UserSocialAuth model isn't available.
    sql = """
        INSERT INTO socialaccount_socialaccount
            (provider, uid, user_id, last_login, date_joined, extra_data)
        SELECT
            '%(prov_to)s', uid, user_id, last_login, date_joined, '{}'
        FROM social_auth_usersocialauth usa
        JOIN auth_user ON usa.user_id = auth_user.id
        WHERE provider = '%(prov_from)s';
        """
    return [sql % {"prov_from": key, "prov_to": value}
            for key, value in PROVIDERS_MAP.items()]


class Migration(migrations.Migration):

    dependencies = [
        ('hyperkitty', '0006_thread_on_delete'),
        ('socialaccount', '0003_extra_data_default_dict'),
        ('account', '0002_email_max_length'),
    ]

    operations = [
        migrations.RunPython(populate_emailaddress),
        #migrations.RunPython(migrate_social_users),
        migrations.RunSQL(get_social_users_migration_sql()),
    ]
