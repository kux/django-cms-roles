from django.contrib.auth.models import User, Group
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import signals, Q
from django.utils.translation import ugettext_lazy as _

from cms.models.permissionmodels import AbstractPagePermission, GlobalPagePermission
from parse import parse


def get_permission_fields():
    permission_keys = []
    for field in AbstractPagePermission._meta.fields:
        if isinstance(field, models.BooleanField) and field.name.startswith('can_'):
            permission_keys.append(field.name)
    return permission_keys


class Role(AbstractPagePermission):

    class Meta:
        abstract = False
        app_label = 'cmsroles'
        verbose_name = _('role')
        verbose_name_plural = _('roles')

    group_name_pattern = 'cmsroles-generated-{site_id}-{group_id}'

    name = models.CharField(max_length=50, unique=True)
    derived_global_permissions = models.ManyToManyField(
        GlobalPagePermission, blank=True, null=True)
    # TODO: writer role -- add support for non-global permissions role

    def __unicode__(self):
        return self.name

    def clean(self):
        filter_clause = Q(group=self.group) | Q(derived_global_permissions__group=self.group)
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

    def save(self, *args, **kwargs):
        old_group = Role.objects.get(id=self.id).group_id if self.id else None
        super(Role, self).save(*args, **kwargs)

        group_changed = old_group is not None and old_group != self.group_id
        if group_changed:
            self._update_site_groups_permissions()

        # TODO: improve performance by having less queries
        derived_global_permissions = self.derived_global_permissions.all()
        covered_sites = set(derived_global_permissions.values_list('sites', flat=True))
        for site in Site.objects.exclude(pk__in=covered_sites):
            self.add_site_specific_global_page_perm(site)
        permissions = self._get_permissions_dict()
        for gp in derived_global_permissions:
            for key, value in permissions.iteritems():
                setattr(gp, key, value)
            gp.save()

    def delete(self, *args, **kwargs):
        for global_perm in self.derived_global_permissions.all():
            # global_perm will also get deleted by cascading from global_perm.group
            global_perm.group.delete()
        return super(Role, self).delete(*args, **kwargs)

    def _get_permissions_dict(self):
        return dict((key, getattr(self, key))
                    for key in get_permission_fields())

    def add_site_specific_global_page_perm(self, site):
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

    def all_users(self):
        """Returns all users having this role."""
        return User.objects.filter(groups__globalpagepermission__role=self)

    def users(self, site):
        """Returnes all users having this role in the given site."""
        gp = self.derived_global_permissions.filter(sites=site)
        return User.objects.filter(groups__globalpagepermission=gp)

    def get_site_specific_group(self, site):
        # TODO: enforce there is one global page perm per site
        #       the derived global page permissions should always have
        #       a single site, but there's nothing stopping super-users
        #       from messing around with them
        return self.derived_global_permissions.get(sites=site).group


def create_role_groups(instance, **kwargs):
    site = instance
    if kwargs['created']:
        for role in Role.objects.all():
            role.add_site_specific_global_page_perm(site)


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


def delete_role_groups(instance, **kwargs):
    for site_group in getattr(instance, '_role_groups', []):
        site_group.delete()


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


signals.post_save.connect(create_role_groups, sender=Site)

signals.pre_delete.connect(set_role_groups_to_delete, sender=Site)
signals.post_delete.connect(delete_role_groups, sender=Site)

signals.m2m_changed.connect(update_site_specific_groups, sender=Group.permissions.through)
