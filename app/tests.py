import bleach
import markdown
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Entry, Notification, PrivateMessage, Tag, User

MARKDOWN_SAMPLE = """# hello, This is Markdown Live Preview
----
## what is Markdown?
see [Wikipedia](http://en.wikipedia.org/wiki/Markdown)
> Markdown is a lightweight markup language, originally created by John Gruber and Aaron Swartz allowing people "to write using an easy-to-read, easy-to-write plain text format, then convert it to structurally valid XHTML (or HTML)".
----
## usage
1. Write markdown text in this textarea.
2. Click 'HTML Preview' button.
----
## markdown quick reference
# headers
*emphasis*
**strong**
* list
"""


class PrivateMessageAPIViewTestCase(APITestCase):
    def setUp(self):
        User.objects.create(username="testuser1", email="test1@email.com")
        User.objects.create(username="testuser2", email="test2@email.com")

    def test_user_cant_message_himself(self):
        """Ensure that users cannot message themselves"""
        user = User.objects.get(username="testuser1")
        self.client.force_authenticate(user)
        url = reverse("privatemessages-list")
        data = {"target": user.username, "text": "Test private message"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_author_cannot_change_read_attribute(self):
        """Ensure that author of a PM cant 'read' message for target"""
        user = User.objects.get(username="testuser1")
        user2 = User.objects.get(username="testuser2")
        self.client.force_authenticate(user)
        url = reverse("privatemessages-list")
        data = {"target": user2.username, "text": "Test private message"}
        response = self.client.post(url, data, format="json")
        url = reverse("privatemessages-read", kwargs={"pk": response.data["id"]})
        self.client.post(url)
        self.client.force_authenticate(user2)
        url = reverse("privatemessages-detail", kwargs={"pk": response.data["id"]})
        response = self.client.get(url)
        self.assertEqual(response.data["read"], False)

    def test_text_cannot_be_empty(self):
        """Ensure that user can't send empty PM"""
        user = User.objects.get(username="testuser1")
        user2 = User.objects.get(username="testuser2")
        self.client.force_authenticate(user)
        url = reverse("privatemessages-list")
        data = {"target": user2.username, "text": ""}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_to_user_that_exists(self):
        """Ensure that target user must exist when sending PM"""
        user = User.objects.get(username="testuser1")
        self.client.force_authenticate(user)
        url = reverse("privatemessages-list")
        data = {"target": "userDoesntExist", "text": "Test private message"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_read_attribute_for_author(self):
        """Ensure that, for PM author, the 'read' attribute is always True"""
        user = User.objects.get(username="testuser1")
        user2 = User.objects.get(username="testuser2")
        self.client.force_authenticate(user)
        url = reverse("privatemessages-list")
        data = {"target": user2.username, "text": "Test private message"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.data["read"], True)


class NotificationAPIViewTestCase(APITestCase):
    def test_disallow_read_false(self):
        u = User.objects.create(username="testuser")
        e = Entry.objects.create(pk=1, content="test", user=u, deleted=True)
        Notification.objects.create(
            pk=1, type="user_replied", sender=u, object=e, target=u
        )
        self.client.force_authenticate(user=u)
        url = reverse("notifications-detail", kwargs={"pk": 1})
        data = {"read": True}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        data = {"read": False}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_allow_authenticated_users_only(self):
        url = reverse("notifications-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_only_users_notifications(self):
        u = User.objects.create(username="testuser")
        u2 = User.objects.create(username="testuser2", email="email")
        e = Entry.objects.create(pk=1, content="test", user=u, deleted=True)
        Notification.objects.create(type="user_replied", sender=u, object=e, target=u2)
        self.client.force_authenticate(user=u)
        url = reverse("notifications-list")
        response = self.client.get(url)
        self.assertEqual(len(response.data["results"]), 0)


class EntryAPIViewTestCase(APITestCase):
    def test_allow_get_only_when_deleted(self):
        user = User.objects.create(username="testuser")
        Entry.objects.create(pk=1, content="test", user=user, deleted=True)
        self.client.force_authenticate(user=user)
        url = reverse("entry-detail", kwargs={"pk": 1})
        data = {"content": ""}
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deleted_entry_content(self):
        user = User.objects.create(username="testuser")
        entry = Entry.objects.create(pk=1, content="test", user=user)
        Entry.objects.create(parent=entry, content="test", user=user)
        entry.delete()
        self.client.force_authenticate(user=user)
        url = reverse("entry-detail", kwargs={"pk": 1})
        response = self.client.get(url)
        self.assertEqual(response.data["content"], "<p><em>deleted</em></p>")
        self.assertEqual(response.data["content_formatted"], "<p><em>deleted</em></p>")

    def test_allow_post_when_owner_only(self):
        user = User.objects.create(username="testuser")
        owner = User.objects.create(username="Owner", email="test@test.test")
        Entry.objects.create(pk=1, content="test", user=owner)
        self.client.force_authenticate(user=user)
        url = reverse("entry-detail", kwargs={"pk": 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = {"content": ""}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_allow_authenticated_users_only(self):
        user = User.objects.create(username="testuser")
        Entry.objects.create(pk=1, content="test", user=user)
        url = reverse("entry-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        url = reverse("entry-detail", kwargs={"pk": 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TagTestCase(TestCase):
    def setUp(self):
        self.u = User.objects.create(
            username="testuser", email="testuser@testuser.testuser"
        )
        self.u2 = User.objects.create(
            username="testuser2", email="testuse2r@testuser2.testuser2"
        )
        self.u3 = User.objects.create(
            username="testuser3", email="testuser3@testuser3.testuser3"
        )
        self.t = Tag.objects.create(name="testtag")
        self.t2 = Tag.objects.create(name="testtag2")
        self.t.observers.add(self.u)
        self.t.observers.add(self.u2)
        self.t2.observers.add(self.u3)

    def test_notification_creation(self):
        Entry.objects.create(
            user=self.u, content="#testtag#this shouldn't create notifications"
        )
        self.assertFalse(Notification.objects.all().exists())
        Entry.objects.create(
            user=self.u, content="#testtag this should create 1 notification"
        )
        self.assertEqual(Notification.objects.all().count(), 1)
        Entry.objects.create(
            user=self.u2, content="#testtag this #should_ create 1 notification"
        )
        self.assertEqual(Notification.objects.all().count(), 2)
        Entry.objects.create(
            user=self.u3, content="#testtag this should create 2 notifications"
        )
        self.assertEqual(Notification.objects.all().count(), 4)
        Entry.objects.all().update(content="#this #should #not #create #notifications!")
        self.assertEqual(Notification.objects.all().count(), 4)

    def test_tag_creation(self):
        Entry.objects.create(
            user=self.u, content="#testtagthree this should create 1 tag"
        )
        self.assertEqual(Tag.objects.all().count(), 3)
        Entry.objects.create(
            user=self.u, content="#testTAGthree this shouldn't create a tag"
        )
        Entry.objects.create(
            user=self.u, content="#testtag#this shouldn't create a tag"
        )
        self.assertEqual(Tag.objects.all().count(), 3)
        Entry.objects.create(
            user=self.u, content="#testtag #testtagfourth should create 1 tag"
        )
        self.assertEqual(Tag.objects.all().count(), 4)


class EntryViewSetTestCase(TestCase):
    def test_soft_deletion(self):
        u = User.objects.create(username="testuser")
        e = Entry.objects.create(pk=1, user=u, content="test")
        Entry.objects.create(pk=2, user=u, content="test2", parent=e)
        e.delete()
        self.assertIsNotNone(Entry.objects.get(pk=1))
        self.assertIsNotNone(Entry.objects.get(pk=2))
        self.assertTrue(e.deleted)

    def test_hard_deletion(self):
        u = User.objects.create(username="testuser")
        e = Entry.objects.create(pk=1, user=u, content="test")
        e2 = Entry.objects.create(pk=2, user=u, content="test2", parent=e)
        e2.delete()
        e.delete()
        self.assertRaises(Entry.DoesNotExist, Entry.objects.get, pk=1)
        self.assertRaises(Entry.DoesNotExist, Entry.objects.get, pk=2)


class UserEntryTestCase(TestCase):
    def setUp(self):
        Entry.objects.create(
            pk=1,
            user=User.objects.create(
                pk=1, username="testuser", email="test@test.test", password="Test1234"
            ),
            content=MARKDOWN_SAMPLE,
        )

    def test_content_formatted(self):
        """Test if content_formatted equals content as it's part of custom save method"""
        e = Entry.objects.get(pk=1)
        e.save()
        self.assertEqual(
            e.content,
            bleach.clean(
                MARKDOWN_SAMPLE, settings.MARKDOWN_TAGS, settings.MARKDOWN_ATTRS
            ),
        )

    def test_user_points(self):
        """
        Test if user's points are properly calculated
        """
        self.assertEqual(User.objects.get(pk=1).points, 1)
        e = Entry.objects.create(pk=2, user=User.objects.get(pk=1))
        self.assertEqual(User.objects.get(pk=1).points, 2)
        e.upvotes.add(User.objects.get(pk=1))
        self.assertEqual(User.objects.get(pk=1).points, 3)
        Entry.objects.filter(user=User.objects.get(pk=1)).delete()
        self.assertEqual(User.objects.get(pk=1).points, 0)
