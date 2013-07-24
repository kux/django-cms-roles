from django.conf.urls import patterns, url

urlpatterns = patterns('cmsroles.views',
    url(r'^usersetup/$', 'user_setup', name='user_setup'),
)
