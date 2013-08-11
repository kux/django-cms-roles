from django.contrib.auth.models import User, Group
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import signals, Q
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from cms.models.permissionmodels import (
    AbstractPagePermission, GlobalPagePermission, PagePermission)
from cms.models.pagemodel import Page
from parse import parse


def get_permission_fields():
    permission_keys = []
    for field in AbstractPagePermission._meta.fields:
        if isinstance(field, models.BooleanField) and field.name.startswith('can_'):
            permission_keys.append(field.name)
    return permission_keys


class Role(AbstractPagePermission):
    """
    When is_site_wide is True this role uses derived_global_permissions
    When is_site_wide is False this role uses derived_page_permissions

    The class invariant is that one of derived_global_permissions and
    derived_page_permissions must be empty at all times
    """

    class Meta:
        abstract = False
        app_label = 'cmsroles'
        verbose_name = _('role')
        verbose_name_plural = _('roles')
        permissions = (('user_setup', 'Can access user setup'),)

    group_name_pattern = 'cmsroles-generated-{site_id}-{group_id}'

    name = models.CharField(max_length=50, unique=True)

    is_site_wide = models.BooleanField(default=True)

    # used when is_site_wide is True
    derived_global_permissions = models.ManyToManyField(
        GlobalPagePermission, blank=True, null=True)

    # used when is_site_wide is False
    derived_page_permissions = models.ManyToManyField(
        PagePermission, blank=True, null=True)

    def __unicode__(self):
        return self.name

    def __init__(self, *args, **kwargs):
        super(Role, self).__init__(*args, **kwargs)
        self._old_group = self.group_id
        self._old_is_site_wide = self.is_site_wide

    def clean(self):
        if self.group is not None:
            filter_clause = Q(group=self.group) | (
                Q(derived_global_permissions__group=self.group) &
                Q(is_site_wide=True))
            query = Role.objects.filter(filter_clause)
            if self.pk:
                query = query.exclude(pk=self.pk)
            if query.exists():
                raise ValidationError(u'A Role for group "%s" already exists' % self.group.name)

    def _update_site_groups_permissions(self):
        new_group_permissions = self.group.permissions.all()
        global_perm_q = self.derived_global_permissions.select_related(
            'group').prefetch_related('group__permissions')
        site_groups = [global_perm.group for global_perm in global_perm_q]
        for site_group in site_groups:
            # change permissions
            site_group.permissions = new_group_permissions
            # rename group
            parsed_name = parse(self.group_name_pattern, site_group.name)
            site_group.name = self.group_name_pattern.format(
                site_id=parsed_name['site_id'], group_id=self.group.id)
            site_group.save()

    def _propagate_perm_changes(self, derived_perms):
        permissions = self._get_permissions_dict()
        for gp in derived_perms:
            for key, value in permissions.iteritems():
                setattr(gp, key, value)
            gp.save()

    def save(self, *args, **kwargs):
        super(Role, self).save(*args, **kwargs)

        if self.is_site_wide:
            group_changed = (self._old_group is not None and
                             self._old_group != self.group_id)
            if group_changed:
                self._update_site_groups_permissions()

            # TODO: improve performance by having less queries
            derived_global_permissions = self.derived_global_permissions.all()
            covered_sites = set(derived_global_permissions.values_list('sites', flat=True))
            for site in Site.objects.exclude(pk__in=covered_sites):
                self.add_site_specific_global_page_perm(site)
            self._propagate_perm_changes(derived_global_permissions)
        else:
            self._propagate_perm_changes(self.derived_page_permissions.all())

        if self.is_site_wide != self._old_is_site_wide:
            if self.is_site_wide:
                for page_perm in self.derived_page_permissions.all():
                    self.grant_to_user(page_perm.user, page_perm.page.site)
                    page_perm.delete()
            else:
                for global_page_perm in self.derived_global_permissions.all():
                    # there should be exactly one site, uness someone
                    # manually fiddled with it
                    try:
                        site = global_page_perm.sites.all()[0]
                    except IndexError:
                        continue
                    else:
                        for user in global_page_perm.group.user_set.all():
                            self.grant_to_user(user, site)
                    global_page_perm.group.delete()

    def delete(self, *args, **kwargs):
        for global_perm in self.derived_global_permissions.all():
            # global_perm will also get deleted by cascading from global_perm.group
            global_perm.group.delete()
        for page_perm in self.derived_page_permissions.all():
            page_perm.delete()
        return super(Role, self).delete(*args, **kwargs)

    def _get_permissions_dict(self):
        return dict((key, getattr(self, key))
                    for key in get_permission_fields())

    def add_site_specific_global_page_perm(self, site):
        if not self.is_site_wide:
            return
        site_group = Group.objects.get(pk=self.group.pk)
        permissions = self.group.permissions.all()
        site_group.pk = None
        site_group.name = self.group_name_pattern.format(
            site_id=site.pk, group_id=self.group.pk)
        site_group.save()
        site_group.permissions = permissions
        kwargs = self._get_permissions_dict()
        kwargs['group'] = site_group
        gp = GlobalPagePermission.objects.create(**kwargs)
        gp.sites.add(site)
        self.derived_global_permissions.add(gp)

    def grant_to_user(self, user, site):
        """Grant the given user this role for given site"""
        if self.is_site_wide:
            user.groups.add(self.get_site_specific_group(site))
        else:
            try:
                first_page = Page.objects.filter(site=site)\
                    .order_by('tree_id', 'lft')[0]
            except IndexError:
                raise ValidationError(
                    'Site needs to have at least one page '
                    'before you can grant this role to an user')
            else:
                page_permission = PagePermission(page=first_page, user=user)
                for key, value in self._get_permissions_dict().iteritems():
                    setattr(page_permission, key, value)
                page_permission.save()
                self.derived_page_permissions.add(page_permission)
                user.groups.add(self.group)

        if not user.is_staff:
            user.is_staff = True
            user.save()

    def ungrant_from_user(self, user, site):
        """Remove the given user from this role from the given site"""
        # TODO: Extract some 'state' class that implements the is/isn't site wide
        #       different strategies
        if self.is_site_wide:
            user.groups.remove(self.get_site_specific_group(site))
        else:
            for perm in self.derived_page_permissions.filter(page__site=site, user=user):
                perm.delete()
            user.groups.remove(self.group)

    def all_users(self):
        """Returns all users having this role."""
        if self.is_site_wide:
            qs = User.objects.filter(groups__globalpagepermission__role=self)
        else:
            qs = User.objects.filter(groups=self.group)
        return qs.distinct()

    def users(self, site):
        """Returnes all users having this role in the given site."""
        if self.is_site_wide:
            global_page_perm = self.derived_global_permissions.filter(sites=site)
            qs = User.objects.filter(groups__globalpagepermission=global_page_perm)
        else:
            qs = User.objects.filter(
                pagepermission__page__site=site, groups=self.group)
        return qs.distinct()

    def get_site_specific_group(self, site):
        # TODO: enforce there is one global page perm per site
        #       the derived global page permissions should always have
        #       a single site, but there's nothing stopping super-users
        #       from messing around with them
        return self.derived_global_permissions.get(sites=site).group


