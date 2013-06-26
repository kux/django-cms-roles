from django.contrib import admin
from django.contrib.auth.models import Group
from django.db import models
from django.forms import ModelForm, ModelChoiceField

from cmsroles.models import Role, get_permission_fields


class RoleForm(ModelForm):
    group = ModelChoiceField(
        queryset=Group.objects.filter(
            globalpagepermission__isnull=True),
        required=True)

    class Meta:
        model = Role
        fields = tuple(['name', 'group'] + get_permission_fields())


class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'group'] + get_permission_fields()
    form = RoleForm

    def __init__(self, *args, **kwargs):
        super(RoleAdmin, self).__init__(*args, **kwargs)

    def get_actions(self, request):
        """Overriden get_actions so we don't allow bulk deletions.
        Bulk deletions would leave orphaned auto-generated groups.
        """
        actions = super(RoleAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


class UserSetup(models.Model):
    """Dummy model without any associated db table.
    It's only purpose is to provide an additional
    entry in the admin index.
    """
    class Meta:
        verbose_name_plural = 'User Setup'


admin.site.register(Role, RoleAdmin)
admin.site.register(UserSetup)
