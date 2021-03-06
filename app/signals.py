import re

from django.db.models.signals import m2m_changed, post_save, pre_delete
from django.dispatch import receiver
from django.urls import reverse

from .models import Entry, Notification, User


@receiver(post_save, sender=Entry)
def entry_notification(sender, instance, created, **kwargs):
    """
    Signal used to create notification(s) when an entry is created
    This function notifies an user if this entry is a reply to him.
    This function notifies an user if he's mentioned (by @username) in one's entry
    """
    if created:
        # First find usernames mentioned (by @ tag)
        p = re.compile(r"^(@)(\w+)$")
        usernames = set(
            [
                p.match(c).group(2).lower()
                for c in instance.content.split()
                if p.match(c)
            ]
        )
        # Remove the author of an entry from users to notify
        if instance.user.username in usernames:
            usernames.remove(instance.user.username)
        # If entry has a parent and it's parent is not the same author then notify about a reply
        # and delete from usernames if being notified
        if instance.parent and instance.parent.user.username != instance.user.username:
            if instance.parent.user.username in usernames:
                usernames.remove(instance.parent.user.username)
            Notification.objects.create(
                type="user_replied",
                sender=instance.user,
                target=instance.parent.user,
                object=instance,
            )
        # Notify mentioned users without the author of an entry
        for name in usernames:
            if name == instance.user.username:
                continue
            try:
                target = User.objects.get(username=name)
            except Exception:
                continue
            Notification.objects.create(
                type="user_mentioned",
                sender=instance.user,
                target=target,
                object=instance,
            )


@receiver(m2m_changed, sender=Entry.tags.through)
def entry_tag_notification(instance, action, **kwargs):
    """
    Notifies users if one of the tags in entry is observed by them.
    """
    if not instance.modified_date and "post" in action:
        already_notified = set()
        reversed_user = reverse(
            "user-detail-view", kwargs={"username": instance.user.username}
        )
        reversed_entry = reverse("entry-detail-view", kwargs={"pk": instance.pk})
        all_tags = instance.tags.all().prefetch_related("observers", "blacklisters")
        all_blacklisters = [
            blacklister for tag in all_tags for blacklister in tag.blacklisters.all()
        ]
        to_create = []
        for tag in all_tags:
            for observer in tag.observers.all():
                # If user blacklisted one of the tags in an entry, don't notify him.
                if observer in all_blacklisters:
                    continue
                if (
                    observer.username == instance.user.username
                    or observer in already_notified
                ):
                    continue
                reversed_tag = reverse("tag", kwargs={"tag": tag.name})
                content = (
                    f'<a href="{reversed_user}">{instance.user.username}</a> used tag <a href="{reversed_tag}">#{tag.name}</a>'
                    f' in <a href="{reversed_entry}">"{instance.content:.25}..."</a>'
                )
                to_create.append(
                    Notification(
                        type="tag_used",
                        sender=instance.user,
                        target=observer,
                        object=instance,
                        content=content,
                    )
                )
                already_notified.add(observer)
        Notification.objects.bulk_create(to_create)