@receiver(signals.pre_delete, sender=Group)
def delete_role(instance, **kwargs):
    """When group that a role uses gets deleted, that role also
    and all of the auto generated page permissions and groups
    also need to be deleted. Whithout this pre_delete signal the
    role would be deleted, but the deletion would happen without going
    through the role's delete method
    """
    try:
        roles = Role.objects.filter(group=instance)
        for role in roles:
            role.delete()
    except Role.DoesNotExist:
        # we don't care about groups that don't have any roles
        # built on top of them
        pass


@receiver(signals.post_save, sender=Site)
def create_role_groups(instance, **kwargs):
    site = instance
    if kwargs['created']:
        for role in Role.objects.all():
            role.add_site_specific_global_page_perm(site)


@receiver(signals.pre_delete, sender=Site)
def set_role_groups_to_delete(instance, **kwargs):
    instance._role_groups = []
    for role in Role.objects.all():
        try:
            role_site_group = role.get_site_specific_group(instance)
        except GlobalPagePermission.DoesNotExist:
            # this might happen if site specific global page
            #   permission got deleted
            pass
        else:
            if role_site_group:
                instance._role_groups.append(role_site_group)


@receiver(signals.post_delete, sender=Site)
def delete_role_groups(instance, **kwargs):
    for site_group in getattr(instance, '_role_groups', []):
        site_group.delete()


@receiver(signals.m2m_changed, sender=Group.permissions.through)
def update_site_specific_groups(instance, **kwargs):
    group = instance
    try:
        role = Role.objects.get(group=group)
    except Role.DoesNotExist:
        return
    else:
        derived_global_permissions = role.derived_global_permissions.all()\
            .select_related('group')
        derived_groups = [gp.group for gp in derived_global_permissions]
        permissions = group.permissions.all()
        for derived_group in derived_groups:
            derived_group.permissions = permissions
