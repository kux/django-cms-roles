django-cms-roles
================

Wrapper over django-cms' permissions that allows for easy user management by defining roles that span multiple sites.


Reason
------
When having a django-cms setup with more than a dozen sites, working with the default permissions can be quite painful.

The typical use case is that you have different groups of users. 
As an example, let's consider:
* you need these two user roles: site admins and content writers.
* you have three sites: A, B and C

If you want to create a site admin for site A you need to do the following:
* create a django group named 'site admin for site A'
* create the new user and assign him to the previously created group
* create a global page permission which does the actual mapping from the previously created group to site A

It's easy to notice that the number of django groups you will need is:
```number of user roles * number of sites```

Having a setup with 5 roles and 20 sites results in having to maintain 100 django groups!!

If at some point you need to update one of the roles by adding additional permissions,
you then have to update each one of the site specific groups. Keeping all of these
groups in sync would be quite painful and error prone.

Roles
-----
This app provides a new ```Role``` class that is built on top of the cms ```AbstractPagePermission```

A Role references a django group and adds cms specific permissions on top of it.

On User Setup page you can assign users to different roles within different sites.
In this [example](https://github.com/kux/django-cms-roles/blob/master/User_Setup.png)
user 'Foo Bar' is given the 'writer' role on 'test.site.com'.

A role can function in two modes:
* site wide (is_site_wide = True)
* on a page by page basis (is_site_wide = False)

Site wide roles
---------------
Under the hood a Role object maintains a list of auto generated global page permissions
and django groups. The number of auto generated global page permissions and django groups
is equal to the ```number of roles * number of sites```. These auto generated groups and
global page permissions are hidden from the admin interface so that users don't accidentally
change them thus causing them to become out of sync.

A Role objects maintains the auto generated global page permissions and django groups by doing
the following:
* whenever a new site is added the a site specific django group and global page permission
  for each role will be auto created
* when a new role is added, a site specific django group and global page permission
  for each site will be created
* when a site or role is deleted, the site/role specific django groups and global page permissions
  are deleted
* when a cms specific permission from a Role object is updated (ex: untick ```can_publish```)
  all of the auto generated global page permissions are updated
* when a django group referenced by a Role is updated all of the auto generated django groups
  are also updated

For a visual explanation of how this workd, check out the following
[diagram](https://github.com/kux/django-cms-roles/blob/master/user_setup_diagram.png)


Page by page roles
------------------
When giving an user a role you will also need to specify the pages on which that role applies.
This is the equivalent of creating PagePermission objects by using the cms' 'Change Page' view.

No global page permissions or django groups need to be auto generated when functioning in this mode.
The role will maintain a list of ```PagePermission```s


**Note**: For understanding the inner workings of django-cms-roles it would be worth to check the
django-cms' permissions [documentation](http://django-cms.readthedocs.org/en/latest/advanced/permissions_reference.html)
