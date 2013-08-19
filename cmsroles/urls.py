from django.conf.urls import patterns, url

urlpatterns = patterns('cmsroles.views',
    url(r'^usersetup/$', 'user_setup', name='user_setup'),
    url(r'^get_page_formset/$', 'get_page_formset', name='get_page_formset'),
)
