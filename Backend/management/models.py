from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    skills = models.TextField(blank =True)
    is_leader = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()





class Group(models.Model):
    name = models.CharField(max_length=255)
    leader = models.ForeignKey(User, on_delete=models.CASCADE, related_name="led_groups")
    members = models.ManyToManyField(User, related_name="custom_member_groups", blank =True)

    def __str__(self):
        return self.name





class Work(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    title = models.CharField(max_length = 255)
    description = models.TextField()
    created_by = models.ForeignKey(User, on_delete = models.CASCADE)
    created_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title








class SubTask(models.Model):
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="subtasks")
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("in_progress", "In Progress"), ("completed", "Completed"), ], default = 'pending')

    def __str__(self):
        return self.title