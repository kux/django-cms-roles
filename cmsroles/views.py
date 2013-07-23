from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django import forms
from django.forms.formsets import formset_factory, BaseFormSet
from django.http import HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext

from cmsroles.siteadmin import get_administered_sites, \
    get_site_users, is_site_admin
from cmsroles.models import Role


class UserForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.filter(is_staff=True))
    role = forms.ModelChoiceField(queryset=Role.objects.all())


class AddUserForm(UserCreationForm):
    role = forms.ModelChoiceField(queryset=Role.objects.all())

    def save(self, commit=True):
        user = super(AddUserForm, self).save(commit=False)
        if commit:
            user.save()
        return user


class BaseUserFormSet(BaseFormSet):

    def clean(self):
        if any(self.errors):
            return
        users = set()
        for form in self.forms:
            user = form.cleaned_data['user']
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
    site_pk = request.GET.get('site')
    current_site, administered_sites = _get_user_sites(request.user, site_pk)
    new_user_form = AddUserForm()
    UserFormSet = formset_factory(UserForm, formset=BaseUserFormSet, extra=1)
    if request.method == 'POST':
        user_formset = UserFormSet(request.POST, request.FILES)
        if user_formset.is_valid():
            for form in user_formset.forms:
                user = form.cleaned_data['user']
                role = form.cleaned_data['role']
                # TODO: are there any cases where a user might belong to
                #       non-role generated groups?
                user.groups.clear()
                user.groups.add(role.get_site_specific_group(current_site))
            next_action = request.POST['next']
            if next_action == u'continue':
                return HttpResponseRedirect(reverse(user_setup))
            else:
                return HttpResponseRedirect('/admin/')
    else:
        available_users = get_site_users(current_site)
        initial_data = [
            {'user': user, 'role': role}
            for user, role in available_users.iteritems()]
        user_formset = UserFormSet(initial=initial_data)
    opts = {'app_label': 'cmsroles'}
    context = {'opts': opts,
               'app_label': 'Cmsroles',
               'administered_sites': administered_sites,
               'current_site': current_site,
               'user_formset': user_formset,
               'user': request.user,
               'new_user_form': new_user_form}
    return render_to_response('admin/cmsroles/user_setup.html', context,
                              context_instance=RequestContext(request))
