from django.conf.urls.defaults import *

from . import views

urlpatterns = patterns('',
    (r'^xview/$', views.xview),
)
