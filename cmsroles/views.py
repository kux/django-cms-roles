from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django import forms
from django.forms.formsets import formset_factory, BaseFormSet
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext

from cmsroles.siteadmin import get_administered_sites, \
    get_site_users, is_site_admin
from cmsroles.models import Role


class UserForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_staff=True),
                                  required=False)
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=False)


class BaseUserFormSet(BaseFormSet):

    def clean(self):
        if any(self.errors):
            return
        users = set()
        for form in self.forms:
            user = form.cleaned_data.get('user', None)
            if user is None:
                continue
            if user in users:
                raise forms.ValidationError(
                    "A User can't have multiple roles in the same site")
            users.add(user)


def _get_user_sites(user, site_pk):
    administered_sites = get_administered_sites(user)
    if not administered_sites:
        raise PermissionDenied()

    if not site_pk:
        return (administered_sites[0], administered_sites)

    site_pk = int(site_pk)
    if all(site_pk != s.pk for s in administered_sites):
        raise PermissionDenied()
    else:
        return (next((s for s in administered_sites if site_pk == s.pk),
                     administered_sites[0]),
                administered_sites)


@user_passes_test(is_site_admin, login_url='/admin/')
def user_setup(request):
    site_pk = request.GET.get('site', None)
    current_site, administered_sites = _get_user_sites(request.user, site_pk)
    UserFormSet = formset_factory(UserForm, formset=BaseUserFormSet, extra=1)

    assigned_users = get_site_users(current_site)

    if request.method == 'POST':
        user_formset = UserFormSet(request.POST, request.FILES)
        if user_formset.is_valid():
            newly_assigned_users = []
            existing_users = []
            for form in user_formset.forms:
                user = form.cleaned_data.get('user', None)
                role = form.cleaned_data.get('role', None)
                if user is None or role is None:
                    continue
                if user not in assigned_users:
                    newly_assigned_users.append((user, role))
                else:
                    existing_users.append((user, role))
            unassigned_users = [
                (user, role) for user, role in assigned_users.iteritems()
                if user not in existing_users]
            for user, role in unassigned_users:
                user.groups.remove(role.get_site_specific_group(current_site))
            for user, role in newly_assigned_users:
                user.groups.add(role.get_site_specific_group(current_site))
            for user, new_role in existing_users:
                previous_role = assigned_users[user]
                user.groups.remove(previous_role.get_site_specific_group(current_site))
                user.groups.add(new_role.get_site_specific_group(current_site))

            next_action = request.POST['next']
            if next_action == u'continue':
                return HttpResponseRedirect(reverse(user_setup))
            else:
                return HttpResponseRedirect('/admin/')
    else:
        initial_data = [
            {'user': user, 'role': role}
            for user, role in assigned_users.iteritems()]
        user_formset = UserFormSet(initial=initial_data)
    opts = {'app_label': 'cmsroles'}
    context = {'opts': opts,
               'app_label': 'Cmsroles',
               'administered_sites': administered_sites,
               'current_site': current_site,
               'user_formset': user_formset,
               'user': request.user}
    return render_to_response('admin/cmsroles/user_setup.html', context,
                              context_instance=RequestContext(request))
