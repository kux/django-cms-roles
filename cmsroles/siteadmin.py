from django.contrib.auth.models import User
from django.contrib.sites.models import Site

from cmsroles.models import Role


def is_site_admin(user):
    """Returns whether user is a site admin. A user is a site admin
    if he has add/change/delete permissions over django.contrib.auth.models.User
    """
    if user.is_superuser:
        return True
    req_perm = set(['auth.add_user', 'auth.delete_user', 'auth.change_user'])
    return user.is_staff and req_perm.issubset(user.get_all_permissions())


def is_site_admin_group(group):
    """Returns whether group gives site admin rights to the users
    that belong to it.
    """
    permissions = set([(p.codename, p.content_type.model_class())
                       for p in group.permissions.all()])
    req_perm = set([(u'add_user', User), (u'delete_user', User),
                    (u'change_user', User)])
    return req_perm.issubset(permissions)


def get_administered_sites(user):
    """Returns a list of sites on which user has administrative rights"""
    if user.is_superuser:
        return [s for s in Site.objects.all()]
    sites = []
    for group in user.groups.all():
        if is_site_admin_group(group) and group.globalpagepermission_set.exists():
            # TODO: assert this is a single global page perm?
            print group
            for global_perm in group.globalpagepermission_set.all():
                print global_perm
                # TODO: assert this is a single site?
                sites.extend(global_perm.sites.all())
    return sites


def get_site_users(site):
    """Returns a dictionary containing all users mapped to their role
    that belong to site.
    """
    users_to_roles = {}
    for role in Role.objects.all():
        for user in role.users(site):
            users_to_roles[user] = role
    return users_to_roles
