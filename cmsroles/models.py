from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import signals
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
    # TODO: on delete also delete global page permissions and site groups
    derived_global_permissions = models.ManyToManyField(
        GlobalPagePermission, blank=True, null=True)
    # TODO: writer role -- add support for non -global permissions role

    def __unicode__(self):
        return self.name

    def clean(self):
        if Role.objects.filter(group=self.group).exists():
            raise ValidationError('A Role for this group already exists')

    def save(self, *args, **kwargs):
        super(Role, self).save(*args, **kwargs)
        # TODO: improve performance by having less queries
        covered_sites = set(site.pk
                            for gp in self.derived_global_permissions.all()
                            for site in gp.sites())
        for site in Site.objects.exclude(pk__in=covered_sites):
            self.add_global_page_perm_to_role(site)

    def _get_permissions_dict(self):
        return dict((key, getattr(self, key))
                    for key in get_permission_fields())

    def add_global_page_perm_to_role(self, site):
        site_group = self.group
        permissions = self.group.permissions.all()
        site_group.pk = None
        # TODO: check name is valid. site names are not unique!!
        site_group.name = '%s-%s' % (site.domain, site_group.name)
        site_group.save()
        site_group.permissions = permissions
        kwargs = self._get_permissions_dict()
        kwargs['group'] = site_group
        gp = GlobalPagePermission.objects.create(**kwargs)
        gp.sites.add(site)
        self.derived_global_permissions.add(gp)

    def all_users(self):
        return User.objects.filter(groups__globalpagepermission__role=self)

    def users(self, site):
        gp = self.derived_global_permissions.filter(sites=site)
        return User.objects.filter(groups__globalpagepermission=gp)


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
            role.add_global_page_perm_to_role(site)


signals.post_save.connect(create_role_groups, sender=Site)
