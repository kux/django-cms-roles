django-cms-roles
================

Wrapper over django-cms' permissions that allows for easy user management by defining roles that span multiple sites.


Notes
-----
When deleting:
* a role all auto-generated global page permissions and groups are deleted
* bulk deletion in the admin is disabled so that we don't leave any auto-generated
    groups and global page permissions
