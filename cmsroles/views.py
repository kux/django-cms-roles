from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django import forms
from django.forms.formsets import formset_factory
from django.http import HttpResponseNotAllowed
from django.shortcuts import render_to_response
from django.template import RequestContext

from cmsroles.siteadmin import get_administered_sites, \
    get_site_users, is_site_admin
from cmsroles.models import Role


class UserForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields['user'] = forms.ModelChoiceField(queryset=User.objects.all())
        self.fields['role'] = forms.ModelChoiceField(queryset=Role.objects.all())


@user_passes_test(is_site_admin, login_url='/admin/')
def user_setup(request):
    administered_sites = get_administered_sites(request.user)
    site_pk = request.GET.get('site')
    if not site_pk:
        current_site = administered_sites[0]
    else:
        site_pk = int(site_pk)
        if all(site_pk != s.pk for s in administered_sites):
            return HttpResponseNotAllowed()
        else:
            current_site = next((s for s in administered_sites if site_pk == s.pk),
                                administered_sites[0])

    UserFormset = formset_factory(UserForm, extra=0)
    if request.method == 'POST':
        user_formset = UserFormset(request.POST, request.FILES)
        if user_formset.is_valid():
            pass
    else:
        available_users = get_site_users(current_site)
        initial_data = [
            {'user': user, 'role': role}
            for user, role in available_users.iteritems()]
        user_formset = UserFormset(initial=initial_data)

        user_formset = UserFormset(initial=initial_data)
    opts = {'app_label': 'cmsroles'}
    context = {'opts': opts,
               'app_label': 'Cmsroles',
               'administered_sites': administered_sites,
               'current_site': current_site,
               'user_formset': user_formset,
               'user': request.user,
               'available_users': available_users}
    return render_to_response('admin/cmsroles/user_setup.html', context,
                              context_instance=RequestContext(request))
