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
        Profile.objects.get_or_create(user=instance)


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
    STATUS = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="subtasks")
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    completion_percentage = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        # Auto-set status from percentage
        if self.completion_percentage == 100:
            self.status = "completed"
        elif self.completion_percentage > 0:
            self.status = "in_progress"
        else:
            self.status = "pending"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title




    
class Document(models.Model):
    TYPE_CHOICES = [("text", "Text"), ("file", "File")]
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255, blank=True)
    doc_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="file")
    text_content = models.TextField(blank=True)
    file = models.FileField(upload_to="documents/", blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or f"{self.doc_type} by {self.uploaded_by.username}"