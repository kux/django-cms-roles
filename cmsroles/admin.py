from django.contrib.auth.models import Group, User
from django.contrib import admin
from django.db import models
from django.forms import ModelForm, ModelChoiceField
from django.db.models import Q

from cmsroles.models import Role, get_permission_fields
from cmsroles.siteadmin import is_site_admin, get_administered_sites
from cms.models.permissionmodels import PageUser, PageUserGroup, GlobalPagePermission


class RoleForm(ModelForm):
    group = ModelChoiceField(
        queryset=Group.objects.filter(
            globalpagepermission__isnull=True),
        required=True)

    class Meta:
        model = Role
        fields = tuple(['name', 'group', 'is_site_wide'] + get_permission_fields())


class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'group', 'is_site_wide'] + get_permission_fields()
    form = RoleForm

    def __init__(self, *args, **kwargs):
        super(RoleAdmin, self).__init__(*args, **kwargs)

    def get_actions(self, request):
        """Overriden get_actions so we don't allow bulk deletions.
        Bulk deletions would leave orphaned auto-generated groups.
        """
        actions = super(RoleAdmin, self).get_actions(request)
        actions.pop('delete_selected', None)
        return actions


class UserSetup(models.Model):
    """Dummy model without any associated db table.
    It's only purpose is to provide an additional
    entry in the admin index.
    """
    class Meta:
        verbose_name_plural = 'User Setup'
        permissions = ()


class UserSetupAdmin(admin.ModelAdmin):

    class Meta:
        model = UserSetup

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # should be available only to superusers and to site admins that
        #   have at least one site under their control
        user = request.user
        return is_site_admin(user) and len(get_administered_sites(user)) > 0


admin.site.register(Role, RoleAdmin)
admin.site.register(UserSetup, UserSetupAdmin)


# admin extensions
def _get_registered_modeladmin(model):
    return type(admin.site._registry[model])


class ExtendedGroupAdmin(_get_registered_modeladmin(Group)):

    @classmethod
    def get_filtered_queryset(cls, qs=None):
        if qs is None:
            qs = Group.objects.all()
        return qs.filter(globalpagepermission__role__isnull=True).distinct()

    def queryset(self, request):
        return self.get_filtered_queryset(
            super(ExtendedGroupAdmin, self).queryset(request))


admin.site.unregister(Group)
admin.site.register(Group, ExtendedGroupAdmin)


class ExtendedGlobalPagePermssionAdmin(_get_registered_modeladmin(GlobalPagePermission)):

    def queryset(self, request):
        qs = super(ExtendedGlobalPagePermssionAdmin, self).queryset(request)
        return qs.filter(role__isnull=True)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.rel.to == Group:
            kwargs["queryset"] = ExtendedGroupAdmin.get_filtered_queryset()
        return super(ExtendedGlobalPagePermssionAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs)


admin.site.unregister(GlobalPagePermission)
admin.site.register(GlobalPagePermission, ExtendedGlobalPagePermssionAdmin)


class ExtendedUserAdmin(_get_registered_modeladmin(User)):

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.rel.to == Group:
            kwargs["queryset"] = ExtendedGroupAdmin.get_filtered_queryset()
        return super(ExtendedUserAdmin, self).formfield_for_manytomany(
            db_field, request, **kwargs)


admin.site.unregister(User)
admin.site.register(User, ExtendedUserAdmin)


class ExtendedPageUserAdmin(_get_registered_modeladmin(PageUser)):

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.rel.to == Group:
            kwargs["queryset"] = ExtendedGroupAdmin.get_filtered_queryset()
        return super(ExtendedPageUserAdmin, self).formfield_for_manytomany(
            db_field, request, **kwargs)


admin.site.unregister(PageUser)
admin.site.register(PageUser, ExtendedPageUserAdmin)


class ExtendedPageUserGroupAdmin(_get_registered_modeladmin(PageUserGroup)):

    def queryset(self, request):
        qs = ExtendedGroupAdmin.get_filtered_queryset(
            super(ExtendedPageUserGroupAdmin, self).queryset(request))


admin.site.unregister(PageUserGroup)
admin.site.register(PageUserGroup, ExtendedPageUserGroupAdmin)
