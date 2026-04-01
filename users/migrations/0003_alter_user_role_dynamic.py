from django.db import migrations, models


def sync_role_objects(apps, schema_editor):
    Role = apps.get_model('users', 'Role')
    User = apps.get_model('users', 'User')

    for default_role in ['ADMIN', 'TEAM_LEAD', 'EMPLOYEE']:
        Role.objects.get_or_create(name=default_role)

    for user in User.objects.all():
        if user.role_obj_id and (not user.role or user.role != user.role_obj.name):
            user.role = user.role_obj.name
            user.save(update_fields=['role'])
            continue

        if user.role and not user.role_obj_id:
            role, _ = Role.objects.get_or_create(name=user.role)
            user.role_obj_id = role.id
            user.save(update_fields=['role_obj'])


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_role_user_role_obj'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.RunPython(sync_role_objects, migrations.RunPython.noop),
    ]
