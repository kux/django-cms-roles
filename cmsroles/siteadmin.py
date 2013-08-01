from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site

from cmsroles.models import Role


def get_site_admin_required_permission():
    return Permission.objects.get(content_type__model='role', codename='user_setup')


def is_site_admin(user):
    """Returns whether user is a site admin. A user is a site admin
    if he has add/change/delete permissions over django.contrib.auth.models.User
    """
    if user.is_superuser:
        return True
    req_perm_obj = get_site_admin_required_permission()
    req_perm = '%s.%s' % (req_perm_obj.content_type.app_label,
                          req_perm_obj.codename)
    return user.is_staff and req_perm in user.get_all_permissions()


def is_site_admin_group(group):
    """Returns whether group gives site admin rights to the users
    that belong to it.
    """
    return get_site_admin_required_permission() in group.permissions.all()


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
