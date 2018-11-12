from django.contrib.auth import login, authenticate
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.views.generic.detail import DetailView
from django.shortcuts import render, redirect
from django.db.models import Count
from django.utils import timezone

from .models import Entry, User
from .forms import SignUpForm

from mptt.utils import get_cached_trees
from datetime import timedelta


class EntryDetailView(DetailView):
    model = Entry

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entries"] = (
            super().get_object().get_root().get_descendants(include_self=True)
        )
        return context


class UserDetailView(DetailView):
    model = User

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_entries = Entry.objects.filter(user=super().get_object().pk)[:5]
        qs = []
        for entry in user_entries:
            for node in list(entry.get_family()):
                qs.append(node)
        print(qs)
        context['user'].entries = qs
        context['user'].entries_count = user_entries.count()
        context['user'].points = context['user'].entries_count + sum([entry.upvotes.count() for entry in user_entries])
        return context


def home(request, sorting="new"):
    """
    Home (front page) view.
    It accepts one keyword parameter 'sorting' which is passed from 'hot' and 'top' views.
    To sort a TreeModel from django-mptt this function first sorts root nodes and then
    rebuilds the trees using get_descendants method on every root.
    """
    if sorting == "new":
        root_nodes = Entry.objects.root_nodes()
    elif sorting == "hot":
        root_nodes = (
            Entry.objects.root_nodes()
            .filter(created_date__gte=timezone.now() - timedelta(hours=6))
            .annotate(
                hotness=((Count("upvotes") + Count("downvotes"))*0.5 +Count("children"))
            )
            .order_by("-hotness")
        )
    elif sorting == "top":
        # Top sorting sorts descending by subtracting root's downvotes from upvotes
        root_nodes = (
            Entry.objects.root_nodes()
            .annotate(overall_votes=(Count("upvotes") - Count("downvotes")))
            .order_by("-overall_votes")
        )
    paginator = Paginator(root_nodes, 25)
    page = request.GET.get("page")
    queryset = []
    try:
        queryset = paginator.page(page)
    except PageNotAnInteger:
        queryset = paginator.page(1)
    except EmptyPage:
        queryset = paginator.page(paginator.num_pages)
    new_queryset = []
    for node in queryset.object_list:
        new_queryset.append(node)
        new_queryset.extend(node.get_descendants())
    queryset.object_list = new_queryset
    if request.user.is_authenticated:
        for entry in queryset:
            if entry.upvotes.filter(pk=request.user.id).exists():
                entry.style_class = "user-upvoted"
            elif entry.downvotes.filter(pk=request.user.id).exists():
                entry.style_class = "user-downvoted"
            elif entry.votes_sum == 0:
                entry.style_class = "neutral"
            elif entry.votes_sum > 0:
                entry.style_class = "positive"
            else:
                entry.style_class = "negative"

    return render(request, "app/base.html", {"entries": queryset})


def top(request):
    return home(request, "top")


def hot(request):
    return home(request, "hot")


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            raw_password = form.cleaned_data.get("password1")
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect("home")
    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})