from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    skills = models.TextField(blank=True)
    is_leader = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    # Only need get_or_create here. The second signal below was redundant
    # (every User save fired a second DB hit doing nothing new).
    if created:
        Profile.objects.get_or_create(user=instance)


class Group(models.Model):
    name = models.CharField(max_length=255)
    leader = models.ForeignKey(User, on_delete=models.CASCADE, related_name="led_groups")
    members = models.ManyToManyField(User, related_name="custom_member_groups", blank=True)

    def __str__(self):
        return self.name


class Work(models.Model):
    STATUS = [
        ("pending", "Pending"),        # no subtasks broken down yet
        ("in_progress", "In Progress"),  # subtasks exist, work underway
        ("completed", "Completed"),     # all subtasks completed
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    document = models.FileField(upload_to="work_docs/", blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    # Bug fix: this was auto_now=True, which silently overwrote the
    # creation timestamp on every single save() call (admin edits,
    # subtask cascades, anything touching the row). auto_now_add=True
    # sets it once at creation and never again.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def is_broken_down(self):
        """True once at least one subtask exists — blocks re-breakdown."""
        return self.subtasks.exists()

    def recalculate_status(self):
        """Call after any subtask is created/updated/deleted."""
        subtasks = self.subtasks.all()
        if not subtasks.exists():
            new_status = "pending"
        elif all(s.status == "completed" for s in subtasks):
            new_status = "completed"
        else:
            new_status = "in_progress"
        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status"])

    @property
    def completion_percentage(self):
        subtasks = self.subtasks.all()
        if not subtasks.exists():
            return 0
        return round(sum(s.completion_percentage for s in subtasks) / subtasks.count())


class SubTask(models.Model):
    STATUS = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]
    SOURCE = [
        ("manual", "Manually assigned"),
        ("ai", "AI auto-assigned"),
    ]

    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="subtasks")
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    completion_percentage = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=10, choices=SOURCE, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Same work + same title = duplicate, regardless of assignee.
        # The leader can still get a heads-up and override via the view
        # logic (force=True param), but the DB itself won't silently
        # allow two identical titles under the same work.
        constraints = [
            models.UniqueConstraint(fields=["work", "title"], name="unique_subtask_title_per_work")
        ]

    def __str__(self):
        return self.title

    @property
    def has_steps(self):
        return self.steps.exists()

    def recalculate_completion(self):
        """
        Completion is now DERIVED from steps, not hand-typed by the member.
        If no steps exist yet, leave completion_percentage as-is (0 by
        default) since there's nothing to compute from.
        """
        steps = self.steps.all()
        if steps.exists():
            done = steps.filter(is_done=True).count()
            total = steps.count()
            self.completion_percentage = round(done / total * 100)

        if self.completion_percentage == 100:
            self.status = "completed"
        elif self.completion_percentage > 0:
            self.status = "in_progress"
        else:
            self.status = "pending"

        self.save(update_fields=["completion_percentage", "status"])
        self.work.recalculate_status()


class SubTaskStep(models.Model):
    """
    The 3rd level: actionable to-dos under a subtask, e.g. SubTask "Bake cake"
    -> Steps "mix dry ingredients", "put in oven". Can be added manually by
    the assigned member or generated via AI (using the Work's original
    document as context), regardless of whether the parent SubTask itself
    was created manually or by AI.
    """
    subtask = models.ForeignKey(SubTask, on_delete=models.CASCADE, related_name="steps")
    title = models.CharField(max_length=255)
    is_done = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    generated_by_ai = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.title} ({'done' if self.is_done else 'open'})"


class Document(models.Model):
    TYPE_CHOICES = [("text", "Text"), ("file", "File")]
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="documents")
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="documents", blank=True, null=True)
    title = models.CharField(max_length=255, blank=True)
    doc_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="file")
    text_content = models.TextField(blank=True)
    file = models.FileField(upload_to="documents/", blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or f"{self.doc_type} by {self.uploaded_by.username}"