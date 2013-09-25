from optparse import make_option

from django.core.management.base import BaseCommand

from cms.models.permissionmodels import PagePermission

from cmsroles.models import Role


class Command(BaseCommand):

    help = u'Looks for unmanaged page permissions that grant rights ' +\
        'to users that belong to a group that a non site wide role ' +\
        'is based on. Those page permissions are then added to the ' +\
        'role\'s derived_page_permissions thus making them managed\n\n' +\
        'managed page permissions: page permission objects that exist in ' +\
        'a role\'s derived_page_permissions list \n' +\
        'unmanaged page permissions: page permission objects that were ' +\
        'created by users using the Page Permissions section from the ' +\
        '\'Change page\' view (i.e. not through user setup) '

    option_list = BaseCommand.option_list + (
        make_option('--role', dest='role',
            help='Which role should the page permissions be managed by'),
        )

    def handle(self, *args, **options):
        role_name = options['role']
        role = Role.objects.get(name=role_name)
        if role.is_site_wide:
            raise ValueError('Role must not be site wide')
        other_roles = Role.objects.exclude(name=role_name)
        group = role.group
        unmamanged_page_perms = PagePermission.objects.filter(
            role=None, user__groups=group)
        self.errors = []
        for page_perm in unmamanged_page_perms:
            user = page_perm.user
            site = page_perm.page.site
            for other_role in other_roles:
                if user in other_role.users(site):
                    self.errors.append(
                        (u'Unable to manage page permission %s because user ' +\
                             '%s already belongs to role %s on site %s') % (
                                page_perm, user, other_role, site.domain))
                    break
            else:
                role.derived_page_permissions.add(page_perm)
        for error in self.errors:
            print error
                            


