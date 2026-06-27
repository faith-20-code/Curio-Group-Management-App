from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Work, SubTask, Group, Profile



class ProfileInline(admin.StackedInline):
    model = Profile
    fields = ("skills", "is_leader")
    extra = 0
    can_delete = False
    max_num = 1

class CustomUserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_leader")
    list_filter = ("is_leader",)
    search_fields = ("user__username",)
    fieldsets = (
        (None, {"fields": ("user",)}),
        ("Profile Information", {"fields": ("skills", "is_leader")}),
    )

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)



@admin.register(SubTask)
class SubTaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "work",
        "assigned_to",
        "status",
    )

    list_filter = ("status",)
    search_fields = ("title",)
    ordering = ("status",)

class SubTaskInline(admin.TabularInline):
    model = SubTask
    extra = 0



@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ("title", "group", "created_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("title", "description")
    ordering = ("-created_at",)
    inlines = [SubTaskInline]


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    filter_horizontal = ("members",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "leader":
            kwargs["queryset"] = User.objects.filter(profile__is_leader=True)

        return super().formfield_for_foreignkey(
            db_field, request, **kwargs
        )