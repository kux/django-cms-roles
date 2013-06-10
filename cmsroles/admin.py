from django.contrib import admin
from django.db import models

from cmsroles.models import Role, get_permission_fields


class RoleAdmin(admin.ModelAdmin):
    # TODO: make group field mandatory
    list_display = ['name', 'group'] + get_permission_fields()
    fields = tuple(['name', 'group'] + get_permission_fields())
    exclude = ('derived_global_permissions',)


class UserSetup(models.Model):
    """Dummy model without any associated db table.
    It's only purpose is to provide an additional
    entry in the admin index.
    """
    class Meta:
        verbose_name_plural = 'User Setup'


admin.site.register(Role, RoleAdmin)
admin.site.register(UserSetup)
