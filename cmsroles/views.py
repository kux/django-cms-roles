from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django import forms
from django.forms.formsets import formset_factory, BaseFormSet
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext, loader, Context
from django.utils.encoding import smart_unicode
from django.utils import simplejson

from cms.models.pagemodel import Page
from cms.models.permissionmodels import PagePermission

from cmsroles.siteadmin import get_administered_sites, \
    get_site_users, is_site_admin
from cmsroles.models import Role


class UserChoiceField(forms.ModelChoiceField):

    def label_from_instance(self, obj):
        if obj.first_name and obj.last_name and obj.email:
            return u'%s %s (%s)' % (obj.first_name, obj.last_name, obj.email)
        elif obj.email:
            return obj.email
        else:
            return smart_unicode(obj)


class UserForm(forms.Form):
    user = UserChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False)
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=False)
    current_site = forms.ModelChoiceField(
        queryset=Site.objects.all(),
        widget=forms.HiddenInput())
    is_site_wide = forms.BooleanField(widget=forms.HiddenInput())

    def clean(self):
        cleaned_data = super(UserForm, self).clean()
        user = cleaned_data.get('user', None)
        role = cleaned_data.get('role', None)
        if (user is None) != (role is None):
            raise forms.ValidationError('Both user and role need to be set')
        if role is not None and not role.is_site_wide:
            site = self.cleaned_data.get('current_site', None)
            if not Page.objects.filter(site=site).exists():
                raise forms.ValidationError(
                    'Site needs to have at least one page '
                    'before you can grant this role to an user')

        return cleaned_data


class BaseUserFormSet(BaseFormSet):

    def clean(self):
        if any(self.errors):
            return
        users = set()
        for form in self.forms:
            user = form.cleaned_data.get('user', None)
            role = form.cleaned_data.get('role', None)
            if user is None:
                continue
            if user in users:
                raise forms.ValidationError(
                    "User %s has multiple roles. "
                    "A User can't have multiple roles in the same site"
                    % user.username)
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


def _get_site_pk(request):
    """Get's the current site's pk by first checking for a
    GET request parameter. If that's unavailable it uses
    the current request's Host header
    """
    site_pk = request.GET.get('site', None)
    if site_pk is not None:
        return site_pk

    host = request.META.get('HTTP_HOST', None)
    if host is not None:
        try:
            site_pk = Site.objects.get(domain=host).pk
        except Site.DoesNotExist:
            pass
    return site_pk


def _update_site_users(current_site, assigned_users, submitted_users, user_pages):
    newly_assigned_users = []
    existing_users = []
    for user, role in submitted_users.iteritems():
        if user not in assigned_users:
            newly_assigned_users.append((user, role))
        else:
            existing_users.append((user, role))

    unassigned_users = [
        (user, role) for user, role in assigned_users.iteritems()
        if user not in existing_users]

    for user, role in unassigned_users:
        role.ungrant_from_user(user, current_site)
    for user, role in newly_assigned_users:
        if not role.is_site_wide:
            pages = user_pages[user]
        else:
            pages = None
        role.grant_to_user(user, current_site, pages)
    for user, new_role in existing_users:
        previous_role = assigned_users[user]
        previous_role.ungrant_from_user(user, current_site)
        if not role.is_site_wide:
            pages = user_pages[user]
        else:
            pages = None
        new_role.grant_to_user(user, current_site, pages)


def _get_user_pages(request, PageFormSet, user):
    prefix = 'user-%d' % user.pk
    page_formset = PageFormSet(
        request.POST, request.FILES,
        prefix=prefix)
    pages = []
    if page_formset.is_valid():
        for page_form in page_formset:
            page = page_form.cleaned_data.get('page', None)
            if page is not None:
                pages.append(page)
    return pages


def _get_redirect(request, site_pk):
    next_action = request.POST['next']
    if next_action == u'continue':
        if site_pk is not None:
            next_url = '%s?site=%s' % (reverse(user_setup), site_pk)
        else:
            next_url = reverse(user_setup)
        return HttpResponseRedirect(next_url)
    else:
        return HttpResponseRedirect('/admin/')


def _build_user_pages_formsets(PageFormSet, current_site, assigned_users):
    page_formsets = {}
    site_permissions = PagePermission.objects.select_related().filter(
        page__site=current_site, role__isnull=False)
    user_perms = {}
    for page_perm in site_permissions:
        if page_perm.user is not None:
            # it should never be None unless someone manually changed the page perm
            # from the Change Page view
            user_perms.setdefault(page_perm.user, []).append(page_perm.page)
    for user, role in assigned_users.iteritems():
        if not role.is_site_wide:
            initial_data = []
            for page in user_perms[user]:
                initial_data.append({'page': page})
            page_formset = PageFormSet(initial=initial_data,
                                       prefix='user-%d' % user.pk)
            page_formsets[user.pk] = page_formset
    return page_formsets


@user_passes_test(is_site_admin, login_url='/admin/')
def get_page_formset(request): 
    site_pk = _get_site_pk(request)
    current_site, administered_sites = _get_user_sites(request.user, site_pk)

    class PageForm(forms.Form):
        page = forms.ModelChoiceField(
            queryset=Page.objects.filter(site=current_site))

    PageFormSet = formset_factory(PageForm, formset=BaseFormSet, extra=1)

    user_pk = request.GET.get('user')
    role_pk = request.GET.get('role')
    role = Role.objects.get(pk=role_pk)
    user = User.objects.get(pk=user_pk)
    if role.is_site_wide:
        return ''  # someone changed the role into being site wide the meanwhile
    page_perms = role.derived_page_permissions.filter(
        page__site=current_site,
        user=user)
    initial_data = []
    for page_perm in page_perms:
        initial_data.append({'page': page_perm.page})
    page_formset = PageFormSet(initial=initial_data,
                               prefix='user-%d' % user.pk)
    rendered_formset = loader.get_template(
        'admin/cmsroles/page_formset.html').render(
        Context({'page_formset': page_formset}))
    response = {'page_formset': rendered_formset}
    return HttpResponse(simplejson.dumps(response),
                        content_type="application/json")


@user_passes_test(is_site_admin, login_url='/admin/')
def user_setup(request):
    site_pk = _get_site_pk(request)
    current_site, administered_sites = _get_user_sites(request.user, site_pk)
    UserFormSet = formset_factory(UserForm, formset=BaseUserFormSet, extra=1)

    assigned_users = get_site_users(current_site)

    if request.method == 'POST':
        user_formset = UserFormSet(request.POST, request.FILES,
                                   prefix='user-roles')
        user_pages = {}
        if user_formset.is_valid():
            submitted_users = {}
            for form in user_formset.forms:
                user = form.cleaned_data.get('user', None)
                role = form.cleaned_data.get('role', None)
                if user is None and role is None:
                    continue
                submitted_users[user] = role
            _update_site_users(current_site, assigned_users, submitted_users,
                               user_pages)
            return _get_redirect(request, site_pk)
    else:
        initial_data = [
            {'user': user, 'role': role, 'current_site': current_site,
             'is_site_wide': role.is_site_wide}
            for user, role in assigned_users.iteritems()]
        user_formset = UserFormSet(initial=initial_data, prefix='user-roles')
    context = {'opts': {'app_label': 'cmsroles'},
               'app_label': 'Cmsroles',
               'administered_sites': administered_sites,
               'current_site': current_site,
               'user_formset': user_formset,
               'user': request.user}
    return render_to_response('admin/cmsroles/user_setup.html', context,
                              context_instance=RequestContext(request))
