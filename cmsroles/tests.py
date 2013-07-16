from django.test import TestCase
from django.test.client import Client
from django.contrib.auth.models import User, Group, Permission
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError


from cms.models.permissionmodels import GlobalPagePermission

from cmsroles.models import Role
from cmsroles.siteadmin import is_site_admin, get_administered_sites


class BasicSiteSetupTest(TestCase):

    def setUp(self):
        User.objects.create_superuser(
            username='root', password='root',
            email='root@roto.com')

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
        joe = User.objects.create(username='joe', is_staff=True)
        joe.groups.add(admin_role.get_site_specific_group(foo_site))
        joe.groups.add(admin_role.get_site_specific_group(bar_site))
        george = User.objects.create(username='george', is_staff=True)
        george.groups.add(developer_role.get_site_specific_group(foo_site))
        robin = User.objects.create(username='robin', is_staff=True)
        robin.groups.add(editor_role.get_site_specific_group(foo_site))
        robin.groups.add(developer_role.get_site_specific_group(bar_site))
        jack = User.objects.create(username='jack', is_staff=True)
        jack.groups.add(admin_role.get_site_specific_group(bar_site))
        criss = User.objects.create(username='criss', is_staff=True)
        criss.groups.add(editor_role.get_site_specific_group(bar_site))
        vasile = User.objects.create(username='vasile', is_staff=True)
        vasile.groups.add(editor_role.get_site_specific_group(bar_site))

    def test_is_admin(self):
        self._create_simple_setup()
        joe = User.objects.get(username='joe')
        self.assertTrue(is_site_admin(joe))

    def test_get_administered_sites(self):
        self._create_simple_setup()
        joe = User.objects.get(username='joe')
        administered_sites = get_administered_sites(joe)
        self.assertEquals(set([s.domain for s in administered_sites]),
                          set(['foo.site.com', 'bar.site.com']))
        jack = User.objects.get(username='jack')
        administered_sites = get_administered_sites(jack)
        self.assertEquals([s.domain for s in administered_sites],
                          ['bar.site.com'])

    def test_not_accessible_for_non_siteadmins(self):
        joe = User.objects.create_user(
            username='joe', password='x', email='joe@mata.com')
        joe.is_staff = True
        joe.save()
        self.client.login(username='joe', password='x')
        response = self.client.get('/admin/cmsroles/usersetup/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(any('/admin/?next=/admin/cmsroles/usersetup/' in value
                            for header, value in response.items()))

    def test_403_for_siteadmins_with_no_site(self):
        joe = User.objects.create_user(
            username='joe', password='x', email='joe@mata.com')
        joe.is_staff = True
        site_admin_perms = Permission.objects.filter(content_type__model='user')
        for perm in site_admin_perms:
            joe.user_permissions.add(perm)
        joe.save()
        self.client.login(username='joe', password='x')
        response = self.client.get('/admin/cmsroles/usersetup/')
        self.assertEqual(response.status_code, 403)

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

    def test_role_deletion(self):
        self._create_simple_setup()
        group_count = Group.objects.count()
        site_count = Site.objects.count()
        developer_role = Role.objects.get(name='developer')
        developer_role.delete()
        after_deletion_group_count = Group.objects.count()
        # check that the groups that were implicitly
        # created for each site also got deleted
        self.assertEqual(after_deletion_group_count, group_count - site_count)

    def test_generated_group_names(self):
        foo_site = Site.objects.create(name='foo.site.com', domain='foo.site.com')
        bar_site = Site.objects.create(name='bar.site.com', domain='bar.site.com')
        base_site_admin_group = self._create_site_adimin_group()
        admin_role = Role.objects.create(name='site admin', group=base_site_admin_group)
        generated_group = admin_role.get_site_specific_group(foo_site)
        self.assertEqual(generated_group.name, '%s-%d-%s' % (
                foo_site.domain, foo_site.pk, base_site_admin_group.name))
        generated_group = admin_role.get_site_specific_group(bar_site)
        self.assertEqual(generated_group.name, '%s-%d-%s' % (
                bar_site.domain, bar_site.pk, base_site_admin_group.name))

    def test_changes_in_role_reflected_in_global_perms(self):
        self._create_simple_setup()
        developer_role = Role.objects.get(name='developer')
        can_add = developer_role.can_add
        for gp in developer_role.derived_global_permissions.all():
            self.assertEqual(gp.can_add, developer_role.can_add)
        developer_role.can_add = not can_add
        developer_role.save()
        for gp in developer_role.derived_global_permissions.all():
            self.assertEqual(gp.can_add, developer_role.can_add)

    def test_changes_in_base_group_reflected_in_generated_ones(self):

        def check_permissions(role, permission_set):
            for gp in role.derived_global_permissions.all():
                self.assertSetEqual(
                    set([perm.pk for perm in gp.group.permissions.all()]),
                    permission_set)

        self._create_simple_setup()
        site_admin_base_group = Group.objects.get(name='site_admin')
        perms = site_admin_base_group.permissions.all()
        self.assertTrue(len(perms) > 0)
        admin_role = Role.objects.get(name='site admin')
        check_permissions(admin_role, set(p.pk for p in perms))
        # remove all permissions
        site_admin_base_group.permissions = []
        site_admin_base_group = Group.objects.get(pk=site_admin_base_group.pk)
        self.assertEqual(list(site_admin_base_group.permissions.all()), [])
        admin_role = Role.objects.get(pk=admin_role.pk)
        check_permissions(admin_role, set())
        #and set them back again
        site_admin_base_group.permissions = perms
        self.assertTrue(len(perms) > 0)
        admin_role = Role.objects.get(name='site admin')
        check_permissions(admin_role, set(p.pk for p in perms))
