from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import signals, Q
from django.utils.translation import ugettext_lazy as _

from cms.models.permissionmodels import AbstractPagePermission, GlobalPagePermission


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

    def save(self, *args, **kwargs):
        super(Role, self).save(*args, **kwargs)
        # TODO: improve performance by having less queries
        covered_sites = set(site.pk
                            for gp in self.derived_global_permissions.all()
                            for site in gp.sites.all())
        for site in Site.objects.exclude(pk__in=covered_sites):
            self.add_site_specific_global_page_perm(site)

    def delete(self, *args, **kwargs):
        for global_perm in self.derived_global_permissions.all():
            # global_perm will also get deleted by cascading from global_perm.group
            global_perm.group.delete()
        return super(Role, self).delete(*args, **kwargs)

    def _get_permissions_dict(self):
        return dict((key, getattr(self, key))
                    for key in get_permission_fields())

    def add_site_specific_global_page_perm(self, site):
        site_group = self.group
        permissions = self.group.permissions.all()
        site_group.pk = None
        site_group.name = '%s-%d-%s' % (site.domain, site.pk, site_group.name)
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
        return self.derived_global_permissions.get(sites=site).group


def get_permission_keys():
    permission_keys = []
    for field in AbstractPagePermission._meta.fields:
        if isinstance(field, models.BooleanField) and field.name.startswith('can_'):
            permission_keys.append(field.name)
    return permission_keys


def create_role_groups(instance, **kwargs):
    site = instance
    if kwargs['created']:
        for role in Role.objects.all():
            role.add_site_specific_global_page_perm(site)


signals.post_save.connect(create_role_groups, sender=Site)
