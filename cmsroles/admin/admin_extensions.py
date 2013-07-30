from django.contrib.auth.models import Group
from django.contrib import admin

from cms.models.permissionmodels import GlobalPagePermission


def _get_registered_modeladmin(model):
    return type(admin.site._registry[model])


class ExtendedGlobalPagePermssionAdmin(_get_registered_modeladmin(GlobalPagePermission)):

    def queryset(self, request):
        qs = super(ExtendedGlobalPagePermssionAdmin, self).queryset(request)
        return qs.filter(role__isnull=True)


admin.site.unregister(GlobalPagePermission)
admin.site.register(GlobalPagePermission, ExtendedGlobalPagePermssionAdmin)


class ExtendedGroupAdmin(_get_registered_modeladmin(Group)):

    def queryset(self, request):
        qs = super(ExtendedGroupAdmin, self).queryset(request)
        return qs.filter(globalpagepermission__role__isnull=True)


admin.site.unregister(Group)
admin.site.register(Group, ExtendedGroupAdmin)
