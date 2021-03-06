from django.contrib.auth.decorators import login_required
from django.urls import path, re_path
from . import views


urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('activity/', login_required(views.PurchaseListView.as_view()), name='activity'),
    path('activity/get_accounts_sum/', views.get_accounts_sum),
    path('activity/get_purchases/', views.get_json_queryset),
    path('activity/net_worth_chart/', views.get_net_worth_chart_data),
    path('activity/purchase_category_chart/', views.get_pie_chart_data),
    path('activity/delete_purchase/', views.delete_purchase),
    re_path('.*filters/', views.filter_manager),
    path('activity/account_update/', views.account_update),
    path('activity/reset_credit_card/', views.reset_credit_card),
    path('settings/', views.settings, name='settings'),
    path('charts/', views.get_purchases_chart_data),
    path('get_quick_entries/', views.get_quick_entries),
    path('information', views.information_page, name='information page'),
]
