from django.contrib.auth.models import User

from cmsroles.models import Role


def is_site_admin(user):
    req_perm = set(['auth.add_user', 'auth.delete_user', 'auth.change_user'])
    return req_perm.issubset(user.get_all_permissions())


def is_site_admin_group(group):
   permissions = set([(p.codename, p.content_type.model_class())
                       for p in group.permissions.all()])
   req_perm = set([(u'add_user', User), (u'delete_user', User),
                   (u'change_user', User)])
   return req_perm.issubset(permissions)


def get_administered_sites(site_admin):
    sites = []
    for group in site_admin.groups.all():
        if is_site_admin_group(group) and group.globalpagepermission_set.exists():
            # TODO: assert this is a single global page perm?
            print group
            for global_perm in group.globalpagepermission_set.all():
                print global_perm
                # TODO: assert this is a single site?
                sites.extend(global_perm.sites.all())
                print sites
    return sites


def users_assigned_to_site(site):
    users = []
    for role in Role.objects.all():
        users.extend(role.users_with_role(site))
    return users
