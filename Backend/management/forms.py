from django import forms
from django.contrib.auth.models import User
from .models import Group, Work, SubTask, Document, Profile


class SignupForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    skills = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False,
                             help_text="List your skills, e.g. Python, Research, Writing")

    def clean(self):
        data = super().clean()
        if data.get("password") != data.get("confirm_password"):
            raise forms.ValidationError("Passwords do not match.")
        if User.objects.filter(username=data.get("username")).exists():
            raise forms.ValidationError("Username already taken.")
        return data


class GroupForm(forms.ModelForm):
    # Let leader pick existing users as members
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Group
        fields = ["name", "members"]


class AddMembersForm(forms.Form):
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    def __init__(self, group, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude leader and already-existing members
        self.fields["members"].queryset = User.objects.exclude(
            id=group.leader.id
        ).exclude(
            id__in=group.members.values_list("id", flat=True)
        )


class WorkForm(forms.ModelForm):
    group = forms.ModelChoiceField(queryset=Group.objects.none(), required=True)

    class Meta:
        model = Work
        fields = ["group", "title", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["group"].queryset = Group.objects.filter(leader=user)


class SubTaskForm(forms.ModelForm):
    class Meta:
        model = SubTask
        fields = ["work", "title", "assigned_to"]

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["work"].queryset = Work.objects.filter(group__leader=user)
        member_qs = User.objects.filter(custom_member_groups__leader=user).distinct()
        self.fields["assigned_to"].queryset = member_qs


class SubTaskProgressForm(forms.ModelForm):
    class Meta:
        model = SubTask
        fields = ["completion_percentage"]
        widgets = {
            "completion_percentage": forms.NumberInput(attrs={"min": 0, "max": 100, "type": "range"})
        }


class LeaderDocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["title", "doc_type", "text_content", "file"]
        widgets = {"text_content": forms.Textarea(attrs={"rows": 4})}

    def clean(self):
        data = super().clean()
        if data.get("doc_type") == "text" and not data.get("text_content"):
            raise forms.ValidationError("Provide text content for a text document.")
        if data.get("doc_type") == "file" and not data.get("file"):
            raise forms.ValidationError("Attach a file for a file document.")
        return data


class MemberDocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["title", "file"]

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if f:
            ext = f.name.split(".")[-1].lower()
            if ext not in ("pdf", "doc", "docx"):
                raise forms.ValidationError("Only PDF or Word files (.pdf, .doc, .docx) are allowed.")
        return f