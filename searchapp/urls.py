from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("health/", views.health, name="health"),
    path("api/autocomplete/", views.autocomplete_api, name="autocomplete_api"),
    path("api/search/", views.search_api, name="search_api"),
    path("api/search/store/", views.search_store_api, name="search_store_api"),
    path("api/search/cache/", views.search_cache_api, name="search_cache_api"),
    path("api/bridge/mercadia/jobs/", views.mercadia_bridge_jobs_api, name="mercadia_bridge_jobs_api"),
    path("api/bridge/mercadia/push/", views.mercadia_bridge_push_api, name="mercadia_bridge_push_api"),
    path("api/bridge/mercadia/catalog/status/", views.mercadia_catalog_status_api, name="mercadia_catalog_status_api"),
    path("api/bridge/mercadia/catalog/start/", views.mercadia_catalog_start_api, name="mercadia_catalog_start_api"),
    path("api/bridge/mercadia/catalog/batch/", views.mercadia_catalog_batch_api, name="mercadia_catalog_batch_api"),
    path("api/bridge/mercadia/catalog/finish/", views.mercadia_catalog_finish_api, name="mercadia_catalog_finish_api"),
]
