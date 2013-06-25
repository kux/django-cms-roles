"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase
from django.contrib.auth.models import User, Group, Permission
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError

from cms.models.permissionmodels import GlobalPagePermission

from cmsroles.models import Role 


class BasicSiteSetupTest(TestCase):

    def _create_site_adimin_group(self):
        site_admin_group = Group.objects.create(name='site_admin')
        site_admin_perms = Permission.objects.filter(content_type__model='user')
        for perm in site_admin_perms:
            site_admin_group.permissions.add(perm)
        return site_admin_group

    def _create_simple_setup(self):
        """Creates two sites, three roles and five users that have
        different foles within the two sites.
        """
        foo_site = Site.objects.create(name='foo.site.com', domain='foo.site.com')
        bar_site = Site.objects.create(name='bar.site.com', domain='bar.site.com')
        base_site_admin_group = self._create_site_adimin_group()
        admin_role = Role.objects.create(name='site admin', group=base_site_admin_group)
        base_editor_group = Group.objects.create(name='editor')
        editor_role = Role.objects.create(name='editor', group=base_editor_group)
        base_developer_group = Group.objects.create(name='developer')
        developer_role = Role.objects.create(name='developer', group=base_developer_group)
        joe = User.objects.create(username='joe')
        joe.groups.add(admin_role.get_site_specific_group(foo_site))
        joe.groups.add(admin_role.get_site_specific_group(bar_site))
        george = User.objects.create(username='george')
        george.groups.add(developer_role.get_site_specific_group(foo_site))
        robin = User.objects.create(username='robin')
        robin.groups.add(editor_role.get_site_specific_group(foo_site))
        robin.groups.add(developer_role.get_site_specific_group(bar_site))
        jack = User.objects.create(username='jack')
        jack.groups.add(admin_role.get_site_specific_group(bar_site))
        criss = User.objects.create(username='criss')
        criss.groups.add(editor_role.get_site_specific_group(bar_site))
        vasile = User.objects.create(username='vasile')
        vasile.groups.add(editor_role.get_site_specific_group(bar_site))

    def test_global_page_permission_implicitly_created(self):
        site_admin_group = self._create_site_adimin_group()
        site_admin = Role.objects.create(name='site admin', group=site_admin_group)
        global_page_perms = GlobalPagePermission.objects.all()
        # a global page permissions obj implicitly got created on role creation
        # for the default example.com site
        self.assertEqual(len(global_page_perms), 1)

        # when a new site is being added, a global page permisison obj specific
        # for that site must be created for all existing roles
        Site.objects.create(name='new.site.com', domain='new.site.com')
        global_page_perms = GlobalPagePermission.objects.all()
        self.assertEqual(len(global_page_perms), 2)

        for global_perm in global_page_perms:
            site_specific_group = global_perm.group
            self.assertEqual(set(site_specific_group.permissions.all()),
                             set(site_admin_group.permissions.all()))

    def test_cant_create_two_roles_based_on_the_same_group(self):
        site_admin_group = self._create_site_adimin_group()
        Role.objects.create(name='site admin', group=site_admin_group)
        with self.assertRaises(ValidationError):
            role = Role(name='site admin', group=site_admin_group)
            role.full_clean()

    def test_user_role_site_assignments(self):
        self._create_simple_setup()
        developer_role = Role.objects.get(name='developer')
        all_developers = developer_role.all_users()
        self.assertSetEqual(set(u.username for u in all_developers), set(['george', 'robin']))
        editor_role = Role.objects.get(name='editor')
        bar_site = Site.objects.get(name='bar.site.com')
        bar_editors = editor_role.users(bar_site)
        self.assertSetEqual(set(u.username for u in bar_editors), set(['criss', 'vasile']))
