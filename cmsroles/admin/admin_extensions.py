from django.contrib.auth.models import Group, User
from django.contrib import admin
from django.db.models import Q

from cms.models.permissionmodels import GlobalPagePermission


def _get_registered_modeladmin(model):
    return type(admin.site._registry[model])


class ExtendedGroupAdmin(_get_registered_modeladmin(Group)):

    @classmethod
    def get_role_filtered_queryset(cls):
        return Q(globalpagepermission__role__isnull=True)

    def queryset(self, request):
        qs = super(ExtendedGroupAdmin, self).queryset(request)
        return qs.filter(ExtendedGroupAdmin.get_role_filtered_queryset())


admin.site.unregister(Group)
admin.site.register(Group, ExtendedGroupAdmin)


class ExtendedGlobalPagePermssionAdmin(_get_registered_modeladmin(GlobalPagePermission)):

    def queryset(self, request):
        qs = super(ExtendedGlobalPagePermssionAdmin, self).queryset(request)
        return qs.filter(role__isnull=True)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "group":
            kwargs["queryset"] = Group.objects.filter(
                ExtendedGroupAdmin.get_role_filtered_queryset())
        return super(ExtendedGlobalPagePermssionAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs)


admin.site.unregister(GlobalPagePermission)
admin.site.register(GlobalPagePermission, ExtendedGlobalPagePermssionAdmin)


class ExtendedUserAdmin(_get_registered_modeladmin(User)):

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "groups":
            kwargs["queryset"] = Group.objects.filter(
                ExtendedGroupAdmin.get_role_filtered_queryset())
        return super(ExtendedUserAdmin, self).formfield_for_manytomany(
            db_field, request, **kwargs)


admin.site.unregister(User)
admin.site.register(User, ExtendedUserAdmin)
