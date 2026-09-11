from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("health/", views.health, name="health"),
    path("api/autocomplete/", views.autocomplete_api, name="autocomplete_api"),
    path("api/search/", views.search_api, name="search_api"),
    path("api/search/store/", views.search_store_api, name="search_store_api"),
    path("api/search/cache/", views.search_cache_api, name="search_cache_api"),
]
