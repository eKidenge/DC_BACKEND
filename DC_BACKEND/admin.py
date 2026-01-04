from django.contrib import admin
from django.contrib.auth.models import Group

# Unregister default Group model if not needed
admin.site.unregister(Group)

# Custom admin site configuration
admin.site.site_header = "Expert Consultation Platform Admin"
admin.site.site_title = "Expert Platform Admin"
admin.site.index_title = "Dashboard Administration"

# Import all admin configurations
from accounts.admin import *
from categories.admin import *
from dashboard.admin import *
from payments.admin import *
from payments.mpesa_admin import *