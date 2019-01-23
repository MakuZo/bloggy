from django.urls import path

from .views import (EntryDetailView, HomeView, NotificationListView,
                    PrivateMessageView, UserDetailView, UserRankingView)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("top/", HomeView.as_view(), {"sorting": "top"}, name="top"),
    path("hot/", HomeView.as_view(), {"sorting": "hot"}, name="hot"),
    path("entries/tag/<str:tag>/", HomeView.as_view(), name="tag"),
    path("ranking/", UserRankingView.as_view(), name="ranking"),
    path("entries/<int:pk>/", EntryDetailView.as_view(), name="entry-detail-view"),
    path("notifications/", NotificationListView.as_view(), name="notifications-all"),
    path("inbox/", PrivateMessageView.as_view(), name="inbox"),
    path("inbox/user/<str:target>/", PrivateMessageView.as_view(), name="inbox-user-view"),
    path("users/<str:username>/", UserDetailView.as_view(), name="user-detail-view"),
]
