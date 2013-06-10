from django.shortcuts import render_to_response

from cmsroles.models import Role
from cmsroles.siteadmin import get_administered_sites, users_assigned_to_site


def _get_site_users(site):
    users = []
    for role in Role.objects.all():
        users.extend(role.users_with_role(site))
    return users



# TODO: add user authentication and authorization on this view
# TODO: check user is site admin
def user_setup(request):
    if request.METHOD == 'POST':
        pass
    else:
        # Minimum context for rendering the admin surroundings
        sites = get_administered_sites(request.user)
        if sites:
            current_site = sites[0]
            available_users = users_assigned_to_site(current_site)
        else:
            current_site = None
            available_users = []

        opts = {'app_label': 'cmsroles'}
        context = {'opts': opts,
                   'app_label': 'Cmsroles',
                   'user': request.user,
                   'sites': sites,
                   'current_site': current_site,
                   'available_users': available_users}

    # TODO: User RequestContext
    return render_to_response('admin/cmsroles/user_setup.html', context)
