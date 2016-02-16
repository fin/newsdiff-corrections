from django.conf.urls import url

urlpatterns = [
    url(r'^insert/', 'thesis_stats.views.insert', name='stat_insert'),
]

