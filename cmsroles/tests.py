from django.test import TestCase
from django.contrib.auth.models import User, Group, Permission
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError

from cms.models.permissionmodels import GlobalPagePermission, PagePermission
from cms.api import create_page

from cmsroles.models import Role
from cmsroles.siteadmin import (is_site_admin, get_administered_sites, get_site_users,
                                get_site_admin_required_permission)


class BasicSiteSetupTest(TestCase):

    def setUp(self):
        User.objects.create_superuser(
            username='root', password='root',
            email='root@roto.com')       

    def _create_site_admin_group(self):
        site_admin_group = Group.objects.create(name='site_admin')
        site_admin_group.permissions.add(get_site_admin_required_permission())
        return site_admin_group

    def _create_simple_setup(self):
        """Creates two sites, three roles and five users that have
        different foles within the two sites.

        Many tests depend on this particular setup. If you want to add
        more users, sites, roles, create a new method which calls this one...
        """
        foo_site = Site.objects.create(name='foo.site.com', domain='foo.site.com')
        bar_site = Site.objects.create(name='bar.site.com', domain='bar.site.com')
        base_site_admin_group = self._create_site_admin_group()
        admin_role = Role.objects.create(
            name='site admin', group=base_site_admin_group,
            is_site_wide=True)
        base_editor_group = Group.objects.create(name='editor')
        editor_role = Role.objects.create(
            name='editor', group=base_editor_group,
            is_site_wide=True)
        base_developer_group = Group.objects.create(name='developer')
        developer_role = Role.objects.create(
            name='developer', group=base_developer_group,
            is_site_wide=True)
        base_writer_group = Group.objects.create(name='writer')
        writer_role = Role.objects.create(
            name='writer', group=base_writer_group,
            is_site_wide=False)
        joe = User.objects.create(username='joe', is_staff=True)
        admin_role.grant_to_user(joe, foo_site)
        admin_role.grant_to_user(joe, bar_site)
        george = User.objects.create(username='george', is_staff=True)
        developer_role.grant_to_user(george, foo_site)
        robin = User.objects.create(username='robin', is_staff=True)
        editor_role.grant_to_user(robin, foo_site)
        developer_role.grant_to_user(robin, bar_site)
        jack = User.objects.create(username='jack', is_staff=True)
        admin_role.grant_to_user(jack, bar_site)
        criss = User.objects.create(username='criss', is_staff=True)
        editor_role.grant_to_user(criss, bar_site)
        vasile = User.objects.create(username='vasile', is_staff=True)
        editor_role.grant_to_user(vasile, bar_site)
        bob = User.objects.create(username='bob', is_staff=True)
        create_page('master', 'template.html', language='en', site=bar_site)
        writer_role.grant_to_user(bob, bar_site)

    def _create_non_site_wide_role(self):
        writer_group = Group.objects.create(name='writer')
        writer_role = Role.objects.create(
            name='writer', group=writer_group, is_site_wide=False,
            can_add=False)
        foo_site = Site.objects.create(name='foo.site.com', domain='foo.site.com')
        user = User.objects.create(username='gigi', is_staff=True)
        create_page('master', 'template.html', language='en', site=foo_site)
        writer_role.grant_to_user(user, foo_site)
        return writer_role, user, foo_site

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

    def test_get_administered_sites_with_user_referencing_glob_page_(self):
        foo_site = Site.objects.create(name='foo.site.com', domain='foo.site.com')
        admin_user = User.objects.create(username='gigi', password='baston')
        site_admin_perms = Permission.objects.filter(content_type__model='user')
        for perm in site_admin_perms:
            admin_user.user_permissions.add(perm)
        gpp = GlobalPagePermission.objects.create(user=admin_user)
        gpp.sites.add(foo_site)
        administered_sites = get_administered_sites(admin_user)
        self.assertEquals(len(administered_sites), 1)
        self.assertEquals([s.pk for s in administered_sites], [foo_site.pk])

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
        joe.user_permissions.add(get_site_admin_required_permission())
        joe.save()
        self.client.login(username='joe', password='x')
        response = self.client.get('/admin/cmsroles/usersetup/')
        self.assertEqual(response.status_code, 403)

    def test_global_page_permission_implicitly_created(self):
        site_admin_group = self._create_site_admin_group()
        site_admin = Role.objects.create(
            name='site admin', group=site_admin_group,
            is_site_wide=True)
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

    def test_assign_user_to_non_site_wide_role(self):
        writer_role, user, foo_site = self._create_non_site_wide_role()
        page_perms = PagePermission.objects.filter(user=user)
        self.assertEqual(len(page_perms), 1)
        users = writer_role.users(foo_site)
        self.assertItemsEqual([u.pk for u in users], [user.pk])

    def test_switch_role_form_site_wide_to_non_wide(self):
        writer_role, user, foo_site = self._create_non_site_wide_role()
        writer_role.is_site_wide = True
        writer_role.save()
        self.assertFalse(writer_role.derived_page_permissions.exists())
        self.assertTrue(writer_role.derived_global_permissions.exists())
        users = writer_role.users(foo_site)
        self.assertItemsEqual([u.pk for u in users], [user.pk])
        self.assertTrue(writer_role.derived_global_permissions.filter(group__user=user).exists())

    def test_cant_create_two_roles_based_on_the_same_group(self):
        site_admin_group = self._create_site_admin_group()
        Role.objects.create(
            name='site admin', group=site_admin_group,
            is_site_wide=True)
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

    def _setup_site_deletion(self, site_name):
        site = Site.objects.create(name=site_name, domain=site_name)
        base_site_admin_group = self._create_site_admin_group()
        admin_role = Role.objects.create(
            name='site admin', group=base_site_admin_group,
            is_site_wide=True)
        return site, admin_role

    def test_site_deletion_no_roles(self):
        # site delete must work even if there are no roles
        Site.objects.create(
            name='foo.site.com', domain='foo.site.com').delete()

    def test_site_deletion_with_roles(self):
        foo_site, role  = self._setup_site_deletion('foo.site.com')
        generated_group = role.get_site_specific_group(foo_site)
        foo_site.delete()
        with self.assertRaises(GlobalPagePermission.DoesNotExist):
            role.get_site_specific_group(foo_site)
        with self.assertRaises(Group.DoesNotExist):
            Group.objects.get(id=generated_group.id)

    def test_site_deletion_with_deleted_site_specific_group(self):
        foo_site, role  = self._setup_site_deletion('foo.site.com')
        role.get_site_specific_group(foo_site).delete()
        foo_site.delete()

    def test_site_deletion_with_deleted_site_specific_permission(self):
        foo_site, role  = self._setup_site_deletion('foo.site.com')
        role.derived_global_permissions.filter(sites=foo_site).update(group=None)
        Site.objects.get(id=foo_site.id).delete()

    def test_generated_group_names(self):
        foo_site = Site.objects.create(name='foo.site.com', domain='foo.site.com')
        bar_site = Site.objects.create(name='bar.site.com', domain='bar.site.com')
        base_site_admin_group = self._create_site_admin_group()
        admin_role = Role.objects.create(name='site admin', group=base_site_admin_group,
                                         is_site_wide=True)
        generated_group = admin_role.get_site_specific_group(foo_site)
        self.assertEqual(generated_group.name, Role.group_name_pattern.format(
            site_id=foo_site.pk, group_id=base_site_admin_group.pk))
        generated_group = admin_role.get_site_specific_group(bar_site)
        self.assertEqual(generated_group.name, Role.group_name_pattern.format(
            site_id=bar_site.pk, group_id=base_site_admin_group.pk))

    def test_site_group_perms_change_on_role_group_change(self):
        foo_site = Site.objects.create(
            name='foo.site.com', domain='foo.site.com')
        g1 = Group.objects.create(name='g1')
        g1.permissions = Permission.objects.filter(
            content_type__model='page')
        g2 = Group.objects.create(name='g2')
        g2.permissions = Permission.objects.filter(
            content_type__model='user')
        role = Role.objects.create(name='editor', group=g1)
        self.assertItemsEqual(
            role.group.permissions.values_list('id', flat=True),
            g1.permissions.values_list('id', flat=True))
        role.group = g2
        role.save()
        self.assertItemsEqual(
            Role.objects.get(
                id=role.id).group.permissions.values_list('id', flat=True),
            g2.permissions.values_list('id', flat=True))

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

    def test_changes_in_role_relected_in_page_perms(self):
        writer_role, _, _ = self._create_non_site_wide_role()
        self.assertEqual(writer_role.derived_page_permissions.count(), 1)
        for page_perm in writer_role.derived_page_permissions.all():
            self.assertFalse(page_perm.can_add)
        writer_role.can_add = True
        writer_role.save()
        for page_perm in writer_role.derived_page_permissions.all():
            self.assertTrue(page_perm.can_add)

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

    def test_role_validation_two_roles_same_group(self):
        Site.objects.create(name='foo.site.com', domain='foo.site.com')
        base_site_admin_group = self._create_site_admin_group()
        Role.objects.create(name='site admin 1', group=base_site_admin_group)
        role_from_same_group = Role(name='site admin 2', group=base_site_admin_group)
        with self.assertRaises(ValidationError):
            role_from_same_group.clean()

    def test_role_validation_role_from_derived_group(self):
        Site.objects.create(name='foo.site.com', domain='foo.site.com')
        base_site_admin_group = self._create_site_admin_group()
        role = Role.objects.create(name='site admin 1', group=base_site_admin_group,
                                   is_site_wide=True)
        # there should be at least one derived group for
        # the foo.site.com created above
        derived_group = role.derived_global_permissions.all()[0].group
        role_from_derived_group = Role(name='site admin 2', group=derived_group)
        with self.assertRaises(ValidationError):
            role_from_derived_group.clean()

    def _get_foo_site_objs(self):
        foo_site = Site.objects.get(name='foo.site.com', domain='foo.site.com')
        joe = User.objects.get(username='joe')
        admin = Role.objects.get(name='site admin')
        george = User.objects.get(username='george')
        developer = Role.objects.get(name='developer')
        robin = User.objects.get(username='robin')
        editor = Role.objects.get(name='editor')
        return foo_site, joe, admin, george, developer, robin, editor

    def test_user_formset_submit_change_roles(self):
        self._create_simple_setup()
        # users assigned to foo.site.com:
        # joe: site admin, george: developer, robin: editor
        foo_site, joe, _, george, developer, robin, editor = self._get_foo_site_objs()
        self.client.login(username='root', password='root')
        response = self.client.post('/admin/cmsroles/usersetup/?site=%s' % foo_site.pk, {
                # management form
                u'form-MAX_NUM_FORMS': [u''],
                u'form-TOTAL_FORMS': [u'3'],
                u'form-INITIAL_FORMS': [u'3'],
                # change joe to a developer
                u'form-0-user': [unicode(joe.pk)],
                u'form-0-role': [unicode(developer.pk)],
                u'form-0-site': [unicode(foo_site.pk)],
                # george to an editor
                u'form-1-user': [unicode(george.pk)],
                u'form-1-role': [unicode(editor.pk)],
                u'form-1-site': [unicode(foo_site.pk)],
                # robin stays the same
                u'form-2-user': [unicode(robin.pk)],
                u'form-2-role': [unicode(editor.pk)],
                u'form-2-site': [unicode(foo_site.pk)],
                u'next': [u'continue']}
                )
        self.assertEqual(response.status_code, 302)
        users_to_roles = get_site_users(foo_site)
        user_pks_to_role_pks = dict((u.pk, r.pk) for u, r in users_to_roles.iteritems())
        self.assertEqual(len(user_pks_to_role_pks), 3)
        self.assertEqual(user_pks_to_role_pks[joe.pk], developer.pk)
        self.assertEqual(user_pks_to_role_pks[george.pk], editor.pk)
        self.assertEqual(user_pks_to_role_pks[robin.pk], editor.pk)

    def test_user_formset_submit_unassign_user(self):
        self._create_simple_setup()
        # users assigned to foo.site.com:
        # joe: site admin, george: developer, robin: editor
        foo_site, joe, admin, george, developer, _, _ = self._get_foo_site_objs()
        self.client.login(username='root', password='root')
        response = self.client.post('/admin/cmsroles/usersetup/?site=%s' % foo_site.pk, {
                # management form
                u'form-MAX_NUM_FORMS': [u''],
                u'form-TOTAL_FORMS': [u'2'],
                u'form-INITIAL_FORMS': [u'2'],
                # joe remains an admin
                u'form-0-user': [unicode(joe.pk)],
                u'form-0-role': [unicode(admin.pk)],
                u'form-0-site': [unicode(foo_site.pk)],
                # george remains a developer
                u'form-1-user': [unicode(george.pk)],
                u'form-1-role': [unicode(developer.pk)],
                u'form-1-site': [unicode(foo_site.pk)],
                # but robin gets removed !!
                u'next': [u'continue']}
                )
        self.assertEqual(response.status_code, 302)
        users_to_roles = get_site_users(foo_site)
        user_pks_to_role_pks = dict((u.pk, r.pk) for u, r in users_to_roles.iteritems())
        self.assertEqual(len(user_pks_to_role_pks), 2)
        self.assertEqual(user_pks_to_role_pks[joe.pk], admin.pk)
        self.assertEqual(user_pks_to_role_pks[george.pk], developer.pk)

    def test_user_formset_submit_assign_new_user(self):
        self._create_simple_setup()
        # users assigned to foo.site.com:
        # joe: site admin, george: developer, robin: editor
        foo_site, joe, admin, george, developer, robin, editor = self._get_foo_site_objs()
        criss = User.objects.get(username='criss')
        self.client.login(username='root', password='root')
        response = self.client.post('/admin/cmsroles/usersetup/?site=%s' % foo_site.pk, {
                # management form
                u'form-MAX_NUM_FORMS': [u''],
                u'form-TOTAL_FORMS': [u'4'],
                u'form-INITIAL_FORMS': [u'4'],
                # joe remains an admin
                u'form-0-user': [unicode(joe.pk)],
                u'form-0-role': [unicode(admin.pk)],
                u'form-0-site': [unicode(foo_site.pk)],
                # george remains a developer
                u'form-1-user': [unicode(george.pk)],
                u'form-1-role': [unicode(developer.pk)],
                u'form-1-site': [unicode(foo_site.pk)],
                # robin remains an editor
                u'form-2-user': [unicode(robin.pk)],
                u'form-2-role': [unicode(editor.pk)],
                u'form-2-site': [unicode(foo_site.pk)],
                # but we also add criss to foo_site
                u'form-3-user': [unicode(criss.pk)],
                u'form-3-role': [unicode(admin.pk)],
                u'form-3-site': [unicode(foo_site.pk)],
                u'next': [u'continue']}
                )
        self.assertEqual(response.status_code, 302)
        users_to_roles = get_site_users(foo_site)
        user_pks_to_role_pks = dict((u.pk, r.pk) for u, r in users_to_roles.iteritems())
        self.assertEqual(len(user_pks_to_role_pks), 4)
        self.assertEqual(user_pks_to_role_pks[joe.pk], admin.pk)
        self.assertEqual(user_pks_to_role_pks[george.pk], developer.pk)
        self.assertEqual(user_pks_to_role_pks[robin.pk], editor.pk)
        self.assertEqual(user_pks_to_role_pks[criss.pk], admin.pk)
