from django.contrib.auth.models import User
from django.contrib.sites.models import Site

from cmsroles.models import Role


def is_site_admin(user):
    """Returns whether user is a site admin. A user is a site admin
    if he has add/change/delete permissions over django.contrib.auth.models.User
    """
    if user.is_superuser:
        return True
    return user.is_staff and 'auth.change_user' in user.get_all_permissions()


def is_site_admin_group(group):
    """Returns whether group gives site admin rights to the users
    that belong to it.
    """
    permissions = set([(p.codename, p.content_type.model_class())
                       for p in group.permissions.all()])
    return (u'change_user', User) in permissions


def get_administered_sites(user):
    """Returns a list of sites on which user has administrative rights"""
    if user.is_superuser:
        return [s for s in Site.objects.all()]
    sites = []

    def lookup_sites(auth_obj):
        for global_perm in auth_obj.globalpagepermission_set.\
                prefetch_related('sites').all():
            sites.extend(global_perm.sites.all())

    for group in user.groups.all():
        if is_site_admin_group(group):
            lookup_sites(group)
    lookup_sites(user)

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
